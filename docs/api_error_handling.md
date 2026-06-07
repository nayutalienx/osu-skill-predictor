# API Error Handling Rules

Project: `osu-skill-predictor`

## Purpose

This document defines the MVP error-handling behavior for the local FastAPI service.

The goal is to keep failures:

- predictable;
- easy to debug locally;
- understandable to a caller;
- free of raw stack-trace output in API responses.

## Current Service Boundary

The API currently exposes:

- `GET /health`
- `POST /predict`

The service loads model artifacts at startup and stores the prediction service in application state.

## Error Categories

### 1. Validation errors

Source:

- request body does not match the Pydantic schema;
- required fields are missing;
- field types are invalid;
- cross-field domain checks fail.

Examples:

- missing `beatmap_bpm`;
- `user_play_count` is negative;
- `beatmap_total_length_sec < beatmap_hit_length_sec`;
- `beatmap_playcount < beatmap_passcount`.

Response behavior:

- HTTP status: `422 Unprocessable Entity`
- body shape: FastAPI/Pydantic validation error response

Why:

- this is standard FastAPI behavior;
- the caller gets field-level feedback without custom parsing logic.

### 2. Service-not-ready errors

Source:

- model artifacts are missing;
- `model_metadata.json` is missing or incomplete;
- model loading fails during application startup.

Response behavior:

For `GET /health`:

- HTTP status: `503 Service Unavailable`
- payload fields:
  - `status = "error"`
  - `models_loaded = false`
  - `detail = startup error message`

For `POST /predict`:

- HTTP status: `503 Service Unavailable`
- payload uses FastAPI `HTTPException` format
- `detail` contains a short readiness message or startup error message

Why:

- prediction should not pretend to be available when artifacts are not loaded;
- `503` is the clearest local-service signal for dependency readiness failure.

### 3. Internal prediction errors

Source:

- unexpected failure during feature preparation;
- model inference failure;
- data-shape mismatch between service logic and serialized model pipeline.

Response behavior:

- HTTP status: `500 Internal Server Error`
- body contains:
  - `detail = "Prediction failed: ..."`

Important rule:

- do not return raw Python stack traces in the HTTP response;
- a short exception message is acceptable for local MVP debugging.

Why:

- this is still a local developer-facing service;
- keeping the message short is enough for debugging without dumping internal trace noise into the response.

## Endpoint-Specific Rules

### `/health`

Healthy service means:

- classifier artifact loads successfully;
- regressor artifact loads successfully;
- metadata loads successfully;
- required inference metadata such as `star_comfort_mapping` is present.

Healthy response:

- status code: `200`
- `status = "ok"`
- `models_loaded = true`
- includes `artifact_version`, `classifier_model`, and `regressor_model`

Unhealthy response:

- status code: `503`
- `status = "error"`
- `models_loaded = false`
- `detail` explains the startup failure briefly

### `/predict`

Successful prediction means:

1. request validates;
2. service is loaded;
3. raw request values are transformed into model-ready features;
4. classifier and regressor both produce outputs;
5. regressor output is clipped into `[0, 100]`.

Successful response:

- status code: `200`
- includes:
  - `pass_probability`
  - `predicted_accuracy`
  - `difficulty_gap`
  - `recommendation`
  - `classifier_model`
  - `regressor_model`
  - `artifact_version`

Failure responses:

- `422` for invalid input
- `503` when the prediction service is not ready
- `500` for unexpected inference-time failures

## Validation Error Expectations

The request schema should continue to reject:

- missing required fields
- unknown extra fields
- invalid numeric domains
- logically inconsistent beatmap length and play/pass count relationships

This behavior is desirable because it prevents the service from silently guessing on malformed payloads.

## Logging Guidance

For the current MVP:

- API responses should stay short and readable;
- detailed debugging should come from local terminal logs, not the response body;
- if later needed, add structured logging around startup load failures and prediction failures.

## V1 Practical Recommendation

Keep the API failure contract simple:

- `200` for healthy service and successful prediction
- `422` for invalid caller input
- `503` for missing or unloaded model artifacts
- `500` for unexpected inference failures

This is enough for a clear local developer workflow without overengineering a custom error envelope.
