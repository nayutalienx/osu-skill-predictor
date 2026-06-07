from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_pp: float = Field(ge=0.0)
    user_accuracy: float = Field(ge=0.0, le=100.0)
    user_play_count: int = Field(ge=0)
    beatmap_star_rating: float = Field(ge=0.0)
    beatmap_bpm: float = Field(gt=0.0)
    beatmap_ar: float = Field(ge=0.0, le=12.0)
    beatmap_od: float = Field(ge=0.0, le=12.0)
    beatmap_cs: float = Field(ge=0.0, le=10.0)
    beatmap_hit_length_sec: int = Field(ge=0)
    beatmap_total_length_sec: int = Field(ge=0)
    beatmap_passcount: int = Field(ge=0)
    beatmap_playcount: int = Field(ge=0)
    mods_raw: str = Field(default="")

    @field_validator("mods_raw")
    @classmethod
    def normalize_mods_raw(cls, value: str) -> str:
        return value.strip().upper().replace(" ", "")

    @model_validator(mode="after")
    def validate_cross_field_domains(self) -> "PredictionRequest":
        if self.beatmap_total_length_sec < self.beatmap_hit_length_sec:
            raise ValueError("beatmap_total_length_sec must be greater than or equal to beatmap_hit_length_sec")
        if self.beatmap_playcount < self.beatmap_passcount:
            raise ValueError("beatmap_playcount must be greater than or equal to beatmap_passcount")
        return self


class PredictionResponse(BaseModel):
    pass_probability: float = Field(ge=0.0, le=1.0)
    predicted_accuracy: float = Field(ge=0.0, le=100.0)
    difficulty_gap: float
    recommendation: str
    classifier_model: str
    regressor_model: str
    artifact_version: str


class HealthResponse(BaseModel):
    status: str
    models_loaded: bool
    artifact_version: str | None = None
    classifier_model: str | None = None
    regressor_model: str | None = None
    detail: str | None = None
