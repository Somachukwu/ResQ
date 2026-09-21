import os
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

# Initialize real-time SocketIO bus
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
_orig_socketio_run = socketio.run
def _guarded_run(*args, **kwargs):
    kwargs.setdefault("allow_unsafe_werkzeug", True)
    return _orig_socketio_run(*args, **kwargs)
socketio.run = _guarded_run
register_socket_events(socketio)

# Initialize local database schema and seed data
init_db()


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
        data = request.get_json() or {}
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
    
    status = request.args.get("status")
    incidents = get_incidents(status=status)
    return jsonify(incidents)


@app.route("/api/incidents/<incident_uuid>", methods=["GET"])
def incident_detail_api(incident_uuid):
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


@app.route("/api/incidents/<incident_uuid>/debrief", methods=["GET"])
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
def assign_responder_api():
    """Assigns an emergency responder unit to an incident and broadcasts real-time telemetry."""
    data = request.get_json() or {}
    incident_uuid = data.get("incident_uuid")
    unit_code = data.get("unit_code")

    if not incident_uuid or not unit_code:
        return jsonify({"error": "incident_uuid and unit_code required"}), 400

    incident = get_incident_by_uuid(incident_uuid)
    responder = get_responder_by_code(unit_code)
    if not incident or not responder:
        return jsonify({"error": "Incident or Responder not found"}), 404

    # Update responder and incident statuses
    from backend.database import update_responder_status
    update_responder_status(unit_code, status="assigned", incident_id=incident_uuid)
    updated_inc = update_incident(incident_uuid, {
        "status": "dispatched",
        "assigned_responder_id": unit_code
    })

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
        "timestamp": incident["updated_at"]
    }
    socketio.emit("responder:assigned", payload, room="dispatchers")
    socketio.emit("responder:assigned", payload, room="responders")

    return jsonify({
        "status": "success",
        "incident": updated_inc,
        "responder": get_responder_by_code(unit_code)
    })


@app.route("/api/responder-telemetry", methods=["POST"])
def responder_telemetry_beacon_api():
    """Ingests periodic GPS beacon from active responder unit and emits live tracking event."""
    data = request.get_json() or {}
    unit_code = data.get("unit_code")
    lat = data.get("lat")
    lng = data.get("lng")
    heading = data.get("heading", 0.0)
    speed_kmh = data.get("speed_kmh", 0.0)

    if not unit_code or lat is None or lng is None:
        return jsonify({"error": "unit_code, lat, lng required"}), 400

    from backend.database import update_responder_telemetry
    update_responder_telemetry(unit_code, lat=lat, lng=lng, heading=heading, speed_kmh=speed_kmh)

    # Broadcast live pin update to dispatcher and responder GIS screens
    beacon_payload = {
        "unit_code": unit_code,
        "lat": lat,
        "lng": lng,
        "heading": heading,
        "speed_kmh": speed_kmh
    }
    socketio.emit("responder:beacon", beacon_payload, room="dispatchers")
    socketio.emit("responder:beacon", beacon_payload, room="responders")

    return jsonify({"status": "beacon_recorded", "data": beacon_payload})


@app.route("/api/responders", methods=["GET"])
def responders_api():
    responders = get_responders()
    return jsonify(responders)


@app.route("/api/hospitals", methods=["GET"])
def hospitals_api():
    capability = request.args.get("capability")
    hospitals = get_hospitals(capability=capability)
    return jsonify(hospitals)


@app.route("/api/weather", methods=["GET"])
def weather_api():
    lat = request.args.get("lat", type=float, default=6.4474)
    lng = request.args.get("lng", type=float, default=7.5098)
    region = request.args.get("region", default="community")
    weather_data = get_weather_for_coords(lat=lat, lng=lng, region_code=region)
    return jsonify(weather_data)


@app.route("/api/demo/inject", methods=["POST"])
def demo_inject_api():
    data = request.get_json() or {}
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
    data = request.get_json() or {}
    civilian_lat = data.get("lat")
    civilian_lng = data.get("lng")
    incident_type = data.get("incident_type", "general")

    if not civilian_lat or not civilian_lng:
        return jsonify({"error": "Location coordinates required"}), 400

    all_hospitals = get_hospitals()
    if incident_type == "trauma":
        candidates = [h for h in all_hospitals if h["capability"] == "trauma"]
        if not candidates:
            candidates = all_hospitals
    else:
        candidates = all_hospitals

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

    return jsonify({
        "recommended_hospital": survival_eval["recommended_hospital"],
        "capability": survival_eval["recommended_facility_tier"],
        "distance_km": survival_eval["optimal_distance_km"],
        "duration_mins": survival_eval["optimal_duration_mins"],
        "geometry": survival_eval["geometry"],
        "predicted_survival_probability": survival_eval["predicted_survival_probability"],
        "survival_utility_score": survival_eval["survival_utility_score"],
        "clinical_tradeoff_active": survival_eval["clinical_tradeoff_active"],
        "clinical_justification": survival_eval["clinical_justification"],
        "all_options": results
    })


# --- Decision Intelligence & Predictive Modeling REST Endpoints ---

@app.route("/api/analysis/severity", methods=["POST"])
def severity_analysis_api():
    """Computes ResQ Severity Index (1.0-5.0) and clinical START triage."""
    data = request.get_json() or {}
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
    data = request.get_json() or {}
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
    data = request.get_json() or {}
    responder_lat = data.get("responder_lat")
    responder_lng = data.get("responder_lng")
    incident_lat = data.get("incident_lat")
    incident_lng = data.get("incident_lng")

    if not all([responder_lat, responder_lng, incident_lat, incident_lng]):
        return jsonify({"error": "All coordinates required"}), 400

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
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    lat = data.get("lat")
    lng = data.get("lng")
    incident_uuid = data.get("incident_uuid")
    photo_b64 = data.get("photo_b64")
    history = data.get("history") or []
    eta_seconds = data.get("eta_seconds")
    if eta_seconds is not None:
        try:
            eta_seconds = int(eta_seconds)
        except (ValueError, TypeError):
            eta_seconds = None

    if not message and not photo_b64:
        return jsonify({"error": "Message or photo required"}), 400

    # 1. Multimodal AI Extraction (English + Nigerian Pidgin)
    extraction = extract_telemetry_and_guidance(bystander_text=message, scene_photo_base64=photo_b64)
    # 1. Multimodal AI Extraction (English + Nigerian Pidgin + Multi-turn context)
    extraction = extract_telemetry_and_guidance(bystander_text=message, scene_photo_base64=photo_b64, history=history)
    # 1. Multimodal AI Extraction (English + Nigerian Pidgin + Multi-turn context + ETA awareness)
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
        new_level = triage["priority_label"] if triage["rsi_score"] >= float(incident["severity_score"] or 1.0) else incident["severity_level"]
        update_data = {
            "severity_score": new_score,
            "severity_level": new_level,
            "casualties_count": max(int(incident["casualties_count"] or 1), extraction["casualties_count"])
        }
        if lat and lng:
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

    vision_result = analyze_scene_photo(photo_bytes=photo_bytes, mime_type=mime_type)

    # Bind hazard to incident if active
    if incident_uuid:
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
    return jsonify({
        "status": "healthy",
        "service": "ResQ Emergency Intelligence",
        "version": "2026.1"
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