from flask import Flask, render_template, request, jsonify, send_from_directory
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(
    __name__,
    template_folder="frontend",
    static_folder="frontend/static",
    static_url_path="/static"
)


@app.route("/resources/<path:filename>")
@app.route("/Resources/<path:filename>")
def serve_resources(filename):
    return send_from_directory(os.path.join(app.root_path, "frontend", "Resources"), filename)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "frontend"), "favicon.ico", mimetype="image/vnd.microsoft.icon")

ORS_API_KEY = os.getenv("ORS_API_KEY")

HOSPITALS = [
    {
        "name": "Enugu State University Teaching Hospital",
        "capability": "trauma",
        "emergency": True,
        "lat": 6.4541,
        "lng": 7.5248
    },
    {
        "name": "National Orthopaedic Hospital Enugu",
        "capability": "orthopaedic",
        "emergency": True,
        "lat": 6.4418,
        "lng": 7.4985
    },
    {
        "name": "University of Nigeria Teaching Hospital",
        "capability": "general",
        "emergency": True,
        "lat": 6.4698,
        "lng": 7.5597
    },
    {
        "name": "Park Lane General Hospital",
        "capability": "general",
        "emergency": True,
        "lat": 6.4622,
        "lng": 7.5106
    }
]


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


@app.route("/api/nearest-hospital", methods=["POST"])
def nearest_hospital():
    data = request.get_json()
    civilian_lat = data.get("lat")
    civilian_lng = data.get("lng")
    incident_type = data.get("incident_type", "general")

    if not civilian_lat or not civilian_lng:
        return jsonify({"error": "Location coordinates required"}), 400

    if incident_type == "trauma":
        candidates = [h for h in HOSPITALS if h["capability"] == "trauma"]
        if not candidates:
            candidates = HOSPITALS
    else:
        candidates = HOSPITALS

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
        return jsonify({"error": "Could not calculate routes"}), 500

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
    data = request.get_json()
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
        return jsonify({"error": "Could not calculate route"}), 500

    return jsonify({
        "eta_mins": round(route_data["duration"] / 60, 1),
        "distance_km": round(route_data["distance"] / 1000, 2),
        "geometry": route_data["geometry"]
    })


def get_route(start_lng, start_lat, end_lng, end_lat):
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
    app.run(host="0.0.0.0", port=5000, debug=True)