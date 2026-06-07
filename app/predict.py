from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from ml.features import (
    ALL_FEATURE_COLUMNS,
    ComfortMapping,
    apply_star_comfort_mapping,
    assign_length_bucket,
    contains_mod,
    deserialize_comfort_mapping,
)

from .schemas import PredictionRequest, PredictionResponse


def default_models_root() -> Path:
    return Path(__file__).resolve().parents[1] / "models"


@dataclass
class LoadedPredictionArtifacts:
    classifier: Any
    regressor: Any
    metadata: dict[str, Any]
    feature_columns: list[str]
    comfort_mapping: ComfortMapping


def recommendation_text(*, pass_probability: float, predicted_accuracy: float, difficulty_gap: float) -> str:
    if pass_probability < 0.35:
        return "Likely too hard right now"
    if pass_probability < 0.65:
        return "Borderline pass chance"
    if difficulty_gap > 0.5:
        return "Playable, but slightly above comfort zone"
    if predicted_accuracy >= 97.0 and difficulty_gap <= 0.0:
        return "Comfortable map for current skill"
    return "Playable around current comfort zone"


def clip_accuracy_prediction(prediction: float) -> float:
    return max(0.0, min(100.0, prediction))


def build_prediction_feature_frame(
    payload: PredictionRequest,
    *,
    comfort_mapping: ComfortMapping,
    feature_columns: list[str],
) -> pd.DataFrame:
    raw_row = pd.DataFrame(
        [
            {
                "user_pp": float(payload.user_pp),
                "user_accuracy": float(payload.user_accuracy),
                "user_play_count": int(payload.user_play_count),
                "beatmap_star_rating": float(payload.beatmap_star_rating),
                "beatmap_bpm": float(payload.beatmap_bpm),
                "beatmap_ar": float(payload.beatmap_ar),
                "beatmap_od": float(payload.beatmap_od),
                "beatmap_cs": float(payload.beatmap_cs),
                "beatmap_hit_length_sec": int(payload.beatmap_hit_length_sec),
                "beatmap_total_length_sec": int(payload.beatmap_total_length_sec),
                "beatmap_passcount": int(payload.beatmap_passcount),
                "beatmap_playcount": int(payload.beatmap_playcount),
                "mods_raw": payload.mods_raw,
            }
        ]
    )

    raw_row["length_bucket"] = assign_length_bucket(raw_row["beatmap_hit_length_sec"])
    raw_row["has_hidden"] = contains_mod(raw_row["mods_raw"], "HD").astype(int)
    raw_row["has_hardrock"] = contains_mod(raw_row["mods_raw"], "HR").astype(int)
    raw_row["has_doubletime"] = (contains_mod(raw_row["mods_raw"], "DT") | contains_mod(raw_row["mods_raw"], "NC")).astype(int)
    player_star_comfort = apply_star_comfort_mapping(raw_row["user_pp"], comfort_mapping)
    raw_row["star_gap"] = raw_row["beatmap_star_rating"] - player_star_comfort

    return raw_row[feature_columns].copy()


def load_prediction_artifacts(models_root: str | Path | None = None) -> LoadedPredictionArtifacts:
    root = default_models_root() if models_root is None else Path(models_root)
    classifier_path = root / "pass_model.joblib"
    regressor_path = root / "accuracy_model.joblib"
    metadata_path = root / "model_metadata.json"

    missing = [path.name for path in [classifier_path, regressor_path, metadata_path] if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing model artifacts under {root}: {missing}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    if "star_comfort_mapping" not in metadata:
        raise ValueError("Model metadata is missing star_comfort_mapping required for API inference")

    feature_columns = list(metadata.get("feature_columns", ALL_FEATURE_COLUMNS))
    return LoadedPredictionArtifacts(
        classifier=joblib.load(classifier_path),
        regressor=joblib.load(regressor_path),
        metadata=metadata,
        feature_columns=feature_columns,
        comfort_mapping=deserialize_comfort_mapping(metadata["star_comfort_mapping"]),
    )


class PredictionService:
    def __init__(self, artifacts: LoadedPredictionArtifacts):
        self.artifacts = artifacts

    @classmethod
    def load(cls, models_root: str | Path | None = None) -> "PredictionService":
        return cls(load_prediction_artifacts(models_root=models_root))

    def health_payload(self) -> dict[str, Any]:
        classifier_meta = self.artifacts.metadata.get("classifier", {})
        regressor_meta = self.artifacts.metadata.get("regressor", {})
        return {
            "status": "ok",
            "models_loaded": True,
            "artifact_version": self.artifacts.metadata.get("artifact_version"),
            "classifier_model": classifier_meta.get("estimator"),
            "regressor_model": regressor_meta.get("estimator"),
            "detail": None,
        }

    def predict(self, payload: PredictionRequest) -> PredictionResponse:
        feature_frame = build_prediction_feature_frame(
            payload,
            comfort_mapping=self.artifacts.comfort_mapping,
            feature_columns=self.artifacts.feature_columns,
        )

        pass_probability = float(self.artifacts.classifier.predict_proba(feature_frame)[0, 1])
        predicted_accuracy = clip_accuracy_prediction(float(self.artifacts.regressor.predict(feature_frame)[0]))
        difficulty_gap = float(feature_frame.iloc[0]["star_gap"])

        classifier_meta = self.artifacts.metadata.get("classifier", {})
        regressor_meta = self.artifacts.metadata.get("regressor", {})
        return PredictionResponse(
            pass_probability=pass_probability,
            predicted_accuracy=predicted_accuracy,
            difficulty_gap=difficulty_gap,
            recommendation=recommendation_text(
                pass_probability=pass_probability,
                predicted_accuracy=predicted_accuracy,
                difficulty_gap=difficulty_gap,
            ),
            classifier_model=str(classifier_meta.get("estimator", "")),
            regressor_model=str(regressor_meta.get("estimator", "")),
            artifact_version=str(self.artifacts.metadata.get("artifact_version", "")),
        )
