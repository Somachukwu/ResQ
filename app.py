from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO
import requests
import os
from dotenv import load_dotenv

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
    add_incident_update
)
from backend.socket_events import register_socket_events
from backend.synthetic_injector import inject_expressway_crash, inject_urban_flood
from backend.weather_service import get_weather_for_coords

load_dotenv()

app = Flask(
    __name__,
    template_folder="frontend",
    static_folder="frontend/static",
    static_url_path="/static"
)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "resq-emergency-intelligence-secret-key-2026")

# Initialize real-time SocketIO bus
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
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
    nearest = results[0]

    return jsonify({
        "recommended_hospital": nearest["hospital"]["name"],
        "capability": nearest["hospital"]["capability"],
        "distance_km": nearest["distance_km"],
        "duration_mins": nearest["duration_mins"],
        "geometry": nearest["geometry"],
        "all_options": results
    })


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


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)