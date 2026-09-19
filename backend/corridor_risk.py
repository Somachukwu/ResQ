"""
Corridor Crash Risk Index (CRI_t) Engine
IEEE Response Quest Challenge 2026 - Emergency Intelligence Platform

Evaluates spatial clustering of Federal Road Safety Corps (FRSC) historical
collision blackspots combined with terrain slope, real-time rainfall, and traffic
congestion to calculate dynamic corridor crash risk.

Mathematical Formulation:
    CRI_t = alpha * KDE_blackspot + beta * Grade_slope + gamma * Rain_factor + delta * Congestion_deficit

Where:
    - alpha = 0.40 (Historical FRSC collision kernel density, normalized 0-1)
    - beta  = 0.25 (Topographical slope gradient penalty, normalized 0-1)
    - gamma = 0.20 (Precipitation road slickness factor, normalized 0-1)
    - delta = 0.15 (Traffic congestion speed deficit ratio: (v_free - v_traffic) / v_free)

Output Scale:
    - CRI_t in [0.0, 100.0]
    - CRI_t >= 75.0       -> CRITICAL_RISK (Deploy proactive FRSC highway patrol)
    - 50.0 <= CRI_t < 75.0-> ELEVATED_RISK (Issue speed advisory & ambulance standby)
    - CRI_t < 50.0        -> NOMINAL_RISK  (Routine patrol monitoring)
"""

from typing import Dict, Any, List, Optional

ALPHA = 0.40  # Historical blackspot density weight
BETA = 0.25   # Slope gradient weight
GAMMA = 0.20  # Rainfall slickness weight
DELTA = 0.15  # Congestion deficit weight

# Curated FRSC High-Fatality Blackspot Registry (Enugu State Corridors)
FRSC_CORRIDOR_BLACKSPOTS = [
    {
        "corridor_id": "COR-ONYEAMA-01",
        "name": "Ugwu Onyeama S-Bends & Escarpment Incline",
        "corridor_name": "Enugu - Onitsha Expressway",
        "lat": 6.4528,
        "lng": 7.4395,
        "historical_fatalities_annual": 48,
        "historical_crashes_annual": 112,
        "kde_density_score": 0.95,  # 0.0 - 1.0 (extreme spatial clustering)
        "slope_gradient_percent": 8.5,  # Heavy downhill mountain grade
        "freeflow_speed_kmh": 80.0,
        "recommended_patrol_station": "FRSC RS9.1 Sector Command / 9th Mile Unit",
        "primary_cause": "Brake failure on descent & blind double-apex curves"
    },
    {
        "corridor_id": "COR-9THMILE-02",
        "name": "9th Mile Corner Commercial Intersection",
        "corridor_name": "Enugu - Makurdi / Onitsha Junction",
        "lat": 6.4255,
        "lng": 7.4098,
        "historical_fatalities_annual": 26,
        "historical_crashes_annual": 89,
        "kde_density_score": 0.82,
        "slope_gradient_percent": 4.0,
        "freeflow_speed_kmh": 60.0,
        "recommended_patrol_station": "9th Mile Inter-State Patrol Base",
        "primary_cause": "Heavy articulated truck bottleneck & pedestrian spillover"
    },
    {
        "corridor_id": "COR-OTIGBA-03",
        "name": "Otigba Roundabout / Ogui Arterial Junction",
        "corridor_name": "Presidential Road - Chime Ave Arterial",
        "lat": 6.4426,
        "lng": 7.5065,
        "historical_fatalities_annual": 12,
        "historical_crashes_annual": 65,
        "kde_density_score": 0.60,
        "slope_gradient_percent": 1.5,
        "freeflow_speed_kmh": 50.0,
        "recommended_patrol_station": "Enugu Central Metro Traffic Command",
        "primary_cause": "High-velocity lateral collisions & yellow bus lane violations"
    },
    {
        "corridor_id": "COR-HOLYGHOST-04",
        "name": "Holy Ghost / Old Park Rail Crossing",
        "corridor_name": "Okpara Avenue Corridor",
        "lat": 6.4350,
        "lng": 7.4942,
        "historical_fatalities_annual": 18,
        "historical_crashes_annual": 74,
        "kde_density_score": 0.70,
        "slope_gradient_percent": 2.0,
        "freeflow_speed_kmh": 40.0,
        "recommended_patrol_station": "Holy Ghost FRSC Post",
        "primary_cause": "Extreme pedestrian density & commercial transit congestion"
    },
    {
        "corridor_id": "COR-PORTHARCOURT-05",
        "name": "Four Corners / Port Harcourt Expressway Flyover",
        "corridor_name": "Enugu - Port Harcourt Expressway",
        "lat": 6.3680,
        "lng": 7.5210,
        "historical_fatalities_annual": 34,
        "historical_crashes_annual": 91,
        "kde_density_score": 0.88,
        "slope_gradient_percent": 5.0,
        "freeflow_speed_kmh": 90.0,
        "recommended_patrol_station": "Agbogugu / Ozalla Patrol Outpost",
        "primary_cause": "Excessive speed on bypass & unlit stationary vehicle hazards"
    }
]


def calculate_corridor_risk_index(
    kde_density: float,
    slope_gradient_pct: float,
    rain_rate_mm_hr: float = 0.0,
    current_speed_kmh: Optional[float] = None,
    freeflow_speed_kmh: float = 80.0
) -> Dict[str, Any]:
    """
    Computes dynamic CRI_t (0.0 to 100.0) for a given road corridor.

    Args:
        kde_density: Spatial kernel density of crashes (0.0 to 1.0).
        slope_gradient_pct: Road incline/descent grade percentage (e.g. 8.5%).
        rain_rate_mm_hr: Rainfall rate in mm/hr.
        current_speed_kmh: Real-time observed traffic speed.
        freeflow_speed_kmh: Uncongested freeflow design speed.
    """
    kde_norm = max(0.0, min(1.0, float(kde_density)))

    # Slope normalization: 0% -> 0.0, 10%+ -> 1.0
    slope_norm = max(0.0, min(1.0, float(slope_gradient_pct) / 10.0))

    # Rain normalization: 0 mm/hr -> 0.0, 50+ mm/hr -> 1.0
    rain_norm = max(0.0, min(1.0, float(rain_rate_mm_hr) / 50.0))

    # Traffic congestion deficit: (v_free - v_traffic) / v_free
    if current_speed_kmh is not None and freeflow_speed_kmh > 0:
        observed_speed = max(5.0, min(freeflow_speed_kmh, float(current_speed_kmh)))
        congestion_norm = max(0.0, min(1.0, (freeflow_speed_kmh - observed_speed) / freeflow_speed_kmh))
    else:
        # Default mild congestion
        congestion_norm = 0.20

    raw_cri = (
        (ALPHA * kde_norm) +
        (BETA * slope_norm) +
        (GAMMA * rain_norm) +
        (DELTA * congestion_norm)
    )

    cri_score = round(raw_cri * 100.0, 1)

    if cri_score >= 75.0:
        risk_level = "CRITICAL_RISK"
        color_code = "#D32F2F"
        action_advisory = "HIGH COLLISION PROBABILITY: Pre-position FRSC patrol unit and trauma ambulance."
    elif cri_score >= 50.0:
        risk_level = "ELEVATED_RISK"
        color_code = "#F0920A"
        action_advisory = "MODERATE COLLISION RISK: Broadcast speed restriction warning and maintain standby."
    else:
        risk_level = "NOMINAL_RISK"
        color_code = "#0D6E6E"
        action_advisory = "NORMAL OPERATING CONDITIONS: Routine continuous road safety surveillance."

    return {
        "cri_score": cri_score,
        "risk_level": risk_level,
        "color_code": color_code,
        "action_advisory": action_advisory,
        "component_weights": {
            "kde_blackspot_contrib": round(ALPHA * kde_norm * 100.0, 1),
            "slope_gradient_contrib": round(BETA * slope_norm * 100.0, 1),
            "rain_slickness_contrib": round(GAMMA * rain_norm * 100.0, 1),
            "congestion_contrib": round(DELTA * congestion_norm * 100.0, 1)
        }
    }


def evaluate_all_corridors(rain_rate_mm_hr: float = 0.0) -> Dict[str, Any]:
    """
    Evaluates dynamic CRI_t across all monitored FRSC arterial blackspots
    under current or simulated weather conditions.
    """
    corridors_output = []
    critical_corridors = []
    highest_risk = None

    for c in FRSC_CORRIDOR_BLACKSPOTS:
        # If rain is heavy, assume traffic speed drops by 35%
        speed_reduction = 0.65 if rain_rate_mm_hr > 25.0 else 0.85
        sim_speed = round(c["freeflow_speed_kmh"] * speed_reduction, 1)

        result = calculate_corridor_risk_index(
            kde_density=c["kde_density_score"],
            slope_gradient_pct=c["slope_gradient_percent"],
            rain_rate_mm_hr=rain_rate_mm_hr,
            current_speed_kmh=sim_speed,
            freeflow_speed_kmh=c["freeflow_speed_kmh"]
        )

        item = {
            "corridor_id": c["corridor_id"],
            "name": c["name"],
            "corridor_name": c["corridor_name"],
            "coordinates": {"lat": c["lat"], "lng": c["lng"]},
            "slope_gradient_percent": c["slope_gradient_percent"],
            "historical_crashes_annual": c["historical_crashes_annual"],
            "historical_fatalities_annual": c["historical_fatalities_annual"],
            "primary_cause": c["primary_cause"],
            "recommended_patrol_station": c["recommended_patrol_station"],
            "risk_analysis": result
        }
        corridors_output.append(item)

        if result["risk_level"] == "CRITICAL_RISK":
            critical_corridors.append(item)

        if highest_risk is None or result["cri_score"] > highest_risk["risk_analysis"]["cri_score"]:
            highest_risk = item

    # Sort descending by CRI score
    corridors_output.sort(key=lambda x: x["risk_analysis"]["cri_score"], reverse=True)

    return {
        "model_name": "ResQ Spatial Corridor Crash Risk Engine (CRI_t)",
        "frsc_integration": "Federal Road Safety Corps Historical Blackspot Registry",
        "rain_rate_mm_hr": rain_rate_mm_hr,
        "highest_risk_corridor": highest_risk["name"] if highest_risk else None,
        "critical_corridors_count": len(critical_corridors),
        "total_corridors_monitored": len(FRSC_CORRIDOR_BLACKSPOTS),
        "tactical_prepositioning_alerts": [
            {
                "corridor": c["name"],
                "cri_score": c["risk_analysis"]["cri_score"],
                "action": f"Idle patrol unit at {c['recommended_patrol_station']}"
            }
            for c in critical_corridors
        ],
        "corridors": corridors_output
    }

