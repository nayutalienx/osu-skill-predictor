from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app


VALID_REQUEST = {
    "user_pp": 5309.75,
    "user_accuracy": 98.24,
    "user_play_count": 11266,
    "beatmap_star_rating": 5.35,
    "beatmap_bpm": 180.0,
    "beatmap_ar": 9.5,
    "beatmap_od": 8.8,
    "beatmap_cs": 4.0,
    "beatmap_hit_length_sec": 112,
    "beatmap_total_length_sec": 128,
    "beatmap_passcount": 1200,
    "beatmap_playcount": 3000,
    "mods_raw": "HDHR",
}


class ApiTests(unittest.TestCase):
    def test_health_endpoint_reports_loaded_models(self) -> None:
        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["models_loaded"])
        self.assertEqual(payload["classifier_model"], "RandomForestClassifier")
        self.assertEqual(payload["regressor_model"], "HistGradientBoostingRegressor")

    def test_predict_endpoint_returns_expected_contract(self) -> None:
        with TestClient(app) as client:
            response = client.post("/predict", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("pass_probability", payload)
        self.assertIn("predicted_accuracy", payload)
        self.assertIn("difficulty_gap", payload)
        self.assertIn("recommendation", payload)
        self.assertIn("classifier_model", payload)
        self.assertIn("regressor_model", payload)
        self.assertGreaterEqual(payload["pass_probability"], 0.0)
        self.assertLessEqual(payload["pass_probability"], 1.0)
        self.assertGreaterEqual(payload["predicted_accuracy"], 0.0)
        self.assertLessEqual(payload["predicted_accuracy"], 100.0)
        self.assertIsInstance(payload["recommendation"], str)
        self.assertTrue(payload["recommendation"])

    def test_predict_rejects_invalid_payload(self) -> None:
        invalid_request = dict(VALID_REQUEST)
        invalid_request.pop("beatmap_bpm")

        with TestClient(app) as client:
            response = client.post("/predict", json=invalid_request)

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
