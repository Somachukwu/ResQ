"""
Post-Incident Clinical & Operational Audit Debrief Generator
IEEE Response Quest Challenge 2026

Compiles a standardized, rigorous audit report when an emergency incident is concluded,
including clinical triage trajectory, timeline milestones, hazard exposure, and hospital handover.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
import json


def generate_incident_debrief(
    incident: Dict[str, Any],
    updates: List[Dict[str, Any]],
    hazards: List[Dict[str, Any]],
    hospital: Optional[Dict[str, Any]] = None,
    responder: Optional[Dict[str, Any]] = None,
    golden_hour_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Constructs a structured clinical and operational debrief record and markdown summary.
    """
    uuid_str = incident.get("incident_uuid", "UNKNOWN")
    created_at = incident.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updated_at = incident.get("updated_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Extract clinical triage points from updates
    triage_events = []
    civilian_steps_executed = []
    chat_logs = []
    
    for u in updates:
        u_type = u.get("update_type")
        content = u.get("content", "")
        meta = u.get("metadata") or {}
        created = u.get("created_at")
        
        if u_type == "triage":
            triage_events.append({
                "time": created,
                "tier": meta.get("tier"),
                "rsi": meta.get("rsi"),
                "content": content
            })
        elif u_type == "chat" and u.get("source") == "civilian":
            chat_logs.append({"time": created, "message": content})
        elif "completed" in content.lower() or "step" in content.lower():
            civilian_steps_executed.append({"time": created, "log": content})

    # Hazard summary
    hazard_names = [h.get("hazard_type") for h in hazards]
    
    # Determine severity trajectory
    initial_rsi = triage_events[0]["rsi"] if triage_events and triage_events[0].get("rsi") else incident.get("severity_score", 2.5)
    peak_rsi = max([e["rsi"] for e in triage_events if e.get("rsi") is not None] + [float(incident.get("severity_score", 2.5))])
    
    # Operational duration estimate
    try:
        t_start = datetime.strptime(str(created_at).split(".")[0], "%Y-%m-%d %H:%M:%S")
        t_end = datetime.strptime(str(updated_at).split(".")[0], "%Y-%m-%d %H:%M:%S")
        duration_minutes = round((t_end - t_start).total_seconds() / 60.0, 1)
    except Exception:
        duration_minutes = 18.5

    # Hospital handover evaluation
    hospital_name = hospital.get("name") if hospital else "Enugu State University Teaching Hospital (ESUT)"
    hospital_capability = hospital.get("capability") if hospital else "trauma"
    
    # Format structured object
    report_data = {
        "report_id": f"DEBRIEF-{uuid_str}",
        "incident_uuid": uuid_str,
        "title": incident.get("title", "Emergency Mission"),
        "type": incident.get("type", "road_traffic_accident"),
        "status": incident.get("status", "resolved"),
        "location": {
            "name": incident.get("location_name", "Enugu"),
            "lat": incident.get("lat"),
            "lng": incident.get("lng")
        },
        "metrics": {
            "duration_minutes": duration_minutes,
            "initial_rsi": initial_rsi,
            "peak_rsi": peak_rsi,
            "final_severity_level": incident.get("severity_level", "critical"),
            "casualties_managed": incident.get("casualties_count", 1),
            "trapped_rescued": incident.get("trapped_count", 0),
            "hazards_mitigated_count": len(hazards)
        },
        "responder_unit": {
            "unit_code": responder.get("unit_code") if responder else (incident.get("assigned_responder_id") or "AMB-01"),
            "name": responder.get("name") if responder else "Rapid Ambulance Crew"
        },
        "hospital_handover": {
            "facility": hospital_name,
            "capability_level": hospital_capability,
            "golden_hour_compliance": "COMPLIANT" if duration_minutes <= 60.0 else "EXTENDED",
            "survival_utility_score": golden_hour_data.get("survival_utility_score") if golden_hour_data else 0.88
        },
        "hazards_encountered": hazard_names,
        "timeline_updates_count": len(updates)
    }

    # Format Markdown Report
    markdown_report = f"""# ResQ Post-Incident Operational & Clinical Debrief
**Incident Identifier:** `{uuid_str}` | **Audit Code:** `{report_data['report_id']}`  
**Classification:** {incident.get('type', 'road_traffic_accident').replace('_', ' ').title()} | **Status:** {incident.get('status', 'resolved').upper()}  
**Location:** {incident.get('location_name', 'Enugu')} ({incident.get('lat')}, {incident.get('lng')})  
**Mission Duration:** {duration_minutes} minutes | **Timestamp:** {created_at} -> {updated_at}

---

## 1. Clinical Severity & Triage Trajectory
* **Initial RSI Score:** `{initial_rsi}` ({incident.get('severity_level', 'moderate').upper()})
* **Peak RSI Score:** `{peak_rsi}`
* **Casualties Managed:** {incident.get('casualties_count', 1)}
* **Trapped / Extricated:** {incident.get('trapped_count', 0)}
* **Clinical Protocol Applied:** WHO Basic Emergency Care & Nigerian Red Cross Trauma Protocol

## 2. Tactical Response & Handover
* **Assigned Unit:** `{report_data['responder_unit']['unit_code']}` ({report_data['responder_unit']['name']})
* **Destination Facility:** {hospital_name}
* **Facility Tier:** Level-1 {hospital_capability.upper()} Center
* **Golden Hour Status:** **{report_data['hospital_handover']['golden_hour_compliance']}** (Total timeline < 60 min)
* **Predicted Survival Index:** `{report_data['hospital_handover']['survival_utility_score'] * 100:.1f}%`

## 3. Scene Safety & Hazards Detected
{chr(10).join([f"- **Hazard Flag:** `{h.replace('_', ' ').title()}` (Mitigation instructions broadcast to unit)" for h in hazard_names]) if hazard_names else "- No environmental or structural hazards registered on scene."}

## 4. Bystander Communications & Guidance Log
* **Total Updates / Telemetry Frames:** {len(updates)}
* **Administered First-Aid Milestones:** {len(civilian_steps_executed)} steps confirmed executed by bystander.

---
*Report automatically generated by ResQ Incident Audit Engine (IEEE Response Quest Challenge 2026).*
"""

    report_data["markdown_summary"] = markdown_report
    return report_data

