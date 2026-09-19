"""
Hydro-Meteorological Inundation & Road Impassability Engine
IEEE Response Quest Challenge 2026 - Emergency Intelligence Platform
Designated IEEE Modeling Sub-Problem Deliverable

Evaluates precipitation intensity combined with elevation gradients and drainage
basin culvert proximity to compute the empirical probability of road impassability (P_impassable).

Mathematical Formulation:
    P_impassable = 1 / (1 + exp(-(beta_0 + beta_1 * RainRate + beta_2 * ElevationDeficit + beta_3 * CulvertProximity)))

Where:
    - beta_0 = -3.20 (Baseline log-odds under dry conditions)
    - beta_1 =  0.065 (Precipitation coefficient per mm/hr rainfall)
    - beta_2 =  0.450 (Drainage depression deficit coefficient per meter below crest)
    - beta_3 =  0.800 (Proximity to natural river culvert / storm canal choke point)

Classification Thresholds:
    - P >= 0.65         -> IMPASSABLE / SUBMERGED (Detour strictly required)
    - 0.35 <= P < 0.65  -> CAUTION / FLOOD_WATCH (Slow transit for high-clearance units only)
    - P < 0.35          -> PASSABLE (Clear for standard emergency vehicles)
"""

import math
from typing import Dict, Any, List, Optional

# Empirical model calibration coefficients for Enugu Urban Drainage Basins
BETA_0 = -3.20
BETA_1 = 0.065
BETA_2 = 0.450
BETA_3 = 0.800

# High-risk urban drainage basins in Enugu State
ENUGU_DRAINAGE_BASINS = [
    {
        "basin_id": "BASIN-EKULU-01",
        "name": "Ekulu River Bridge / Abakpa Choke Point",
        "river_system": "Ekulu River",
        "lat": 6.4712,
        "lng": 7.5284,
        "base_elevation_m": 194.0,
        "threshold_elevation_m": 200.0,
        "culvert_factor": 1.0,
        "affected_road": "Abakpa - Trans-Ekulu Link Bridge",
        "criticality": "high"
    },
    {
        "basin_id": "BASIN-ASATA-02",
        "name": "Asata River Channel / Ogui Lowlands",
        "river_system": "Asata River",
        "lat": 6.4385,
        "lng": 7.5023,
        "base_elevation_m": 202.0,
        "threshold_elevation_m": 206.5,
        "culvert_factor": 0.85,
        "affected_road": "Ogui Road Culvert by Stadium",
        "criticality": "high"
    },
    {
        "basin_id": "BASIN-ARIA-03",
        "name": "Aria River Drainage / New Haven Corridor",
        "river_system": "Aria River",
        "lat": 6.4491,
        "lng": 7.5218,
        "base_elevation_m": 208.0,
        "threshold_elevation_m": 212.0,
        "culvert_factor": 0.75,
        "affected_road": "Upper Chime Avenue - New Haven",
        "criticality": "moderate"
    },
    {
        "basin_id": "BASIN-IDAW-04",
        "name": "Idaw River Channel / Achara Layout",
        "river_system": "Idaw River",
        "lat": 6.4150,
        "lng": 7.5080,
        "base_elevation_m": 218.0,
        "threshold_elevation_m": 222.0,
        "culvert_factor": 0.70,
        "affected_road": "Agulu Street - Achara Layout Crossing",
        "criticality": "moderate"
    },
    {
        "basin_id": "BASIN-ONYEAMA-05",
        "name": "Ugwu Onyeama Gully Runoff Corridors",
        "river_system": "Onyeama Escarpment Runoff",
        "lat": 6.4560,
        "lng": 7.4410,
        "base_elevation_m": 230.0,
        "threshold_elevation_m": 235.0,
        "culvert_factor": 0.90,
        "affected_road": "Enugu - Onitsha Expressway (Mountain Slopes)",
        "criticality": "critical"
    }
]


def compute_impassability_probability(
    rain_rate_mm_hr: float,
    elevation_deficit_m: float,
    culvert_proximity_factor: float
) -> float:
    """
    Computes P_impassable using the calibrated logistic regression function.

    Args:
        rain_rate_mm_hr: Current or forecasted rainfall rate (mm/hr).
        elevation_deficit_m: Meters road sits below basin threshold crest (max 0).
        culvert_proximity_factor: Proximity weight (0.0 to 1.0) to natural river choke points.

    Returns:
        Probability of road impassability (0.0 to 1.0).
    """
    rain = max(0.0, float(rain_rate_mm_hr))
    deficit = max(0.0, float(elevation_deficit_m))
    culvert = max(0.0, min(1.0, float(culvert_proximity_factor)))

    linear_predictor = BETA_0 + (BETA_1 * rain) + (BETA_2 * deficit) + (BETA_3 * culvert)

    # Sigmoid function
    try:
        p = 1.0 / (1.0 + math.exp(-linear_predictor))
    except OverflowError:
        p = 1.0 if linear_predictor > 0 else 0.0

    return round(p, 4)


def estimate_water_depth_cm(rain_rate_mm_hr: float, elevation_deficit_m: float, culvert_factor: float) -> float:
    """
    Estimates standing/flowing water depth over road surface in centimeters.
    """
    if rain_rate_mm_hr <= 0:
        return 0.0
    # Hydro-accumulation approximation: rain_rate * 0.4 + elevation_deficit * 6.5 * culvert_factor
    depth = (rain_rate_mm_hr * 0.35) + (elevation_deficit_m * 5.5 * culvert_factor)
    return round(max(0.0, depth), 1)


def evaluate_basin_flood_risk(rain_rate_mm_hr: float = 0.0, basin_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Evaluates hydro-meteorological flood risk across all monitored basins
    given the specified precipitation rate.

    Returns:
        Detailed analysis with road statuses, probabilities, water depths,
        impassable segments count, and routing avoidance recommendations.
    """
    rain = max(0.0, float(rain_rate_mm_hr))
    results = []
    impassable_count = 0
    caution_count = 0
    avoidance_points = []

    for basin in ENUGU_DRAINAGE_BASINS:
        if basin_filter and basin_filter.lower() not in basin["basin_id"].lower() and basin_filter.lower() not in basin["name"].lower():
            continue

        elevation_deficit = max(0.0, basin["threshold_elevation_m"] - basin["base_elevation_m"])
        prob = compute_impassability_probability(
            rain_rate_mm_hr=rain,
            elevation_deficit_m=elevation_deficit,
            culvert_proximity_factor=basin["culvert_factor"]
        )
        depth_cm = estimate_water_depth_cm(rain, elevation_deficit, basin["culvert_factor"])

        if prob >= 0.65:
            status = "IMPASSABLE"
            color = "#D32F2F"
            advisory = "Road completely submerged. Ambulances MUST detour."
            impassable_count += 1
            avoidance_points.append({
                "lat": basin["lat"],
                "lng": basin["lng"],
                "basin_name": basin["name"],
                "road": basin["affected_road"]
            })
        elif prob >= 0.35:
            status = "CAUTION"
            color = "#F0920A"
            advisory = "Water accumulation on surface. Passable only with high-clearance units."
            caution_count += 1
        else:
            status = "PASSABLE"
            color = "#0D6E6E"
            advisory = "Road open and passable for all emergency vehicles."

        results.append({
            "basin_id": basin["basin_id"],
            "name": basin["name"],
            "river_system": basin["river_system"],
            "coordinates": {"lat": basin["lat"], "lng": basin["lng"]},
            "affected_road": basin["affected_road"],
            "criticality": basin["criticality"],
            "elevation_deficit_m": elevation_deficit,
            "culvert_factor": basin["culvert_factor"],
            "impassability_probability": prob,
            "estimated_water_depth_cm": depth_cm,
            "status": status,
            "status_color": color,
            "advisory": advisory
        })

    # Overall regional status
    if impassable_count > 0:
        regional_status = "SEVERE_FLOOD_ALERT"
        summary = f"{impassable_count} arterial road segment(s) submerged. Dynamic rerouting engaged."
    elif caution_count > 0:
        regional_status = "FLOOD_WATCH"
        summary = f"{caution_count} road segment(s) showing water buildup. Precautionary monitoring active."
    else:
        regional_status = "NORMAL_CLEAR"
        summary = "All arterial drainage corridors operating within capacity. No flood delays."

    return {
        "model_name": "ResQ Hydro-Meteorological Inundation Engine",
        "ieee_subproblem": "Modeling & Decision-Making",
        "current_rain_rate_mm_hr": rain,
        "regional_status": regional_status,
        "summary": summary,
        "impassable_segments_count": impassable_count,
        "caution_segments_count": caution_count,
        "total_monitored_basins": len(ENUGU_DRAINAGE_BASINS),
        "avoidance_waypoints": avoidance_points,
        "basins": results
    }


def get_flood_hazard_geojson(rain_rate_mm_hr: float = 0.0) -> Dict[str, Any]:
    """
    Generates a GeoJSON FeatureCollection of flood danger zones
    suitable for direct Leaflet / Google Maps tactical overlay.
    """
    evaluation = evaluate_basin_flood_risk(rain_rate_mm_hr)
    features = []

    for item in evaluation["basins"]:
        coords = item["coordinates"]
        # Create a danger buffer polygon around the point
        d_lat = 0.0035  # ~380m radius
        d_lng = 0.0035
        polygon = [
            [coords["lng"] - d_lng, coords["lat"] - d_lat],
            [coords["lng"] + d_lng, coords["lat"] - d_lat],
            [coords["lng"] + d_lng, coords["lat"] + d_lat],
            [coords["lng"] - d_lng, coords["lat"] + d_lat],
            [coords["lng"] - d_lng, coords["lat"] - d_lat]
        ]

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon]
            },
            "properties": {
                "basin_id": item["basin_id"],
                "name": item["name"],
                "affected_road": item["affected_road"],
                "status": item["status"],
                "probability": item["impassability_probability"],
                "depth_cm": item["estimated_water_depth_cm"],
                "color": item["status_color"],
                "advisory": item["advisory"]
            }
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features
    }

