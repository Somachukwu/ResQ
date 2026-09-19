"""
Unit and Integration Tests for Nigerian Landmark Resolution and Debrief Generator
"""

import pytest
from backend.geocoding_service import resolve_landmark
from backend.debrief_generator import generate_incident_debrief


def test_resolve_landmark_enugu_exact():
    # Otigba Junction coordinates
    res = resolve_landmark(6.4474, 7.5098)
    assert "Otigba Junction" in res["location_name"]
    assert res["source"] == "local_spatial_db"
    assert res["distance_km"] < 0.5


def test_resolve_landmark_highway_marker():
    # Ugwuoba corridor marker
    res = resolve_landmark(6.2750, 7.2180)
    assert "Ugwuoba" in res["location_name"]
    assert res["landmark_type"] == "highway_marker"


def test_resolve_landmark_missing_coords():
    res = resolve_landmark(None, None)
    assert res["location_name"] == "Location Coordinates Pending"
    assert res["distance_km"] is None


def test_generate_incident_debrief():
    incident = {
        "incident_uuid": "INC-TEST-001",
        "title": "Bystander SOS: Head Trauma",
        "type": "road_traffic_accident",
        "status": "resolved",
        "severity_level": "critical",
        "severity_score": 4.5,
        "lat": 6.4474,
        "lng": 7.5098,
        "location_name": "Near Otigba Junction, Enugu",
        "casualties_count": 2,
        "trapped_count": 0,
        "assigned_responder_id": "AMB-01",
        "created_at": "2026-09-19 12:00:00",
        "updated_at": "2026-09-19 12:25:00"
    }
    updates = [
        {"update_type": "triage", "content": "Triage alert", "metadata": {"tier": "P1", "rsi": 4.5}, "created_at": "2026-09-19 12:02:00"},
        {"update_type": "chat", "source": "civilian", "content": "Driver is bleeding", "created_at": "2026-09-19 12:05:00"},
        {"update_type": "chat", "source": "civilian", "content": "Well done, step completed", "created_at": "2026-09-19 12:08:00"}
    ]
    hazards = [{"hazard_type": "fuel_leak", "description": "Leaking petrol"}]
    hospital = {"name": "ESUT Teaching Hospital", "capability": "trauma"}
    responder = {"unit_code": "AMB-01", "name": "Rapid Ambulance 01"}

    debrief = generate_incident_debrief(
        incident=incident,
        updates=updates,
        hazards=hazards,
        hospital=hospital,
        responder=responder
    )

    assert debrief["incident_uuid"] == "INC-TEST-001"
    assert debrief["metrics"]["peak_rsi"] == 4.5
    assert debrief["metrics"]["duration_minutes"] == 25.0
    assert "ESUT Teaching Hospital" in debrief["hospital_handover"]["facility"]
    assert "fuel_leak" in debrief["hazards_encountered"]
    assert "# ResQ Post-Incident Operational & Clinical Debrief" in debrief["markdown_summary"]

