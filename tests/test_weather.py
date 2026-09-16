import unittest
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from backend.weather_service import get_weather_for_coords, translate_operational_impact

class TestWeatherEngine(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()

    def test_community_weather_model(self):
        data = get_weather_for_coords(region_code="community")
        self.assertEqual(data["region"], "community")
        self.assertIn("Enugu Urban", data["location_name"])
        self.assertGreater(data["temp_c"], 0)
        self.assertIn("operational_impact", data)
        self.assertIn("advisories", data["operational_impact"])

    def test_state_weather_model(self):
        data = get_weather_for_coords(region_code="state")
        self.assertEqual(data["region"], "state")
        self.assertIn("Enugu State", data["location_name"])

    def test_operational_impact_translation(self):
        # Heavy rain should trigger flash flood warning and transit delay
        impact = translate_operational_impact(
            weather_main="Heavy Rain",
            rainfall_mm=45.0,
            wind_kmh=35.0,
            visibility_km=1.2,
            temp=28.0
        )
        self.assertEqual(impact["escalation_trend"], "escalating")
        self.assertGreater(impact["transit_delay_pct"], 20)
        
        advisory_types = [a["type"] for a in impact["advisories"]]
        self.assertIn("flood", advisory_types)
        self.assertIn("visibility", advisory_types)

    def test_weather_rest_api(self):
        res = self.client.get("/api/weather?region=community")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("temp_c", data)
        self.assertIn("operational_impact", data)

        res_state = self.client.get("/api/weather?region=state")
        self.assertEqual(res_state.status_code, 200)
        data_state = json.loads(res_state.data)
        self.assertIn("Enugu State", data_state["location_name"])

if __name__ == "__main__":
    unittest.main()

