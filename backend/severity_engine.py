"""
ResQ Severity Index (RSI) Engine
IEEE Response Quest Challenge 2026 - Emergency Intelligence Platform

Mathematically formulated deterministic bystander triage engine based on the
Simple Triage and Rapid Treatment (START) and Advanced Trauma Life Support (ATLS)
clinical frameworks.

Mathematical Formulation:
    RSI = min(5.0, 1.0 + w1*x_unresponsive + w2*x_hemorrhage + w3*x_airway
                       + w4*x_entrapment + 0.2*max(0, victims - 1) + H_scene)

Where:
    - Base = 1.0
    - w1 = 2.0 (x_unresponsive: patient unresponsive or altered mental status)
    - w2 = 1.5 (x_hemorrhage: active uncontrolled external arterial/venous bleeding)
    - w3 = 1.5 (x_airway: compromised respiratory rate, stridor, or obstructed airway)
    - w4 = 1.0 (x_entrapment: physical vehicular or structural entrapment)
    - Victim scaling = 0.2 per additional victim above 1
    - H_scene = +0.5 if hazardous scene condition present (fire, fuel leak, live wire, collapse)

Triage Classification:
    - RSI >= 4.0        -> RED (Immediate / Critical)
    - 2.5 <= RSI < 4.0  -> YELLOW (Delayed / Urgent)
    - RSI < 2.5         -> GREEN (Minor / Walking Wounded)
    - All pulseless/dead-> BLACK (Expectant / Deceased)
"""

from typing import Dict, Any, List, Optional


def calculate_rsi(
    unresponsive: bool = False,
    severe_hemorrhage: bool = False,
    airway_compromise: bool = False,
    entrapment: bool = False,
    casualties_count: int = 1,
    scene_hazards: Optional[List[str]] = None,
    all_deceased: bool = False
) -> Dict[str, Any]:
    """
    Computes the ResQ Severity Index (1.0 - 5.0) and determines the clinical START
    triage category, priority tier, recommended emergency unit, and rationale.

    Args:
        unresponsive: Victim is unresponsive or cannot follow simple commands.
        severe_hemorrhage: Massive or spurting external bleeding.
        airway_compromise: Breathing rate > 30/min, agonal breathing, or obstruction.
        entrapment: Casualty is physically pinned or trapped in wreckage.
        casualties_count: Total number of victims reported at the scene.
        scene_hazards: List of detected environmental/structural hazards.
        all_deceased: Irreversible death or non-survivable injury confirmed.

    Returns:
        Dict containing rsi_score, triage_tier, priority_label, color_code,
        recommended_unit, clinical_rationale, and first_aid_priority.
    """
    if all_deceased:
        return {
            "rsi_score": 5.0,
            "triage_tier": "BLACK",
            "priority_label": "expectant",
            "color_code": "#1A1A1A",
            "recommended_unit": "Coroner / Incident Command Unit",
            "clinical_rationale": ["Confirmed irreversible trauma or pulseless apnea without response"],
            "first_aid_priority": "Scene safety preservation; avoid bystander hazard exposure",
            "requires_als": False,
            "breakdown": {
                "base": 1.0,
                "unresponsive": 0.0,
                "hemorrhage": 0.0,
                "airway": 0.0,
                "entrapment": 0.0,
                "victim_scaling": 0.0,
                "scene_hazard_bonus": 0.0,
                "raw_total": 5.0
            }
        }

    # Factor weights
    w_unresponsive = 2.0 if unresponsive else 0.0
    w_hemorrhage = 1.5 if severe_hemorrhage else 0.0
    w_airway = 1.5 if airway_compromise else 0.0
    w_entrapment = 1.0 if entrapment else 0.0

    # Victim count scaling: 0.2 per additional victim beyond 1
    v_count = max(1, int(casualties_count or 1))
    victim_scaling = round(0.2 * max(0, v_count - 1), 2)

    # Scene hazards modifier: +0.5 if critical hazards detected
    critical_hazard_types = {
        "fire", "vehicle_fire", "fuel_leak", "fuel_spill",
        "live_wire", "power_line", "structural_collapse", "toxic_gas"
    }
    hazards = scene_hazards or []
    has_critical_hazard = any(
        h.lower().strip() in critical_hazard_types or
        any(ch in h.lower() for ch in ["fire", "fuel", "wire", "collapse", "gas"])
        for h in hazards
    )
    h_scene = 0.5 if has_critical_hazard else 0.0

    # Core deterministic formula
    base_score = 1.0
    raw_total = base_score + w_unresponsive + w_hemorrhage + w_airway + w_entrapment + victim_scaling + h_scene
    final_rsi = round(min(5.0, max(1.0, raw_total)), 1)

    # Clinical rationale generation
    rationale: List[str] = []
    if unresponsive:
        rationale.append("Unresponsive / Altered mental status (+2.0)")
    if severe_hemorrhage:
        rationale.append("Massive / Active uncontrolled bleeding (+1.5)")
    if airway_compromise:
        rationale.append("Compromised airway or respiratory distress (+1.5)")
    if entrapment:
        rationale.append("Mechanical vehicle / structural entrapment (+1.0)")
    if v_count > 1:
        rationale.append(f"Multiple casualties: {v_count} victims (+{victim_scaling:.1f})")
    if has_critical_hazard:
        rationale.append(f"Environmental scene hazard active: {', '.join(hazards)} (+0.5)")

    if not rationale:
        rationale.append("Conscious, breathing adequately, ambulatory bystander (+0.0)")

    # Triage Tier classification
    if final_rsi >= 4.0:
        triage_tier = "RED"
        priority_label = "critical"
        color_code = "#D32F2F"
        recommended_unit = "ALS Ambulance (Advanced Life Support) + Extrication Unit" if entrapment else "ALS Ambulance (Advanced Life Support)"
        first_aid_priority = "Immediate airway positioning (head-tilt chin-lift) and firm direct arterial pressure"
        requires_als = True
    elif final_rsi >= 2.5:
        triage_tier = "YELLOW"
        priority_label = "urgent"
        color_code = "#F0920A"
        recommended_unit = "BLS Ambulance (Basic Life Support) with Trauma Stabilization"
        first_aid_priority = "Limb immobilization, sterile wound dressing, and shock prevention (keep warm)"
        requires_als = False
    else:
        triage_tier = "GREEN"
        priority_label = "minor"
        color_code = "#0D6E6E"
        recommended_unit = "First Responder Patrol / Basic First Aid Van"
        first_aid_priority = "Clean minor abrasions, guide walking wounded to safe zone away from traffic"
        requires_als = False

    return {
        "rsi_score": final_rsi,
        "triage_tier": triage_tier,
        "priority_label": priority_label,
        "color_code": color_code,
        "recommended_unit": recommended_unit,
        "clinical_rationale": rationale,
        "first_aid_priority": first_aid_priority,
        "requires_als": requires_als,
        "breakdown": {
            "base": base_score,
            "unresponsive": w_unresponsive,
            "hemorrhage": w_hemorrhage,
            "airway": w_airway,
            "entrapment": w_entrapment,
            "victim_scaling": victim_scaling,
            "scene_hazard_bonus": h_scene,
            "raw_total": round(raw_total, 2)
        }
    }

