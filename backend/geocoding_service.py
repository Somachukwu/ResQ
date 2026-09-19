"""
Nigerian Spatial Landmark Resolution & Offline Geocoding Engine
IEEE Response Quest Challenge 2026

Resolves raw bystander GPS coordinates into human-readable, tactical Nigerian landmarks,
bus stops, junctions, and highway markers to accelerate responder dispatch.
"""

import math
from typing import Dict, Any, Optional, Tuple, List
import requests

# Curated reference points across major corridors (Enugu urban, arterial expressways, Lagos)
NIGERIAN_LANDMARKS = [
    # Enugu Urban & Surrounds
    {"name": "Holy Ghost Cathedral / Old Park, Ogui Road, Enugu", "lat": 6.4422, "lng": 7.4981, "type": "transit_hub"},
    {"name": "Otigba Junction, Independence Layout, Enugu", "lat": 6.4474, "lng": 7.5098, "type": "major_junction"},
    {"name": "New Haven Junction / Chime Avenue, Enugu", "lat": 6.4495, "lng": 7.5255, "type": "junction"},
    {"name": "ESUT Teaching Hospital Gate, Parklane, Enugu", "lat": 6.4541, "lng": 7.5248, "type": "hospital"},
    {"name": "National Orthopaedic Hospital Junction, Abakaliki Road, Enugu", "lat": 6.4418, "lng": 7.4985, "type": "hospital"},
    {"name": "University of Nigeria Teaching Hospital (UNTH), Ituku-Ozalla", "lat": 6.3125, "lng": 7.4764, "type": "hospital"},
    {"name": "82 Division Army Barracks Gate, Abakaliki Expressway, Enugu", "lat": 6.4682, "lng": 7.5385, "type": "landmark"},
    {"name": "9th Mile Corner Junction, Ngwo, Enugu", "lat": 6.4320, "lng": 7.4100, "type": "corridor_node"},
    {"name": "Ugwu Onyeama Descent, Enugu-Onitsha Expressway", "lat": 6.4398, "lng": 7.3785, "type": "hazard_blackspot"},
    {"name": "Akanu Ibiam International Airport Entrance, Emene, Enugu", "lat": 6.4741, "lng": 7.5620, "type": "airport"},
    {"name": "Gariki Market Main Gate, Awkunanaw, Enugu", "lat": 6.3985, "lng": 7.5042, "type": "market"},
    {"name": "Ogbete Main Market / Railway Crossing, Enugu", "lat": 6.4380, "lng": 7.4930, "type": "market"},
    {"name": "New Market Roundabout, Coal Camp, Enugu", "lat": 6.4312, "lng": 7.4789, "type": "roundabout"},
    {"name": "Four Corners Junction, Enugu-Port Harcourt Expressway, Ozalla", "lat": 6.3450, "lng": 7.4910, "type": "corridor_node"},
    {"name": "Afor Awkunanaw Junction, Agbani Road, Enugu", "lat": 6.4150, "lng": 7.5080, "type": "junction"},
    {"name": "Ugwuoba Cattle Market / Oji River Boundary, Km 42 Expressway", "lat": 6.2750, "lng": 7.2180, "type": "highway_marker"},
    {"name": "Amansea Border Bridge, Enugu-Onitsha Expressway", "lat": 6.2420, "lng": 7.1250, "type": "bridge"},

    # Lagos Key Tactical Hubs & Blackspots
    {"name": "Third Mainland Bridge (Adekunle Inward Interchange), Lagos", "lat": 6.4950, "lng": 3.3920, "type": "bridge"},
    {"name": "Berger Bus Stop, Lagos-Ibadan Expressway", "lat": 6.6450, "lng": 3.3670, "type": "corridor_node"},
    {"name": "Ojota Interchange / Ikorodu Road, Lagos", "lat": 6.5820, "lng": 3.3850, "type": "major_junction"},
    {"name": "Lagos University Teaching Hospital (LUTH), Idi-Araba", "lat": 6.5240, "lng": 3.3560, "type": "hospital"},
    {"name": "Lagos State University Teaching Hospital (LASUTH), Ikeja", "lat": 6.5950, "lng": 3.3480, "type": "hospital"},
    {"name": "Lekki Toll Gate / Admiralty Way Junction, Lagos", "lat": 6.4420, "lng": 3.4750, "type": "corridor_node"},
]


def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two GPS coordinates in kilometers."""
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def resolve_landmark(lat: Optional[float], lng: Optional[float]) -> Dict[str, Any]:
    """
    Resolves coordinate pair to closest human-readable landmark.
    Uses zero-latency local spatial database first (<5km proximity threshold),
    with optional fallback to OpenStreetMap Nominatim when available.
    """
    if lat is None or lng is None:
        return {
            "location_name": "Location Coordinates Pending",
            "distance_km": None,
            "landmark_type": "unknown",
            "source": "unresolved"
        }

    # 1. Local spatial index search
    closest_landmark = None
    min_distance = float("inf")

    for landmark in NIGERIAN_LANDMARKS:
        dist = _haversine_distance_km(lat, lng, landmark["lat"], landmark["lng"])
        if dist < min_distance:
            min_distance = dist
            closest_landmark = landmark

    # If within 4.5 km of a known critical hub or corridor marker
    if closest_landmark and min_distance <= 4.5:
        dist_str = f"{round(min_distance * 1000)}m" if min_distance < 1.0 else f"{round(min_distance, 1)}km"
        prefix = "Near" if min_distance <= 0.4 else f"Approx. {dist_str} from"
        return {
            "location_name": f"{prefix} {closest_landmark['name']}",
            "reference_landmark": closest_landmark["name"],
            "distance_km": round(min_distance, 2),
            "landmark_type": closest_landmark["type"],
            "source": "local_spatial_db"
        }

    # 2. OpenStreetMap reverse geocoding fallback (with short timeout)
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}&zoom=16&addressdetails=1"
        headers = {"User-Agent": "ResQ-Emergency-Systems-Intelligence/2026.02 (contact: emergency@resq.ng)"}
        resp = requests.get(url, headers=headers, timeout=2.5)
        if resp.status_code == 200:
            data = resp.json()
            disp_name = data.get("display_name")
            addr = data.get("address", {})
            road = addr.get("road") or addr.get("suburb") or addr.get("neighbourhood") or ""
            city = addr.get("city") or addr.get("town") or addr.get("state") or "Nigeria"
            if road:
                formatted = f"{road}, {city}"
            elif disp_name:
                formatted = ", ".join(disp_name.split(",")[:3])
            else:
                formatted = f"Coordinates {round(lat, 4)}, {round(lng, 4)}"

            return {
                "location_name": formatted,
                "reference_landmark": road or city,
                "distance_km": 0.0,
                "landmark_type": "osm_reverse_geocoded",
                "source": "nominatim"
            }
    except Exception:
        pass

    # 3. Fallback coordinate formatting if distant from index and offline
    if closest_landmark:
        return {
            "location_name": f"{round(min_distance, 1)}km from {closest_landmark['name']}",
            "reference_landmark": closest_landmark["name"],
            "distance_km": round(min_distance, 2),
            "landmark_type": closest_landmark["type"],
            "source": "local_spatial_db_coarse"
        }

    return {
        "location_name": f"GPS Point: {round(lat, 4)}° N, {round(lng, 4)}° E",
        "distance_km": None,
        "landmark_type": "raw_coordinates",
        "source": "fallback"
    }

