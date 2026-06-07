# Local Run Instructions

Project: `osu-skill-predictor`

## Purpose

This document captures the minimum local commands needed to:

- install dependencies;
- ensure canonical model artifacts exist;
- run the FastAPI service;
- check the service locally.

## 1. Open The Repository Root

Run commands from the repository root:

```powershell
cd <repo-root>
```

## 2. Install Runtime Dependencies

Minimum API and ML dependencies:

```powershell
python -m pip install fastapi "uvicorn[standard]" pandas scikit-learn joblib pyarrow
```

Optional notebook dependencies:

```powershell
python -m pip install jupyterlab jupyter-collaboration matplotlib
```

## 3. Ensure Canonical Model Artifacts Exist

The API expects these files under `models/`:

- `models/pass_model.joblib`
- `models/accuracy_model.joblib`
- `models/model_metadata.json`

If they are missing, recreate them from the comparison winners:

```powershell
python -m ml.compare --evaluation-mode cross_validation --cv-folds 5 --save-winners --models-root models
```

That command:

- runs grouped cross-validation comparison;
- selects the current winner models;
- retrains those winners on the full cleaned dataset;
- writes canonical local artifacts into `models/`.

## 4. Start The API

Run the FastAPI app locally with:

```powershell
uvicorn app.main:app --reload
```

Expected local base URL:

```text
http://127.0.0.1:8000
```

Useful endpoints:

- `GET /health`
- `POST /predict`

## 5. Check Service Health

Open in a browser or call from PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected healthy response shape:

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

If models are unavailable, expect `503 Service Unavailable`.

## 6. Run A Sample Prediction

Example request:

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

Expected response fields:

- `pass_probability`
- `predicted_accuracy`
- `difficulty_gap`
- `recommendation`
- `classifier_model`
- `regressor_model`
- `artifact_version`

## 7. Run Tests

To validate the current codebase locally:

```powershell
python -m unittest discover -s tests -v
```

This covers:

- feature engineering
- model loading
- comparison workflow
- API health
- API prediction
- invalid input rejection

## 8. Run From Notebook

For interactive comparison and winner saving:

- use `notebooks/03_model_comparison.ipynb`

Recommended notebook flow:

1. run holdout comparison if needed;
2. run cross-validation comparison;
3. run the save cell to write canonical winner artifacts into `models/`;
4. start the API with `uvicorn app.main:app --reload`.

## V1 Practical Recommendation

The simplest reliable local workflow is:

1. install dependencies;
2. regenerate winner artifacts if needed;
3. start `uvicorn`;
4. check `/health`;
5. send a sample `/predict` request.

That is the minimum path required to train locally and serve predictions from the current repository state.
