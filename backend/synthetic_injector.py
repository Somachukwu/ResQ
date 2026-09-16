import uuid
from datetime import datetime
from .database import (
    create_incident, 
    add_incident_update, 
    add_scene_hazard, 
    update_responder_status,
    get_incident_by_uuid
)

def inject_expressway_crash():
    incident_uuid = f"INC-CRASH-{uuid.uuid4().hex[:6].upper()}"
    
    # 1. Create incident at 9th Mile corner, Enugu-Onitsha Expressway
    incident_data = {
        "incident_uuid": incident_uuid,
        "title": "Severe Two-Vehicle Collision with Trapped Casualty",
        "type": "road_traffic_accident",
        "status": "reported",
        "severity_level": "critical",
        "severity_score": 4.6,
        "escalation_status": "steady",
        "lat": 6.4385,
        "lng": 7.4220,
        "location_name": "Enugu-Onitsha Expressway (Near 9th Mile Corner)",
        "casualties_count": 2,
        "trapped_count": 1,
        "assigned_responder_id": None,
        "recommended_hospital_id": 1 # ESUT Teaching Hospital (trauma)
    }
    incident = create_incident(incident_data)
    
    # 2. Add civilian dialogue and AI guidance log
    add_incident_update(
        incident_uuid=incident_uuid,
        source="civilian",
        update_type="chat",
        content="Two cars just crashed heavily into each other. Driver in the saloon car is not moving, bleeding from head. Passenger in the bus has broken leg."
    )
    add_incident_update(
        incident_uuid=incident_uuid,
        source="ai_system",
        update_type="triage",
        content="ResQ AI Triage Protocol Activated: Victim 1 unresponsive with suspected Traumatic Brain Injury (START: IMMEDIATE / RED). Victim 2 conscious with lower extremity fracture (START: DELAYED / YELLOW). Advising bystander to open airway without neck movement.",
        metadata={"triage_level": "critical", "start_code": "RED", "victims": 2}
    )
    add_incident_update(
        incident_uuid=incident_uuid,
        source="civilian",
        update_type="chat",
        content="I have tilted his chin and checked his breathing. He is breathing shallowly. Fuel is dripping from the engine."
    )
    
    # 3. Add scene hazard
    add_scene_hazard(
        incident_uuid=incident_uuid,
        hazard_type="fuel_leak",
        severity="high",
        description="Active petrol leakage from crumpled engine bay. Flammable vapour risk. Bystanders advised to keep 25m distance."
    )
    
    return get_incident_by_uuid(incident_uuid)


def inject_urban_flood():
    incident_uuid = f"INC-FLOOD-{uuid.uuid4().hex[:6].upper()}"
    
    incident_data = {
        "incident_uuid": incident_uuid,
        "title": "Rapid Urban Flash Flood & Stranded Commuter",
        "type": "urban_flood",
        "status": "reported",
        "severity_level": "urgent",
        "severity_score": 3.8,
        "escalation_status": "escalating",
        "lat": 6.4520,
        "lng": 7.5180,
        "location_name": "Chime Avenue / New Haven River Channel, Enugu",
        "casualties_count": 1,
        "trapped_count": 1,
        "assigned_responder_id": None,
        "recommended_hospital_id": 4 # Park Lane
    }
    incident = create_incident(incident_data)
    
    add_incident_update(
        incident_uuid=incident_uuid,
        source="civilian",
        update_type="chat",
        content="The culvert overflowed rapidly. Water is at waist height. One elderly woman is clinging to a gate post and cannot cross the current."
    )
    add_incident_update(
        incident_uuid=incident_uuid,
        source="ai_system",
        update_type="triage",
        content="Flood Hazard Protocol: Fast-flowing floodwaters (~0.8m depth). Immediate risk of drowning or being swept into open drainage. Bystanders instructed NOT to enter fast current without rope/anchor.",
        metadata={"triage_level": "urgent", "start_code": "YELLOW", "victims": 1}
    )
    
    add_scene_hazard(
        incident_uuid=incident_uuid,
        hazard_type="flood_water",
        severity="urgent",
        description="Deep fast-moving runoff across Chime Avenue. Open drainage trench submerged."
    )
    
    return get_incident_by_uuid(incident_uuid)

