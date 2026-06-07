from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from ui.app import app


class FakeLiveService:
    def settings_payload(self) -> dict:
        return {
            "tosu_base_url": "http://127.0.0.1:24050",
            "tosu_executable_path": "",
            "osu_client_id": "123",
            "osu_client_secret": "secret",
            "setup_required": False,
            "oauth_settings_url": "https://osu.ppy.sh/home/account/edit",
            "callback_url_hint": "http://localhost:1337",
            "web_port": 8765,
            "player_source": "tosu",
            "manual_username": "",
            "offline_mode": False,
            "offline_pp": 0.0,
            "offline_accuracy": 0.0,
            "offline_play_count": 0,
            "offline_global_rank": 0,
            "offline_country": "",
        }

    def update_settings(self, payload: dict) -> dict:
        merged = self.settings_payload()
        merged.update(payload)
        merged["setup_required"] = False
        return merged

    def start_tosu(self) -> dict:
        return {"status": "started"}

    def shutdown(self) -> dict:
        return {"tosu_status": "not_running"}

    def snapshot(self) -> dict:
        return {
            "status": "ok",
            "message": "Prediction updated from current osu! state.",
            "refreshed_at": "2026-06-07T12:00:00Z",
            "setup_required": False,
            "sources": {"tosu": "ok", "osu_api": "ok", "prediction": "local-models"},
            "player": {
                "username": "nayut",
                "user_id": 1,
                "pp": 1000.0,
                "accuracy": 98.5,
                "play_count": 500,
                "global_rank": 100,
                "country_code": "KZ",
                "mode": "osu",
            },
            "beatmap": {
                "title": "Map",
                "artist": "Artist",
                "version": "Insane",
                "mapper": "Mapper",
                "beatmap_id": 123,
                "beatmapset_id": 456,
                "client_name": "stable",
                "mods_raw": "HDHR",
                "star_rating": 5.2,
                "bpm": 180.0,
                "ar": 9.5,
                "od": 8.8,
                "cs": 4.0,
                "hit_length_sec": 100,
                "total_length_sec": 120,
                "passcount": 5000,
                "playcount": 10000,
            },
            "prediction": {
                "pass_probability": 0.9,
                "predicted_accuracy": 97.5,
                "difficulty_gap": -0.2,
                "recommendation": "Comfortable map for current skill",
                "classifier_model": "RandomForestClassifier",
                "regressor_model": "HistGradientBoostingRegressor",
                "artifact_version": "v2",
            },
        }


class WebLiveApiTests(unittest.TestCase):
    def test_root_serves_html(self) -> None:
        with TestClient(app) as client:
            response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("osu! Skill Predictor", response.text)

    def test_live_endpoints_return_expected_contract(self) -> None:
        with TestClient(app) as client:
            client.app.state.live_service = FakeLiveService()
            settings_response = client.get("/api/live/settings")
            start_response = client.post("/api/live/tosu/start")
            snapshot_response = client.get("/api/live/snapshot")

        self.assertEqual(settings_response.status_code, 200)
        self.assertEqual(start_response.status_code, 200)
        self.assertEqual(snapshot_response.status_code, 200)
        self.assertEqual(start_response.json()["status"], "started")
        self.assertEqual(snapshot_response.json()["status"], "ok")
        self.assertEqual(snapshot_response.json()["player"]["username"], "nayut")

    def test_update_settings_endpoint_accepts_payload(self) -> None:
        with TestClient(app) as client:
            client.app.state.live_service = FakeLiveService()
            response = client.post(
                "/api/live/settings",
                json={
                    "tosu_base_url": "http://127.0.0.1:24050",
                    "tosu_executable_path": "C:/tosu/tosu.exe",
                    "osu_client_id": "58646",
                    "osu_client_secret": "secret-value",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["osu_client_id"], "58646")
        self.assertEqual(payload["tosu_executable_path"], "C:/tosu/tosu.exe")


class SmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import os as _os
        _os.environ["OSU_PREDICTOR_TEST"] = "1"

        from app.main import app as core_app
        from ui.router import STATIC_DIR, router
        from fastapi.staticfiles import StaticFiles

        if not hasattr(core_app, "_ui_mounted"):
            core_app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
            core_app.include_router(router)
            setattr(core_app, "_ui_mounted", True)

    def _client(self) -> TestClient:
        from app.main import app as core_app
        core_app.state.live_service = FakeLiveService()
        return TestClient(core_app)

    def test_health_returns_ok(self) -> None:
        with self._client() as client:
            response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("classifier_model", data)

    def test_root_returns_html(self) -> None:
        with self._client() as client:
            response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("osu! Skill Predictor", response.text)

    def test_live_settings_returns_expected_shape(self) -> None:
        with self._client() as client:
            response = client.get("/api/live/settings")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in ("tosu_base_url", "osu_client_id", "setup_required", "player_source", "manual_username"):
            self.assertIn(key, data)

    def test_live_snapshot_returns_valid_shape(self) -> None:
        with self._client() as client:
            response = client.get("/api/live/snapshot")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("player", data)
        self.assertIn("beatmap", data)
        self.assertIn("prediction", data)
        self.assertEqual(data["player"]["username"], "nayut")
        self.assertGreater(data["prediction"]["pass_probability"], 0)

    def test_tosu_start_returns_status(self) -> None:
        with self._client() as client:
            response = client.post("/api/live/tosu/start")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "started")

    def test_shutdown_returns_ok(self) -> None:
        with self._client() as client:
            response = client.post("/api/live/shutdown")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("tosu_status", data)

    def test_predict_endpoint_accepts_valid_payload(self) -> None:
        with self._client() as client:
            payload = {
                "user_pp": 1000.0,
                "user_accuracy": 95.0,
                "user_play_count": 500,
                "beatmap_star_rating": 5.2,
                "beatmap_bpm": 180.0,
                "beatmap_ar": 9.5,
                "beatmap_od": 8.8,
                "beatmap_cs": 4.0,
                "beatmap_hit_length_sec": 100,
                "beatmap_total_length_sec": 120,
                "beatmap_passcount": 5000,
                "beatmap_playcount": 10000,
            }
            response = client.post("/predict", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("pass_probability", data)
        self.assertIn("predicted_accuracy", data)

    def test_predict_rejects_bad_payload(self) -> None:
        with self._client() as client:
            response = client.post("/predict", json={"user_pp": -1})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
