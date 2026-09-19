import unittest
import json
import os
import sys
import io

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from backend.gemini_triage import (
    extract_telemetry_and_guidance,
    analyze_scene_photo,
    _fallback_heuristic_parser
)
from backend.database import get_incident_by_uuid, get_incident_updates, get_scene_hazards


class TestGeminiTriage(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()

    # --- 1. Natural Language & Pidgin Telemetry Extraction Tests ---

    def test_english_extraction(self):
        """Extracts structured telemetry from plain English emergency description."""
        text = "Two people in a crash. Driver is unresponsive with severe arterial bleeding and trapped inside the car. Fuel is leaking."
        res = _fallback_heuristic_parser(text)

        self.assertTrue(res["unresponsive"])
        self.assertTrue(res["severe_hemorrhage"])
        self.assertTrue(res["entrapment"])
        self.assertEqual(res["casualties_count"], 2)
        self.assertIn("fuel_leak", res["scene_hazards"])
        self.assertGreater(len(res["first_aid_steps"]), 0)
        # Verify direct pressure instruction
        self.assertTrue(any("cloth" in step.lower() or "pressure" in step.lower() for step in res["first_aid_steps"]))

    def test_nigerian_pidgin_extraction(self):
        """Correctly parses Nigerian Pidgin emergency idioms into structured data."""
        text = "Two people dey for road, driver no dey talk at all and blood dey rush well well. Petrol dey leak for floor."
        res = _fallback_heuristic_parser(text)

        self.assertTrue(res["unresponsive"])
        self.assertTrue(res["severe_hemorrhage"])
        self.assertEqual(res["casualties_count"], 2)
        self.assertIn("fuel_leak", res["scene_hazards"])
        # Verify clear English reassurance message is returned
        self.assertIn("Emergency responders", res["reassurance_message"])

    def test_airway_resuscitation_guidance(self):
        """Compromised airway triggers immediate head-tilt chin-lift guidance."""
        text = "The casualty is not breathing at all and unconscious."
        res = _fallback_heuristic_parser(text)

        self.assertTrue(res["unresponsive"])
        self.assertTrue(res["airway_compromise"])
        self.assertTrue(any("airway" in step.lower() or "compressions" in step.lower() for step in res["first_aid_steps"]))

    def test_strict_clinical_boundaries(self):
        """Confirms AI instructions never suggest prescription drugs or diagnosis."""
        text = "Patient has severe chest pain and broken arm."
        res = _fallback_heuristic_parser(text)

        all_steps = " ".join(res["first_aid_steps"]).lower()
        self.assertNotIn("aspirin", all_steps)
        self.assertNotIn("ibuprofen", all_steps)
        self.assertNotIn("diagnose", all_steps)
        self.assertNotIn("injection", all_steps)

    # --- 2. Vision Hazard Analysis Tests ---

    def test_photo_hazard_inspection(self):
        """Analyzes scene photo bytes and returns responder safety advisory."""
        dummy_image = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00"
        result = analyze_scene_photo(dummy_image, mime_type="image/jpeg")

        self.assertIn("hazards_detected", result)
        self.assertIn("responder_safety_advisory", result)

    # --- 3. REST API & Incident Lifecycle Integration Tests ---

    def test_civilian_chat_api_new_incident(self):
        """POST /api/civilian/chat creates incident with calculated RSI score and emits to dispatch."""
        payload = {
            "message": "Two casualties trapped in vehicle, one is unresponsive and bleeding heavily from head",
            "lat": 6.4528,
            "lng": 7.4395,
            "location_name": "Ugwu Onyeama Descent"
        }
        res = self.client.post("/api/civilian/chat", json=payload)
        self.assertEqual(res.status_code, 200)

        data = json.loads(res.data)
        self.assertTrue(data["is_new"])
        self.assertIn("INC-CIV-", data["incident_uuid"])
        self.assertGreaterEqual(data["triage"]["rsi_score"], 4.0)
        self.assertEqual(data["triage"]["triage_tier"], "RED")

        # Verify incident persisted in database
        db_inc = get_incident_by_uuid(data["incident_uuid"])
        self.assertIsNotNone(db_inc)
        self.assertEqual(db_inc["severity_level"], "critical")
        self.assertEqual(db_inc["casualties_count"], 2)

        # Verify updates logged
        updates = get_incident_updates(data["incident_uuid"])
        self.assertGreaterEqual(len(updates), 2)  # civilian chat + ai triage

    def test_civilian_chat_api_session_continuation(self):
        """Subsequent chat message updates the same incident rather than duplicating."""
        # 1. First message
        res1 = self.client.post("/api/civilian/chat", json={
            "message": "One victim on the floor unconscious",
            "lat": 6.4402,
            "lng": 7.4936
        })
        data1 = json.loads(res1.data)
        inc_uuid = data1["incident_uuid"]

        # 2. Second message
        res2 = self.client.post("/api/civilian/chat", json={
            "message": "Fuel is now leaking from the tank! Petrol everywhere!",
            "incident_uuid": inc_uuid
        })
        data2 = json.loads(res2.data)
        self.assertFalse(data2["is_new"])
        self.assertEqual(data2["incident_uuid"], inc_uuid)

        # Verify hazard was bound
        hazards = get_scene_hazards(inc_uuid)
        self.assertTrue(any(h["hazard_type"] == "fuel_leak" for h in hazards))

    def test_civilian_photo_upload_endpoint(self):
        """POST /api/civilian/upload-photo handles multipart upload and logs hazard."""
        dummy_file = (io.BytesIO(b"dummy image content"), "scene.jpg")
        res = self.client.post(
            "/api/civilian/upload-photo",
            data={"photo": dummy_file, "incident_uuid": "INC-TEST-001"},
            content_type="multipart/form-data"
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "success")
        self.assertIn("vision_result", data)

    def test_pwa_offline_assets_served(self):
        """Verifies manifest.json and sw.js are served with appropriate MIME types."""
        manifest_res = self.client.get("/manifest.json")
        self.assertEqual(manifest_res.status_code, 200)
        manifest_data = json.loads(manifest_res.data)
        self.assertEqual(manifest_data["short_name"], "ResQ")

        sw_res = self.client.get("/sw.js")
        self.assertEqual(sw_res.status_code, 200)
        self.assertIn("resq-offline", sw_res.data.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
