from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LiveSettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tosu_base_url: str = Field(min_length=1)
    tosu_executable_path: str = Field(default="")
    osu_client_id: str = Field(min_length=1)
    osu_client_secret: str = Field(min_length=1)
    player_source: str = Field(default="tosu")
    manual_username: str = Field(default="")
    offline_mode: bool = Field(default=False)
    offline_pp: float = Field(default=0.0, ge=0.0)
    offline_accuracy: float = Field(default=0.0, ge=0.0, le=100.0)
    offline_play_count: int = Field(default=0, ge=0)
    offline_global_rank: int = Field(default=0, ge=0)
    offline_country: str = Field(default="")


class LiveSettingsResponse(BaseModel):
    tosu_base_url: str
    tosu_executable_path: str
    osu_client_id: str
    osu_client_secret: str
    setup_required: bool
    oauth_settings_url: str
    callback_url_hint: str
    web_port: int
    player_source: str
    manual_username: str
    offline_mode: bool
    offline_pp: float
    offline_accuracy: float
    offline_play_count: int
    offline_global_rank: int
    offline_country: str


class LivePlayerResponse(BaseModel):
    username: str | None = None
    user_id: int | None = None
    pp: float | None = None
    accuracy: float | None = None
    play_count: int | None = None
    global_rank: int | None = None
    country_code: str | None = None
    mode: str | None = None


class LiveBeatmapResponse(BaseModel):
    title: str | None = None
    artist: str | None = None
    version: str | None = None
    mapper: str | None = None
    beatmap_id: int | None = None
    beatmapset_id: int | None = None
    client_name: str | None = None
    mods_raw: str = ""
    star_rating: float | None = None
    bpm: float | None = None
    ar: float | None = None
    od: float | None = None
    cs: float | None = None
    hit_length_sec: int | None = None
    total_length_sec: int | None = None
    passcount: int | None = None
    playcount: int | None = None


class LivePredictionResponse(BaseModel):
    pass_probability: float
    predicted_accuracy: float
    difficulty_gap: float
    recommendation: str
    classifier_model: str
    regressor_model: str
    artifact_version: str


class LiveSnapshotResponse(BaseModel):
    status: str
    message: str
    refreshed_at: str
    setup_required: bool
    sources: dict[str, str]
    player: LivePlayerResponse | None = None
    beatmap: LiveBeatmapResponse | None = None
    prediction: LivePredictionResponse | None = None


class TosuStartResponse(BaseModel):
    status: str


class ShutdownResponse(BaseModel):
    tosu_status: str
    message: str
