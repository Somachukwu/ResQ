import unittest
import json
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, socketio
from backend.database import (
    init_db,
    get_hospitals,
    get_responders,
    get_incidents,
    get_incident_by_uuid,
    create_incident
)
from backend.synthetic_injector import inject_expressway_crash, inject_urban_flood

class TestResQBackend(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        init_db()

    def test_database_seeding(self):
        hospitals = get_hospitals()
        self.assertGreaterEqual(len(hospitals), 4)
        esut = [h for h in hospitals if "Enugu State University" in h["name"]]
        self.assertTrue(len(esut) > 0)
        self.assertEqual(esut[0]["capability"], "trauma")

        responders = get_responders()
        self.assertGreaterEqual(len(responders), 3)

    def test_synthetic_crash_injection(self):
        crash = inject_expressway_crash()
        self.assertIsNotNone(crash)
        self.assertIn("INC-CRASH-", crash["incident_uuid"])
        self.assertEqual(crash["severity_level"], "critical")
        self.assertEqual(crash["casualties_count"], 2)

    def test_synthetic_flood_injection(self):
        flood = inject_urban_flood()
        self.assertIsNotNone(flood)
        self.assertIn("INC-FLOOD-", flood["incident_uuid"])
        self.assertEqual(flood["type"], "urban_flood")

    def test_rest_api_incidents(self):
        res = self.client.get("/api/incidents")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIsInstance(data, list)

    def test_rest_api_hospitals(self):
        res = self.client.get("/api/hospitals?capability=trauma")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        for h in data:
            self.assertEqual(h["capability"], "trauma")

    def test_demo_inject_endpoint(self):
        res = self.client.post("/api/demo/inject", json={"scenario": "crash"})
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "success")
        self.assertIn("incident", data)

    def test_socketio_connection(self):
        client = socketio.test_client(self.app)
        self.assertTrue(client.is_connected())
        
        # Test joining dispatchers room
        client.emit("join", {"room": "dispatchers"})
        received = client.get_received()
        self.assertTrue(any(msg["name"] == "room:joined" for msg in received))
        
        # Test synthetic injection via socket
        client.emit("demo:inject", {"scenario": "flood"})
        received_after = client.get_received()
        self.assertTrue(any(msg["name"] in ("incident:new", "demo:injected") for msg in received_after))
        client.disconnect()

if __name__ == "__main__":
    unittest.main()

