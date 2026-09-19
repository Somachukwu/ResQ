import unittest
import json
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from backend.severity_engine import calculate_rsi
from backend.flood_model import (
    compute_impassability_probability,
    estimate_water_depth_cm,
    evaluate_basin_flood_risk,
    get_flood_hazard_geojson,
    ENUGU_DRAINAGE_BASINS
)
from backend.corridor_risk import (
    calculate_corridor_risk_index,
    evaluate_all_corridors,
    FRSC_CORRIDOR_BLACKSPOTS
)
from backend.survival_optimizer import (
    compute_survival_probability,
    optimize_trauma_routing,
    get_hospital_tier
)


class TestResQModelingSuite(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()

    # --- 1. ResQ Severity Index (RSI 1.0 - 5.0) Engine Tests ---

    def test_rsi_nominal_green(self):
        """Conscious, single walking casualty with no hemorrhage -> GREEN / Minor."""
        triage = calculate_rsi(
            unresponsive=False,
            severe_hemorrhage=False,
            airway_compromise=False,
            entrapment=False,
            casualties_count=1
        )
        self.assertEqual(triage["rsi_score"], 1.0)
        self.assertEqual(triage["triage_tier"], "GREEN")
        self.assertEqual(triage["priority_label"], "minor")
        self.assertFalse(triage["requires_als"])

    def test_rsi_critical_red(self):
        """Unresponsive victim with severe hemorrhage -> RED / Immediate."""
        triage = calculate_rsi(
            unresponsive=True,        # +2.0
            severe_hemorrhage=True,   # +1.5
            airway_compromise=False,
            entrapment=False,
            casualties_count=1
        )
        # Base 1.0 + 2.0 + 1.5 = 4.5
        self.assertEqual(triage["rsi_score"], 4.5)
        self.assertEqual(triage["triage_tier"], "RED")
        self.assertEqual(triage["priority_label"], "critical")
        self.assertTrue(triage["requires_als"])

    def test_rsi_maximum_clamping(self):
        """Mass-casualty incident with all risk factors clamps strictly at 5.0."""
        triage = calculate_rsi(
            unresponsive=True,
            severe_hemorrhage=True,
            airway_compromise=True,
            entrapment=True,
            casualties_count=12,
            scene_hazards=["fuel_leak", "vehicle_fire"]
        )
        self.assertEqual(triage["rsi_score"], 5.0)
        self.assertEqual(triage["triage_tier"], "RED")

    def test_rsi_expectant_black(self):
        """Confirmed irreversible apnea/death triggers START BLACK."""
        triage = calculate_rsi(all_deceased=True)
        self.assertEqual(triage["rsi_score"], 5.0)
        self.assertEqual(triage["triage_tier"], "BLACK")
        self.assertEqual(triage["priority_label"], "expectant")

    # --- 2. Hydro-Meteorological Flood Impassability Model Tests ---

    def test_flood_dry_condition(self):
        """Under zero precipitation, road impassability probability is low."""
        p = compute_impassability_probability(
            rain_rate_mm_hr=0.0,
            elevation_deficit_m=2.0,
            culvert_proximity_factor=0.5
        )
        self.assertLess(p, 0.35)

    def test_flood_torrential_inundation(self):
        """Under heavy tropical downpour (60 mm/hr), deep basin becomes impassable."""
        p = compute_impassability_probability(
            rain_rate_mm_hr=60.0,
            elevation_deficit_m=5.0,
            culvert_proximity_factor=1.0
        )
        self.assertGreaterEqual(p, 0.65)

    def test_basin_flood_evaluation_and_avoidance(self):
        """Torrential rain triggers avoidance waypoints and severe flood alert."""
        evaluation = evaluate_basin_flood_risk(rain_rate_mm_hr=65.0)
        self.assertIn("regional_status", evaluation)
        self.assertEqual(evaluation["regional_status"], "SEVERE_FLOOD_ALERT")
        self.assertGreater(evaluation["impassable_segments_count"], 0)
        self.assertGreater(len(evaluation["avoidance_waypoints"]), 0)

    def test_flood_geojson_generation(self):
        """GeoJSON FeatureCollection contains valid polygons with proper properties."""
        geojson = get_flood_hazard_geojson(rain_rate_mm_hr=40.0)
        self.assertEqual(geojson["type"], "FeatureCollection")
        self.assertEqual(len(geojson["features"]), len(ENUGU_DRAINAGE_BASINS))
        for feat in geojson["features"]:
            self.assertEqual(feat["geometry"]["type"], "Polygon")
            self.assertIn("probability", feat["properties"])

    # --- 3. FRSC Spatial Crash Corridor Risk (CRI_t) Tests ---

    def test_corridor_risk_calculation(self):
        """Calculates dynamic CRI_t with component breakdown."""
        result = calculate_corridor_risk_index(
            kde_density=0.95,
            slope_gradient_pct=8.5,
            rain_rate_mm_hr=30.0,
            current_speed_kmh=45.0,
            freeflow_speed_kmh=80.0
        )
        self.assertGreaterEqual(result["cri_score"], 65.0)
        self.assertIn(result["risk_level"], ("CRITICAL_RISK", "ELEVATED_RISK"))
        self.assertIn("component_weights", result)

    def test_all_corridors_evaluation(self):
        """Evaluates all FRSC blackspots and identifies Ugwu Onyeama as high risk."""
        eval_result = evaluate_all_corridors(rain_rate_mm_hr=35.0)
        self.assertGreaterEqual(eval_result["total_corridors_monitored"], 5)
        self.assertIsNotNone(eval_result["highest_risk_corridor"])
        self.assertIn("Ugwu Onyeama", eval_result["highest_risk_corridor"])

    # --- 4. Golden Hour Survival Optimization Tests ---

    def test_survival_decay_ordering(self):
        """Tertiary hospital maintains higher survival probability than primary clinic over time."""
        transit_time = 20.0  # 20 minutes
        p_tertiary = compute_survival_probability(transit_time, facility_tier="tertiary")
        p_secondary = compute_survival_probability(transit_time, facility_tier="secondary")
        p_primary = compute_survival_probability(transit_time, facility_tier="primary")

        self.assertGreater(p_tertiary, p_secondary)
        self.assertGreater(p_secondary, p_primary)

    def test_trauma_routing_tradeoff_validation(self):
        """
        Validates clinical trade-off: A 22-min transit to a Tertiary Center (ESUTH Parklane)
        yields higher definitive survival utility than a 9-min transit to an unequipped local clinic.
        """
        candidates = [
            {
                "hospital": {"name": "Local Primary Health Center", "capability": "general"},
                "duration_mins": 9.0,
                "distance_km": 4.5
            },
            {
                "hospital": {"name": "ESUT Teaching Hospital Parklane", "capability": "trauma"},
                "duration_mins": 22.0,
                "distance_km": 14.0
            }
        ]

        decision = optimize_trauma_routing(
            hospital_candidates=candidates,
            incident_type="trauma",
            rsi_score=4.5
        )

        self.assertEqual(decision["recommended_hospital"], "ESUT Teaching Hospital Parklane")
        self.assertTrue(decision["clinical_tradeoff_active"])
        self.assertIn("Bypassing closer clinic", decision["clinical_justification"])

    # --- 5. REST API Integration Tests ---

    def test_api_severity_endpoint(self):
        res = self.client.post("/api/analysis/severity", json={
            "unresponsive": True,
            "severe_hemorrhage": True,
            "casualties_count": 2
        })
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["triage_tier"], "RED")
        self.assertGreaterEqual(data["rsi_score"], 4.0)

    def test_api_flood_risk_endpoint(self):
        res = self.client.get("/api/analysis/flood-risk?rain_rate=45.0")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("basins", data)
        self.assertEqual(len(data["basins"]), len(ENUGU_DRAINAGE_BASINS))

    def test_api_flood_geojson_endpoint(self):
        res = self.client.get("/api/analysis/flood-geojson?rain_rate=30.0")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["type"], "FeatureCollection")

    def test_api_corridor_risk_endpoint(self):
        res = self.client.get("/api/analysis/corridor-risk?rain_rate=20.0")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("corridors", data)
        self.assertIn("tactical_prepositioning_alerts", data)

    def test_api_nearest_hospital_with_survival_metrics(self):
        """Checks that /api/nearest-hospital includes survival optimization fields."""
        res = self.client.post("/api/nearest-hospital", json={
            "lat": 6.4474,
            "lng": 7.5098,
            "incident_type": "trauma",
            "rsi_score": 4.2
        })
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("recommended_hospital", data)
        self.assertIn("predicted_survival_probability", data)
        self.assertIn("survival_utility_score", data)
        self.assertIn("clinical_justification", data)


if __name__ == "__main__":
    unittest.main()

