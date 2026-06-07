# API Usage

Project: `osu-skill-predictor`

## Purpose

This document explains how to run the local FastAPI service and call its endpoints.

## Start The Service

Run from the repository root:

```powershell
uvicorn app.main:app --reload
```

Default local URL:

```text
http://127.0.0.1:8000
```

Interactive API docs:

```text
http://127.0.0.1:8000/docs
```

## Endpoints

### `GET /health`

Purpose:

- confirm that the service started and model artifacts loaded successfully

Healthy response example:

```json
{
  "status": "ok",
  "models_loaded": true,
  "artifact_version": "v2_comparison_winner",
  "classifier_model": "RandomForestClassifier",
  "regressor_model": "HistGradientBoostingRegressor",
  "detail": null
}
```

### `POST /predict`

Purpose:

- predict pass probability and expected accuracy from raw player and beatmap summary fields

Example request:

```json
{
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
  "mods_raw": "HDHR"
}
```

Example response:

```json
{
  "pass_probability": 0.98,
  "predicted_accuracy": 97.1,
  "difficulty_gap": 0.27,
  "recommendation": "Playable around current comfort zone",
  "classifier_model": "RandomForestClassifier",
  "regressor_model": "HistGradientBoostingRegressor",
  "artifact_version": "v2_comparison_winner"
}
```

## PowerShell Example

```powershell
$body = @{
  user_pp = 5309.75
  user_accuracy = 98.24
  user_play_count = 11266
  beatmap_star_rating = 5.35
  beatmap_bpm = 180.0
  beatmap_ar = 9.5
  beatmap_od = 8.8
  beatmap_cs = 4.0
  beatmap_hit_length_sec = 112
  beatmap_total_length_sec = 128
  beatmap_passcount = 1200
  beatmap_playcount = 3000
  mods_raw = "HDHR"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/predict `
  -ContentType "application/json" `
  -Body $body
```

## Request Notes

The API expects raw feature inputs, not pre-engineered features.

The service computes these internally:

- `length_bucket`
- `has_hidden`
- `has_hardrock`
- `has_doubletime`
- `star_gap`

## Error Behavior

Current expected status codes:

- `200` for successful health and prediction responses
- `422` for invalid request bodies
- `503` when model artifacts are unavailable at startup
- `500` for unexpected inference-time failures

See also:

- [api_error_handling.md](api_error_handling.md)
