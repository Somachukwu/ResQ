import unittest
import json
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from backend.gemini_triage import extract_telemetry_and_guidance, _fallback_heuristic_parser
from backend.database import get_incident_by_uuid, get_scene_hazards, get_incident_updates, update_responder_status


class TestScenarioAudit(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        update_responder_status("AMB-01", "idle", None)

    def test_scenario_ai_clinical_demographics_and_hazards(self):
        """Scenario 1 & 5: AI asks important questions (victim gender, where injury is) and detects hazards."""
        # Test heuristic and triage guidance on trauma report
        prompt = "A bike hit a pedestrian near Holy Ghost roundabout. Fuel is leaking on the road and there is bleeding from deep wounds."
        telemetry = _fallback_heuristic_parser(prompt)
        
        # Hazard check
        self.assertIn("fuel_leak", telemetry.get("scene_hazards", []))
        
        # Check clinical guidance has first aid steps
        self.assertGreater(len(telemetry.get("first_aid_steps", [])), 0)
        
        # Check that follow up questions ask about victim details (gender, exact injury location, breathing)
        questions = [q.get("question", "") for q in telemetry.get("assessment_questions", [])]
        combined_questions = " ".join(questions).lower()
        self.assertTrue(
            "male" in combined_questions or "female" in combined_questions or "gender" in combined_questions or "man" in combined_questions or "woman" in combined_questions,
            f"Expected demographic inquiry in: {questions}"
        )
        self.assertTrue(
            "where" in combined_questions or "injury" in combined_questions or "wound" in combined_questions or "bleeding" in combined_questions,
            f"Expected anatomical injury location inquiry in: {questions}"
        )

    def test_scenario_civilian_report_to_command_hazards_and_acknowledgment(self):
        """Scenarios 2, 4, 6: Civilian SOS report -> Incident created -> Hazards in Command -> Acknowledgment starts ETA."""
        # 1. Civilian sends SOS trauma report
        report_payload = {
            "message": "Serious crash at Holy Ghost roundabout! Fuel leaking everywhere, rider is bleeding heavily.",
            "lat": 6.4485,
            "lng": 7.5140,
            "place": "Holy Ghost roundabout, Enugu"
        }
        res = self.client.post("/api/civilian/chat", json=report_payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        incident_uuid = data.get("incident_uuid")
        self.assertTrue(incident_uuid, "Incident UUID must be generated")

        # 2. Command views incident details via /api/incidents/<uuid>
        inc_res = self.client.get(f"/api/incidents/{incident_uuid}")
        self.assertEqual(inc_res.status_code, 200)
        inc_data = inc_res.get_json()
        
        # Verify Command hazard alerts are populated
        raw_hazards = inc_data.get("hazards", [])
        hazard_types = [h.get("hazard_type", str(h)) if isinstance(h, dict) else str(h) for h in raw_hazards]
        self.assertGreater(len(hazard_types), 0, "Incident hazards must be visible to Command")
        self.assertTrue(any("fuel" in h.lower() for h in hazard_types), f"Expected fuel hazard in {hazard_types}")

        # Verify incident in /api/incidents list also contains hazards
        all_res = self.client.get("/api/incidents")
        self.assertEqual(all_res.status_code, 200)
        all_incidents = all_res.get_json()
        target = next((i for i in all_incidents if i.get("incident_uuid") == incident_uuid or i.get("uuid") == incident_uuid or i.get("id") == incident_uuid), None)
        self.assertIsNotNone(target, f"Incident {incident_uuid} should be in incident list: {[i.get('incident_uuid') for i in all_incidents]}")
        self.assertGreater(len(target.get("hazards", [])), 0, "Hazards must be present in queue list")

        # 2.5 Dispatcher assigns responder AMB-01
        assign_res = self.client.post("/api/responder/assign", json={
            "incident_uuid": incident_uuid,
            "unit_code": "AMB-01"
        })
        self.assertEqual(assign_res.status_code, 200, f"Assignment failed: {assign_res.get_json()}")

        # 3. Test crew acknowledgment triggers ETA start
        ack_res = self.client.post(f"/api/incidents/{incident_uuid}/acknowledge", json={"unit_code": "AMB-01"})
        self.assertEqual(ack_res.status_code, 200)
        ack_data = ack_res.get_json()
        self.assertEqual(ack_data.get("status"), "acknowledged")
        self.assertIn("eta_minutes", ack_data)

    def test_scenario_command_dispatch_tactical_comms_channel(self):
        """Scenario: Dedicated Command & Dispatch interaction space."""
        # First create incident
        res = self.client.post("/api/civilian/chat", json={
            "message": "Traffic accident on Abakaliki road.",
            "lat": 6.4520,
            "lng": 7.5190
        })
        incident_uuid = res.get_json().get("incident_uuid")

        # Command issues tactical route directive to crew
        route_payload = {
            "incident_uuid": incident_uuid,
            "new_route": "Bypass flooded culvert via Presidential Road",
            "note": "Bypass flooded culvert via Presidential Road"
        }
        rc_res = self.client.post("/api/responder/route-change", json=route_payload)
        self.assertEqual(rc_res.status_code, 200)

        # Responder crew sends tactical reply back to Command
        reply_payload = {
            "incident_uuid": incident_uuid,
            "unit_code": "AMB-01",
            "message": "Detour underway. ETA adjusted by 2 minutes."
        }
        msg_res = self.client.post("/api/responder/message", json=reply_payload)
        self.assertEqual(msg_res.status_code, 200)

        # Verify tactical comms recorded in incident updates
        updates = get_incident_updates(incident_uuid)
        update_contents = [u["content"] for u in updates]
        self.assertTrue(any("Presidential Road" in c for c in update_contents), "Route directive must be recorded in updates")
        self.assertTrue(any("Detour underway" in c for c in update_contents), "Responder reply must be recorded in updates")

    def test_scenario_voice_bridge_lifecycle(self):
        """Scenario: Tactical Voice Call Bridge lifecycle across roles."""
        res = self.client.post("/api/civilian/chat", json={"message": "Emergency at Polo Park mall."})
        incident_uuid = res.get_json().get("incident_uuid")

        # Civilian/Dispatcher voice call start
        cb_start = self.client.post(f"/api/incidents/{incident_uuid}/call-bridge", json={"action": "start"})
        self.assertEqual(cb_start.status_code, 200)
        self.assertTrue(cb_start.get_json().get("active"))

        # Responder connect
        cb_resp = self.client.post(f"/api/incidents/{incident_uuid}/call-bridge", json={"action": "responder_connect"})
        self.assertEqual(cb_resp.status_code, 200)

        # Disconnect / end call
        cb_end = self.client.post(f"/api/incidents/{incident_uuid}/call-bridge", json={"action": "end"})
        self.assertEqual(cb_end.status_code, 200)
        self.assertFalse(cb_end.get_json().get("active"))


if __name__ == "__main__":
    unittest.main()
