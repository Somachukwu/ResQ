import os
import math
import time
from functools import wraps
from dotenv import load_dotenv

# Ensure environment variables (.env) are loaded before importing backend modules
load_dotenv()

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO
import requests

from backend.database import (
    init_db,
    get_hospitals,
    get_responders,
    get_responder_by_code,
    get_incidents,
    get_incident_by_uuid,
    create_incident,
    update_incident,
    get_incident_updates,
    get_scene_hazards,
    add_incident_update,
    add_scene_hazard
)
from backend.database import assign_responder_to_incident, update_responder_telemetry, USING_MYSQL, get_db_connection
from backend.security import require_role, is_rate_limited, has_operator_token
import uuid
import base64
from backend.socket_events import register_socket_events
from backend.synthetic_injector import inject_expressway_crash, inject_urban_flood
from backend.weather_service import get_weather_for_coords
from backend.severity_engine import calculate_rsi
from backend.flood_model import evaluate_basin_flood_risk, get_flood_hazard_geojson
from backend.corridor_risk import evaluate_all_corridors, calculate_corridor_risk_index
from backend.survival_optimizer import optimize_trauma_routing, compute_survival_probability
from backend.gemini_triage import extract_telemetry_and_guidance, analyze_scene_photo
from backend.geocoding_service import resolve_landmark
from backend.debrief_generator import generate_incident_debrief

app = Flask(
    __name__,
    template_folder="frontend",
    static_folder="frontend/static",
    static_url_path="/static"
)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "resq-emergency-intelligence-secret-key-2026")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

if os.getenv("RESQ_REQUIRE_AUTH", "0").lower() in ("1", "true", "yes") and app.config["SECRET_KEY"] == "resq-emergency-intelligence-secret-key-2026":
    raise RuntimeError("SECRET_KEY must be configured when RESQ_REQUIRE_AUTH is enabled")

# Initialize real-time SocketIO bus
_DEFAULT_CORS = "https://somachukwu.github.io,http://localhost:5000,http://127.0.0.1:5000"
CORS_ORIGINS = {origin.strip() for origin in os.getenv("CORS_ORIGINS", _DEFAULT_CORS).split(",") if origin.strip()}
socketio = SocketIO(app, cors_allowed_origins=list(CORS_ORIGINS), async_mode="threading")
_orig_socketio_run = socketio.run
def _guarded_run(*args, **kwargs):
    kwargs.setdefault("allow_unsafe_werkzeug", True)
    return _orig_socketio_run(*args, **kwargs)
socketio.run = _guarded_run
register_socket_events(socketio)

# Initialize local database schema and seed data
init_db()


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin in CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), geolocation=(self), microphone=(self)"
    return response


@app.before_request
def protect_requests():
    if request.path.startswith("/api/civilian/"):
        limit = 30
    elif request.path.startswith("/api/"):
        limit = 120
    else:
        return None
    if is_rate_limited(limit):
        return jsonify({"error": "Too many requests. Please try again shortly."}), 429
    return None


@app.errorhandler(413)
def payload_too_large(_error):
    return jsonify({"error": "Upload exceeds the 5 MB limit"}), 413


@app.errorhandler(ValueError)
def invalid_request(error):
    return jsonify({"error": str(error)}), 400


def json_object():
    data = request.get_json(silent=True)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("JSON request body must be an object")
    return data


def valid_coordinates(lat, lng):
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        raise ValueError("lat and lng must be numeric")
    if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError("Coordinates are outside valid geographic bounds")
    return lat, lng


@app.route("/resources/<path:filename>")
@app.route("/Resources/<path:filename>")
def serve_resources(filename):
    return send_from_directory(os.path.join(app.root_path, "frontend", "Resources"), filename)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "frontend"), "favicon.ico", mimetype="image/vnd.microsoft.icon")


@app.route("/manifest.json")
def manifest():
    return send_from_directory(os.path.join(app.root_path, "frontend"), "manifest.json", mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    response = send_from_directory(os.path.join(app.root_path, "frontend"), "sw.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    return response


ORS_API_KEY = os.getenv("ORS_API_KEY")


# --- Page Routing ---

@app.route("/templates/static/<path:filename>")
def serve_templates_static(filename):
    return send_from_directory(os.path.join(app.root_path, "frontend", "static"), filename)

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/civilian")
@app.route("/templates/civilian/index.html")
def civilian():
    return render_template("templates/civilian/index.html")


@app.route("/dispatcher")
@app.route("/templates/dispatcher/dashboard.html")
def dispatcher():
    return render_template("templates/dispatcher/dashboard.html")


@app.route("/responder")
@app.route("/templates/responder/scene_brief.html")
def responder():
    return render_template("templates/responder/scene_brief.html")


# --- REST API Endpoints ---

@app.route("/api/incidents", methods=["GET", "POST"])
def incidents_api():
    if request.method == "POST":
        data = json_object()
        data["lat"], data["lng"] = valid_coordinates(data.get("lat"), data.get("lng"))
        data["casualties_count"] = max(1, min(100, int(data.get("casualties_count", 1))))
        if any(k in data for k in ("unresponsive", "severe_hemorrhage", "airway_compromise", "entrapment")):
            triage = calculate_rsi(
                unresponsive=data.get("unresponsive", False),
                severe_hemorrhage=data.get("severe_hemorrhage", False),
                airway_compromise=data.get("airway_compromise", False),
                entrapment=data.get("entrapment", False),
                casualties_count=data.get("casualties_count", 1),
                scene_hazards=data.get("scene_hazards", [])
            )
            data["severity_score"] = triage["rsi_score"]
            data["severity_level"] = triage["priority_label"]
        incident = create_incident(data)
        # Notify connected dispatchers
        socketio.emit("incident:new", incident, room="dispatchers")
        return jsonify(incident), 201
    if not has_operator_token():
        return jsonify({"error": "Valid operator credentials required"}), 401
    status = request.args.get("status")
    incidents = get_incidents(status=status)
    return jsonify(incidents)


@app.route("/api/incidents/<incident_uuid>", methods=["GET"])
def incident_detail_api(incident_uuid):
    if not has_operator_token():
        return jsonify({"error": "Valid operator credentials required"}), 401
    incident = get_incident_by_uuid(incident_uuid)
    if not incident:
        return jsonify({"error": "Incident not found"}), 404
        
    updates = get_incident_updates(incident_uuid)
    hazards = get_scene_hazards(incident_uuid)
    
    return jsonify({
        "incident": incident,
        "updates": updates,
        "hazards": hazards
    })


@app.route("/api/incidents/<incident_uuid>/edit", methods=["POST"])
@require_role("dispatcher")
def edit_incident_api(incident_uuid):
    incident = get_incident_by_uuid(incident_uuid)
    if not incident:
        return jsonify({"error": "Incident not found"}), 404
    data = json_object()
    allowed_updates = {}
    if "title" in data and str(data["title"]).strip():
        allowed_updates["title"] = str(data["title"]).strip()
    if "casualties_count" in data:
        try:
            allowed_updates["casualties_count"] = max(1, int(data["casualties_count"]))
        except (ValueError, TypeError):
            pass
    if "severity_level" in data and data["severity_level"] in ("low", "moderate", "urgent", "critical"):
        allowed_updates["severity_level"] = data["severity_level"]
    if "location_name" in data and str(data["location_name"]).strip():
        allowed_updates["location_name"] = str(data["location_name"]).strip()
    
    if not allowed_updates:
        return jsonify({"error": "No valid fields provided"}), 400

    updated = update_incident(incident_uuid, allowed_updates)
    add_incident_update(
        incident_uuid=incident_uuid,
        source="dispatcher",
        update_type="manual_override",
        content=f"Commander updated incident records: {', '.join(f'{k}={v}' for k, v in allowed_updates.items())}"
    )
    socketio.emit("incident:update", dict(updated), room="dispatchers")
    socketio.emit("incident:update", dict(updated), room="responders")
    socketio.emit("incident:update", dict(updated), room=f"incident_{incident_uuid}")
    return jsonify({"status": "success", "incident": updated})


@app.route("/api/incidents/<incident_uuid>/dispatcher-message", methods=["POST"])
def dispatcher_message_api(incident_uuid):
    incident = get_incident_by_uuid(incident_uuid)
    if not incident:
        return jsonify({"error": "Incident not found"}), 404
    data = json_object()
    message = str(data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message required"}), 400

    add_incident_update(
        incident_uuid=incident_uuid,
        source="dispatcher",
        update_type="comms",
        content=message
    )

    payload = {
        "incident_uuid": incident_uuid,
        "message": message,
        "sender": "Commander",
        "timestamp": time.time()
    }
    socketio.emit("dispatcher:message", payload, room=f"incident_{incident_uuid}")
    socketio.emit("dispatcher:message", payload, room="dispatchers")
    socketio.emit("dispatcher:message", payload, room="responders")
    socketio.emit("dispatcher:message", payload, room="civilians")
    return jsonify({"status": "success", "message": message})


@app.route("/api/incidents/<incident_uuid>/call-bridge", methods=["POST"])
def call_bridge_api(incident_uuid):
    data = json_object()
    action = str(data.get("action") or "start").strip().lower()
    call_type = str(data.get("type") or "voice").strip()
    title = str(data.get("title") or "Tactical Voice Bridge").strip()

    incident = get_incident_by_uuid(incident_uuid)
    is_active = action not in ("end", "stop", "disconnect", "hangup")
    caller = str(data.get("caller") or "command")

    add_incident_update(
        incident_uuid=incident_uuid,
        source=caller,
        update_type="call_bridge",
        content=f"Voice bridge event: {action} ({title})"
    )

    payload = {
        "incident_uuid": incident_uuid,
        "active": is_active,
        "action": action,
        "type": call_type,
        "title": title,
        "caller": caller,
        "timestamp": time.time()
    }
    socketio.emit("call_bridge:event", payload, room=f"incident_{incident_uuid}")
    socketio.emit("call_bridge:event", payload, room="dispatchers")
    socketio.emit("call_bridge:event", payload, room="responders")
    socketio.emit("call_bridge:event", payload, room="civilians")
    socketio.emit("call_bridge:event", payload, broadcast=True)
    return jsonify({"status": "success", "active": is_active, "incident_uuid": incident_uuid})


@app.route("/api/responder/route-change", methods=["POST"])
def responder_route_change_api():
    data = json_object()
    incident_uuid = data.get("incident_uuid")
    new_route = str(data.get("new_route") or "Detour instructed by command").strip()
    note = str(data.get("note") or new_route).strip()

    if incident_uuid:
        add_incident_update(
            incident_uuid=incident_uuid,
            source="dispatcher",
            update_type="route_change",
            content=f"Tactical route change: {new_route}"
        )

    payload = {
        "incident_uuid": incident_uuid,
        "new_route": new_route,
        "note": note,
        "timestamp": time.time()
    }
    socketio.emit("responder:route_change", payload, room="responders")
    socketio.emit("responder:route_change", payload, room="dispatchers")
    if incident_uuid:
        socketio.emit("responder:route_change", payload, room=f"incident_{incident_uuid}")
    return jsonify({"status": "success", "new_route": new_route, "incident_uuid": incident_uuid})


@app.route("/api/incidents/<incident_uuid>/debrief", methods=["GET"])
@require_role("dispatcher")
def incident_debrief_api(incident_uuid):
    """Generates structured clinical debrief and markdown report for resolved or active incidents."""
    incident = get_incident_by_uuid(incident_uuid)
    if not incident:
        return jsonify({"error": "Incident not found"}), 404

    updates = get_incident_updates(incident_uuid)
    hazards = get_scene_hazards(incident_uuid)
    
    hospital = None
    if incident.get("recommended_hospital_id"):
        all_h = get_hospitals()
        matched = [h for h in all_h if h["id"] == incident["recommended_hospital_id"]]
        if matched:
            hospital = matched[0]

    responder = None
    if incident.get("assigned_responder_id"):
        responder = get_responder_by_code(incident["assigned_responder_id"])

    debrief = generate_incident_debrief(
        incident=incident,
        updates=updates,
        hazards=hazards,
        hospital=hospital,
        responder=responder
    )
    return jsonify(debrief)


@app.route("/api/responder/assign", methods=["POST"])
@require_role("dispatcher")
def assign_responder_api():
    """Assigns an emergency responder unit to an incident and broadcasts real-time telemetry."""
    data = json_object()
    incident_uuid = data.get("incident_uuid")
    unit_code = data.get("unit_code")

    if not incident_uuid or not unit_code:
        return jsonify({"error": "incident_uuid and unit_code required"}), 400

    updated_inc, responder, assignment_error = assign_responder_to_incident(incident_uuid, unit_code)
    if assignment_error == "not_found":
        return jsonify({"error": "Incident or responder not found"}), 404
    if assignment_error:
        return jsonify({"error": assignment_error.replace("_", " ")}), 409

    # Log dispatch audit update
    add_incident_update(
        incident_uuid=incident_uuid,
        source="dispatcher",
        update_type="dispatch",
        content=f"Unit {unit_code} ({responder['name']}) dispatched to incident site."
    )

    # Broadcast to dispatchers, responders, and civilian room
    payload = {
        "incident_uuid": incident_uuid,
        "unit_code": unit_code,
        "responder_name": responder["name"],
        "status": "dispatched",
        "timestamp": updated_inc["updated_at"]
    }
    socketio.emit("responder:assigned", payload, room="dispatchers")
    socketio.emit("responder:assigned", payload, room="responders")
    socketio.emit("responder:mission_alert", payload, room=f"responder_{unit_code}")

    return jsonify({
        "status": "success",
        "incident": updated_inc,
        "responder": get_responder_by_code(unit_code)
    })


@app.route("/api/responder-telemetry", methods=["POST"])
@require_role("responder")
def responder_telemetry_beacon_api():
    """Ingests periodic GPS beacon from active responder unit and emits live tracking event."""
    data = json_object()
    unit_code = data.get("unit_code")
    lat = data.get("lat")
    lng = data.get("lng")
    heading = data.get("heading", 0.0)
    speed_kmh = data.get("speed_kmh", 0.0)

    if not unit_code or lat is None or lng is None:
        return jsonify({"error": "unit_code, lat, lng required"}), 400
    lat, lng = valid_coordinates(lat, lng)
    try:
        heading = float(heading)
        speed_kmh = float(speed_kmh)
    except (TypeError, ValueError):
        return jsonify({"error": "heading and speed_kmh must be numeric"}), 400
    if not 0 <= heading < 360 or not 0 <= speed_kmh <= 250:
        return jsonify({"error": "telemetry values outside safe bounds"}), 400

    if not update_responder_telemetry(unit_code, lat=lat, lng=lng, heading=heading, speed_kmh=speed_kmh):
        return jsonify({"error": "Responder not found"}), 404

    # Broadcast live pin update to dispatcher and responder GIS screens
    beacon_payload = {
        "unit_code": unit_code,
        "lat": lat,
        "lng": lng,
        "heading": heading,
        "speed_kmh": speed_kmh
    }
    socketio.emit("telemetry:update", beacon_payload, room="dispatchers")
    socketio.emit("responder:beacon", beacon_payload, room="responders")

    return jsonify({"status": "beacon_recorded", "data": beacon_payload})


@app.route("/api/responders", methods=["GET"])
@require_role("dispatcher")
def responders_api():
    responders = get_responders()
    return jsonify(responders)


@app.route("/api/hospitals", methods=["GET"])
@require_role("dispatcher")
def hospitals_api():
    capability = request.args.get("capability")
    hospitals = get_hospitals(capability=capability)
    return jsonify(hospitals)


@app.route("/api/incidents/<incident_uuid>/acknowledge", methods=["POST"])
@require_role("responder")
def acknowledge_brief_api(incident_uuid):
    """Persist a responder's acknowledgement instead of treating it as UI state."""
    incident = get_incident_by_uuid(incident_uuid)
    if not incident:
        return jsonify({"error": "Incident not found"}), 404
    data = json_object()
    unit_code = data.get("unit_code")
    if not unit_code or incident.get("assigned_responder_id") != unit_code:
        return jsonify({"error": "This unit is not assigned to the incident"}), 403
    add_incident_update(incident_uuid, "responder", f"Unit {unit_code} acknowledged the mission brief.", "acknowledgement")
    payload = {"incident_uuid": incident_uuid, "unit_code": unit_code, "status": "acknowledged"}
    socketio.emit("responder:acknowledged", payload, room="dispatchers")
    socketio.emit("responder:acknowledged", payload, room=f"incident_{incident_uuid}")
    return jsonify({"status": "acknowledged", "data": payload})


@app.route("/api/weather", methods=["GET"])
def weather_api():
    lat = request.args.get("lat", type=float, default=6.4474)
    lng = request.args.get("lng", type=float, default=7.5098)
    region = request.args.get("region", default="community")
    weather_data = get_weather_for_coords(lat=lat, lng=lng, region_code=region)
    return jsonify(weather_data)


@app.route("/api/demo/inject", methods=["POST"])
@require_role("dispatcher")
def demo_inject_api():
    if os.getenv("RESQ_ENABLE_DEMO", "1" if os.getenv("RESQ_REQUIRE_AUTH", "0").lower() not in ("1", "true", "yes") else "0").lower() not in ("1", "true", "yes"):
        return jsonify({"error": "Synthetic scenarios are disabled"}), 403
    data = json_object()
    scenario = data.get("scenario", "crash")
    
    if scenario == "flood":
        incident = inject_urban_flood()
    else:
        incident = inject_expressway_crash()
        
    socketio.emit("incident:new", incident, room="dispatchers")
    return jsonify({
        "status": "success",
        "scenario": scenario,
        "incident": incident
    }), 201


@app.route("/api/nearest-hospital", methods=["POST"])
def nearest_hospital():
    if not has_operator_token():
        return jsonify({"error": "Valid operator credentials required"}), 401
    data = json_object()
    civilian_lat = data.get("lat")
    civilian_lng = data.get("lng")
    incident_type = data.get("incident_type", "general")

    if civilian_lat is None or civilian_lng is None:
        return jsonify({"error": "Location coordinates required"}), 400
    civilian_lat, civilian_lng = valid_coordinates(civilian_lat, civilian_lng)

    # Seed data is advisory only. Facility readiness must be supplied by a verified feed.
    all_hospitals = [h for h in get_hospitals() if h.get("bed_status") not in {"unavailable", "closed"}]
    if incident_type == "trauma":
        candidates = [h for h in all_hospitals if h["capability"] == "trauma"]
        if not candidates:
            candidates = all_hospitals
    else:
        candidates = all_hospitals
    if not candidates:
        return jsonify({"error": "No eligible hospital records are available"}), 503

    results = []
    for hospital in candidates:
        route_data = get_route(
            start_lng=civilian_lng,
            start_lat=civilian_lat,
            end_lng=hospital["lng"],
            end_lat=hospital["lat"]
        )
        if route_data:
            results.append({
                "hospital": hospital,
                "distance_km": round(route_data["distance"] / 1000, 2),
                "duration_mins": round(route_data["duration"] / 60, 1),
                "geometry": route_data["geometry"]
            })

    if not results:
        # Fallback straight-line calculation if ORS API key is missing or offline
        for hospital in candidates:
            # Approximate Euclidean distance in degrees to km (~111km per deg)
            approx_km = round(((hospital["lat"] - civilian_lat)**2 + (hospital["lng"] - civilian_lng)**2)**0.5 * 111, 2)
            approx_mins = round(approx_km / 40 * 60, 1) # Assumed 40 km/h city speed
            results.append({
                "hospital": hospital,
                "distance_km": approx_km,
                "duration_mins": approx_mins,
                "geometry": None
            })

    results.sort(key=lambda x: x["duration_mins"])
    
    # Evaluate via Golden Hour Survival Optimization Model
    survival_eval = optimize_trauma_routing(
        hospital_candidates=results,
        incident_type=incident_type,
        rsi_score=data.get("rsi_score", 4.0)
    )

    recommended = next((r["hospital"] for r in results if r["hospital"]["name"] == survival_eval["recommended_hospital"]), None)
    probability = float(str(survival_eval["predicted_survival_probability"]).rstrip("%")) / 100
    return jsonify({
        "recommended_hospital": recommended,
        "capability": survival_eval["recommended_facility_tier"],
        "distance_km": survival_eval["optimal_distance_km"],
        "duration_mins": survival_eval["optimal_duration_mins"],
        "geometry": survival_eval["geometry"],
        "predicted_survival_probability": probability,
        "survival_utility_score": survival_eval["survival_utility_score"],
        "clinical_tradeoff_active": survival_eval["clinical_tradeoff_active"],
        "clinical_justification": survival_eval["clinical_justification"],
        "all_options": results
    })


# --- Decision Intelligence & Predictive Modeling REST Endpoints ---

@app.route("/api/analysis/severity", methods=["POST"])
def severity_analysis_api():
    """Computes ResQ Severity Index (1.0-5.0) and clinical START triage."""
    data = json_object()
    result = calculate_rsi(
        unresponsive=data.get("unresponsive", False),
        severe_hemorrhage=data.get("severe_hemorrhage", False),
        airway_compromise=data.get("airway_compromise", False),
        entrapment=data.get("entrapment", False),
        casualties_count=data.get("casualties_count", 1),
        scene_hazards=data.get("scene_hazards", []),
        all_deceased=data.get("all_deceased", False)
    )
    return jsonify(result)


@app.route("/api/analysis/flood-risk", methods=["GET"])
def flood_risk_api():
    """Fulfills IEEE Hydro-Meteorological Inundation & Impassability modeling sub-problem."""
    rain_rate = request.args.get("rain_rate", type=float)
    if rain_rate is None:
        weather = get_weather_for_coords(lat=6.4474, lng=7.5098)
        rain_rate = weather.get("precipitation_mm", 0.0)
    basin_filter = request.args.get("basin")
    result = evaluate_basin_flood_risk(rain_rate_mm_hr=rain_rate, basin_filter=basin_filter)
    return jsonify(result)


@app.route("/api/analysis/flood-geojson", methods=["GET"])
def flood_geojson_api():
    """Returns GeoJSON FeatureCollection of flood danger zones for GIS map rendering."""
    rain_rate = request.args.get("rain_rate", type=float)
    if rain_rate is None:
        weather = get_weather_for_coords(lat=6.4474, lng=7.5098)
        rain_rate = weather.get("precipitation_mm", 0.0)
    geojson_data = get_flood_hazard_geojson(rain_rate_mm_hr=rain_rate)
    return jsonify(geojson_data)


@app.route("/api/analysis/corridor-risk", methods=["GET"])
def corridor_risk_api():
    """Evaluates dynamic CRI_t across FRSC blackspots along arterial corridors."""
    rain_rate = request.args.get("rain_rate", type=float)
    if rain_rate is None:
        weather = get_weather_for_coords(lat=6.4474, lng=7.5098)
        rain_rate = weather.get("precipitation_mm", 0.0)
    result = evaluate_all_corridors(rain_rate_mm_hr=rain_rate)
    return jsonify(result)


@app.route("/api/analysis/golden-hour", methods=["POST"])
def golden_hour_analysis_api():
    """Evaluates exponential survival decay curves and capability trade-offs for hospital options."""
    data = json_object()
    candidates = data.get("candidates", [])
    incident_type = data.get("incident_type", "trauma")
    rsi_score = data.get("rsi_score", 4.0)
    result = optimize_trauma_routing(
        hospital_candidates=candidates,
        incident_type=incident_type,
        rsi_score=rsi_score
    )
    return jsonify(result)


@app.route("/api/responder-eta", methods=["POST"])
def responder_eta():
    data = json_object()
    responder_lat = data.get("responder_lat")
    responder_lng = data.get("responder_lng")
    incident_lat = data.get("incident_lat")
    incident_lng = data.get("incident_lng")

    if any(value is None for value in (responder_lat, responder_lng, incident_lat, incident_lng)):
        return jsonify({"error": "All coordinates required"}), 400
    responder_lat, responder_lng = valid_coordinates(responder_lat, responder_lng)
    incident_lat, incident_lng = valid_coordinates(incident_lat, incident_lng)

    route_data = get_route(
        start_lng=responder_lng,
        start_lat=responder_lat,
        end_lng=incident_lng,
        end_lat=incident_lat
    )

    if not route_data:
        # Fallback estimation if ORS is offline
        approx_km = round(((incident_lat - responder_lat)**2 + (incident_lng - responder_lng)**2)**0.5 * 111, 2)
        approx_mins = round(approx_km / 45 * 60, 1)
        return jsonify({
            "eta_mins": approx_mins,
            "distance_km": approx_km,
            "geometry": None
        })

    return jsonify({
        "eta_mins": round(route_data["duration"] / 60, 1),
        "distance_km": round(route_data["distance"] / 1000, 2),
        "geometry": route_data["geometry"]
    })


# --- Multimodal AI & Civilian Emergency Triage Endpoints (Track B) ---

@app.route("/api/civilian/chat", methods=["POST"])
def civilian_chat_api():
    """
    Ingests bystander text or voice transcript, extracts structured clinical
    telemetry via Gemini 2.0 Flash / local fallback, computes RSI triage score,
    creates/updates an incident in the database, and emits real-time WebSocket events.
    """
    data = json_object()
    message = (data.get("message") or "").strip()
    lat = data.get("lat")
    lng = data.get("lng")
    incident_uuid = data.get("incident_uuid")
    photo_b64 = data.get("photo_b64")
    history = data.get("history") or []
    if not isinstance(history, list) or len(history) > 8:
        raise ValueError("history must contain at most eight message objects")
    if len(message) > 4000:
        raise ValueError("message exceeds the 4,000 character limit")
    eta_seconds = data.get("eta_seconds")
    if eta_seconds is not None:
        try:
            eta_seconds = int(eta_seconds)
        except (ValueError, TypeError):
            eta_seconds = None

    if not message and not photo_b64:
        return jsonify({"error": "Message or photo required"}), 400

    # One bounded AI request per user turn.
    extraction = extract_telemetry_and_guidance(
        bystander_text=message,
        scene_photo_base64=photo_b64,
        history=history,
        eta_seconds=eta_seconds
    )

    # 2. Algorithmic RSI Triage Scoring
    triage = calculate_rsi(
        unresponsive=extraction["unresponsive"],
        severe_hemorrhage=extraction["severe_hemorrhage"],
        airway_compromise=extraction["airway_compromise"],
        entrapment=extraction["entrapment"],
        casualties_count=extraction["casualties_count"],
        scene_hazards=extraction["scene_hazards"]
    )

    # 3. Incident Lifecycle Binding
    is_new = False
    incident = None
    if incident_uuid:
        incident = get_incident_by_uuid(incident_uuid)

    if not incident:
        is_new = True
        incident_uuid = incident_uuid or f"INC-CIV-{uuid.uuid4().hex[:6].upper()}"
        trauma_str = ", ".join(extraction["suspected_trauma"]) or "Medical Emergency"
        incident_type = "urban_flood" if "flood_water" in extraction["scene_hazards"] else "road_traffic_accident"
        # Resolve descriptive Nigerian landmark from coordinates
        resolved_geo = resolve_landmark(lat=lat, lng=lng)
        loc_name = data.get("location_name")
        if not loc_name or loc_name in ("Civilian Telemetry Point", "Enugu"):
            loc_name = resolved_geo.get("location_name", "Enugu Urban Corridor")

        if lat is not None and lng is not None:
            lat, lng = valid_coordinates(lat, lng)
        incident_data = {
            "incident_uuid": incident_uuid,
            "title": f"Bystander SOS: {trauma_str}",
            "type": incident_type,
            "status": "reported",
            "severity_level": triage["priority_label"],
            "severity_score": triage["rsi_score"],
            "escalation_status": "steady",
            "lat": lat or 6.4474,
            "lng": lng or 7.5098,
            "location_name": loc_name,
            "casualties_count": extraction["casualties_count"],
            "trapped_count": 1 if extraction["entrapment"] else 0
        }
        incident = create_incident(incident_data)
    else:
        # Update existing incident with newly reported casualties or hazards
        new_score = max(float(incident["severity_score"] or 1.0), triage["rsi_score"])
        new_casualties = extraction.get("casualties_count") or incident.get("casualties_count") or 1
        new_level = triage["priority_label"] if triage["rsi_score"] >= float(incident["severity_score"] or 1.0) else incident["severity_level"]
        update_data = {
            "severity_score": new_score,
            "severity_level": new_level,
            "casualties_count": int(new_casualties)
        }
        if lat is not None and lng is not None:
            lat, lng = valid_coordinates(lat, lng)
            update_data["lat"] = lat
            update_data["lng"] = lng
            if not incident.get("location_name") or incident.get("location_name") in ("Civilian Telemetry Point", "Enugu"):
                geo_update = resolve_landmark(lat=lat, lng=lng)
                update_data["location_name"] = geo_update.get("location_name")
        incident = update_incident(incident_uuid, update_data)

    # 4. Audit Trail Updates
    if message:
        add_incident_update(
            incident_uuid=incident_uuid,
            source="civilian",
            update_type="chat",
            content=message
        )

    triage_log = f"ResQ Triage [{triage['triage_tier']} | RSI {triage['rsi_score']}]: {'; '.join(extraction['first_aid_steps'][:2])}"
    add_incident_update(
        incident_uuid=incident_uuid,
        source="ai_system",
        update_type="triage",
        content=triage_log,
        metadata={
            "rsi": triage["rsi_score"],
            "tier": triage["triage_tier"],
            "unit": triage["recommended_unit"],
            "hazards": extraction["scene_hazards"],
            "clinical_synthesis": extraction.get("clinical_synthesis", "")
        }
    )

    # 5. Scene Hazards Registration
    for h in extraction["scene_hazards"]:
        add_scene_hazard(
            incident_uuid=incident_uuid,
            hazard_type=h,
            severity="high" if h in ("fuel_leak", "vehicle_fire", "live_wire") else "moderate",
            description=f"Hazard detected from bystander message: {h.replace('_', ' ')}"
        )

    # 6. Real-time WebSocket Dispatch Broadcast
    socket_payload = dict(incident)
    socketio.emit("incident:new" if is_new else "incident:update", socket_payload, room="dispatchers")

    chat_payload = {
        "incident_uuid": incident_uuid,
        "civilian_message": message,
        "ai_instruction": extraction.get("reassurance_message") or (extraction["first_aid_steps"][0] if extraction.get("first_aid_steps") else ""),
        "first_aid_steps": extraction.get("first_aid_steps", []),
        "casualties_count": int(extraction.get("casualties_count") or incident.get("casualties_count") or 1),
        "rsi_score": triage.get("rsi_score"),
        "triage_tier": triage.get("triage_tier"),
        "scene_hazards": extraction.get("scene_hazards", []),
        "timestamp": time.time()
    }
    socketio.emit("incident:chat_turn", chat_payload, room="dispatchers")
    socketio.emit("incident:chat_turn", chat_payload, room="responders")
    socketio.emit("incident:chat_turn", chat_payload, room=f"incident_{incident_uuid}")

    return jsonify({
        "status": "success",
        "incident_uuid": incident_uuid,
        "is_new": is_new,
        "extraction": extraction,
        "triage": triage,
        "first_aid_steps": extraction["first_aid_steps"],
        "reassurance_message": extraction["reassurance_message"],
        "clinical_synthesis": extraction.get("clinical_synthesis", ""),
        "assessment_questions": extraction.get("assessment_questions", []),
        "red_flags": extraction.get("red_flags", [])
    })


@app.route("/api/civilian/upload-photo", methods=["POST"])
def civilian_upload_photo_api():
    """
    Ingests scene photo, runs Gemini Vision hazard analysis, logs hazard in database,
    and alerts dispatchers. Strictly adheres to non-diagnostic boundary.
    """
    incident_uuid = request.form.get("incident_uuid")
    photo_file = request.files.get("photo")
    
    if not photo_file:
        # Check if base64 in JSON
        data = request.get_json() or {}
        b64 = data.get("photo_b64")
        incident_uuid = incident_uuid or data.get("incident_uuid")
        if b64:
            photo_bytes = base64.b64decode(b64)
            mime_type = data.get("mime_type", "image/jpeg")
        else:
            return jsonify({"error": "No photo provided"}), 400
    else:
        photo_bytes = photo_file.read()
        mime_type = photo_file.mimetype or "image/jpeg"

    if len(photo_bytes) > app.config["MAX_CONTENT_LENGTH"]:
        return jsonify({"error": "Upload exceeds the 5 MB limit"}), 413
    if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
        return jsonify({"error": "Only JPEG, PNG, and WebP images are accepted"}), 400

    vision_result = analyze_scene_photo(photo_bytes=photo_bytes, mime_type=mime_type)

    # Bind hazard to incident if active
    if incident_uuid:
        if not get_incident_by_uuid(incident_uuid):
            return jsonify({"error": "Incident not found"}), 404
        for h in vision_result.get("hazards_detected", []):
            add_scene_hazard(
                incident_uuid=incident_uuid,
                hazard_type=h,
                severity=vision_result.get("hazard_severity", "high"),
                description=vision_result.get("responder_safety_advisory")
            )
        socketio.emit("hazard:flagged", {
            "incident_uuid": incident_uuid,
            "vision_result": vision_result
        }, room="dispatchers")

    return jsonify({
        "status": "success",
        "incident_uuid": incident_uuid,
        "vision_result": vision_result
    })


def get_route(start_lng, start_lat, end_lng, end_lat):
    if not ORS_API_KEY:
        return None

    url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "coordinates": [
            [start_lng, start_lat],
            [end_lng, end_lat]
        ]
    }

    try:
        response = requests.post(url, json=body, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        feature = data["features"][0]
        summary = feature["properties"]["segments"][0]
        return {
            "distance": summary["distance"],
            "duration": summary["duration"],
            "geometry": feature["geometry"]
        }
    except Exception as e:
        print(f"ORS API error: {e}")
        return None


@app.route("/health")
def health_check():
    try:
        conn = get_db_connection(); conn.close()
    except Exception:
        return jsonify({"status": "unhealthy", "service": "ResQ Emergency Intelligence"}), 503
    return jsonify({
        "status": "healthy",
        "service": "ResQ Emergency Intelligence",
        "version": "2026.2",
        "database": "mysql" if USING_MYSQL else "sqlite-development-only"
    }), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true")
    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=debug,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )
