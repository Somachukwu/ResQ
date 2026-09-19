"""
Golden Hour Survival Optimization Algorithm
IEEE Response Quest Challenge 2026 - Emergency Intelligence Platform

Evaluates non-linear exponential patient survival decay S(t) against facility
trauma capability C_h to validate routing to certified tertiary trauma centers
over closer, unequipped primary healthcare clinics.

Mathematical Formulation:
    S(t) = S_0 * exp(-lambda_h * t)
    SurvivalUtility(h) = S(t_h) * C_h(injury_type)

Where:
    - t_h: Transit time in minutes to hospital h
    - S_0: Initial post-incident salvageability (e.g. 0.95 for RSI >= 4.0)
    - lambda_tertiary  = 0.012 min^-1 (Tertiary Trauma Center: 24/7 OR, CT, Blood Bank)
    - lambda_secondary = 0.024 min^-1 (General Hospital: limited surgical ICU)
    - lambda_primary   = 0.045 min^-1 (Primary Clinic: non-surgical triage only)
    - C_h(trauma): Capability coefficient (Tertiary=1.0, Secondary=0.65, Primary=0.30)
"""

import math
from typing import Dict, Any, List, Optional

# Decay constants per minute
LAMBDA_TERTIARY = 0.012
LAMBDA_SECONDARY = 0.024
LAMBDA_PRIMARY = 0.045

# Capability coefficients by facility tier and incident classification
CAPABILITY_WEIGHTS = {
    "trauma": {
        "tertiary": 1.00,
        "secondary": 0.65,
        "primary": 0.30
    },
    "burns": {
        "tertiary": 0.95,
        "secondary": 0.50,
        "primary": 0.25
    },
    "orthopaedic": {
        "tertiary": 1.00,
        "secondary": 0.60,
        "primary": 0.25
    },
    "general": {
        "tertiary": 1.00,
        "secondary": 0.90,
        "primary": 0.75
    }
}


def get_hospital_tier(hospital: Dict[str, Any]) -> str:
    """
    Infers facility clinical capability tier from metadata and hospital name.
    """
    name = hospital.get("name", "").lower()
    capability = hospital.get("capability", "").lower()

    if "university" in name or "teaching" in name or "orthopaedic" in name or capability in ("trauma", "tertiary"):
        return "tertiary"
    elif "general" in name or capability in ("secondary", "surgical"):
        return "secondary"
    return "primary"


def compute_survival_probability(
    transit_mins: float,
    facility_tier: str = "tertiary",
    baseline_s0: float = 0.95
) -> float:
    """
    Computes S(t) = S_0 * exp(-lambda * t).

    Args:
        transit_mins: Travel duration in minutes.
        facility_tier: 'tertiary', 'secondary', or 'primary'.
        baseline_s0: Initial physiological salvageability (0.0 to 1.0).

    Returns:
        Predicted survival probability at definitive arrival time.
    """
    t = max(1.0, float(transit_mins))
    tier = facility_tier.lower()

    if tier == "tertiary":
        decay_rate = LAMBDA_TERTIARY
    elif tier == "secondary":
        decay_rate = LAMBDA_SECONDARY
    else:
        decay_rate = LAMBDA_PRIMARY

    prob = baseline_s0 * math.exp(-decay_rate * t)
    return round(max(0.01, min(1.0, prob)), 4)


def optimize_trauma_routing(
    hospital_candidates: List[Dict[str, Any]],
    incident_type: str = "trauma",
    rsi_score: float = 4.0
) -> Dict[str, Any]:
    """
    Ranks hospital options using the Golden Hour multi-criteria survival utility.

    Args:
        hospital_candidates: List of dicts each with:
            - 'hospital': dict with 'name', 'capability', 'lat', 'lng'
            - 'duration_mins': travel time in minutes
            - 'distance_km': travel distance in kilometers
            - 'geometry': optional route geometry
        incident_type: 'trauma', 'burns', 'orthopaedic', or 'general'
        rsi_score: ResQ Severity Index (1.0 - 5.0)

    Returns:
        Structured evaluation with recommended facility, survival trade-offs,
        and mathematical proof justifying the routing decision.
    """
    if not hospital_candidates:
        return {"error": "No hospital candidates provided"}

    # Severity-adjusted baseline salvageability
    if rsi_score >= 4.0:
        baseline_s0 = 0.92  # High mortality risk without intervention
    elif rsi_score >= 2.5:
        baseline_s0 = 0.96
    else:
        baseline_s0 = 0.99

    inc_type = incident_type.lower()
    weights_table = CAPABILITY_WEIGHTS.get(inc_type, CAPABILITY_WEIGHTS["general"])

    scored_facilities = []

    for item in hospital_candidates:
        hospital = item.get("hospital", item)
        duration_mins = float(item.get("duration_mins", 15.0))
        distance_km = float(item.get("distance_km", 10.0))
        geometry = item.get("geometry")

        tier = get_hospital_tier(hospital)
        c_factor = weights_table.get(tier, 0.70)
        survival_prob = compute_survival_probability(
            transit_mins=duration_mins,
            facility_tier=tier,
            baseline_s0=baseline_s0
        )

        # Survival utility incorporates the facility's clinical intervention efficacy
        utility_score = round(survival_prob * c_factor * 100.0, 1)

        scored_facilities.append({
            "hospital": hospital,
            "facility_tier": tier,
            "capability_factor": c_factor,
            "duration_mins": duration_mins,
            "distance_km": distance_km,
            "survival_probability": round(survival_prob * 100.0, 1),
            "survival_utility_score": utility_score,
            "geometry": geometry
        })

    # Sort descending by survival utility score
    scored_facilities.sort(key=lambda x: x["survival_utility_score"], reverse=True)
    optimal = scored_facilities[0]

    # Find the nearest facility by raw time to demonstrate the clinical trade-off
    closest_by_time = min(scored_facilities, key=lambda x: x["duration_mins"])

    is_tradeoff = optimal["hospital"]["name"] != closest_by_time["hospital"]["name"]
    tradeoff_explanation = ""

    if is_tradeoff:
        extra_mins = round(optimal["duration_mins"] - closest_by_time["duration_mins"], 1)
        utility_gain = round(optimal["survival_utility_score"] - closest_by_time["survival_utility_score"], 1)
        tradeoff_explanation = (
            f"Bypassing closer clinic '{closest_by_time['hospital']['name']}' (+{extra_mins} mins transit) "
            f"to definitive trauma center '{optimal['hospital']['name']}'. "
            f"Delivers +{utility_gain}% higher definitive survival utility by avoiding secondary inter-facility transfer delay."
        )
    else:
        tradeoff_explanation = (
            f"Optimal facility '{optimal['hospital']['name']}' is both the highest capability trauma center "
            f"and within rapid transit range ({optimal['duration_mins']} mins)."
        )

    return {
        "model_name": "ResQ Capability-Aware Golden Hour Survival Optimizer",
        "recommended_hospital": optimal["hospital"]["name"],
        "recommended_facility_tier": optimal["facility_tier"],
        "optimal_duration_mins": optimal["duration_mins"],
        "optimal_distance_km": optimal["distance_km"],
        "predicted_survival_probability": f"{optimal['survival_probability']}%",
        "survival_utility_score": optimal["survival_utility_score"],
        "geometry": optimal["geometry"],
        "clinical_tradeoff_active": is_tradeoff,
        "clinical_justification": tradeoff_explanation,
        "ranked_options": scored_facilities
    }

