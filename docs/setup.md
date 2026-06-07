# Setup

Project: `osu-skill-predictor`

## Purpose

This document defines the minimum local setup needed for development, testing, and serving predictions.

## Python

Recommended environment:

- Python `3.10+`

The current repo has already been exercised on Python `3.10`.

## Create Or Activate An Environment

Example with `venv`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If you prefer a user-site install instead of a virtual environment, that is also acceptable for local work.

## Install Dependencies

Core runtime dependencies:

```powershell
python -m pip install fastapi "uvicorn[standard]" pandas scikit-learn joblib pyarrow
```

Notebook and plotting dependencies:

```powershell
python -m pip install matplotlib jupyterlab jupyter-collaboration
```

Optional quality-of-life dependency for interactive HTTP calls:

```powershell
python -m pip install requests
```

## Required Local Assets

The FastAPI service expects canonical model artifacts under `models/`:

- `models/pass_model.joblib`
- `models/accuracy_model.joblib`
- `models/model_metadata.json`

These files are committed in the repository, but you can regenerate them locally if needed.

## Dataset And API Credentials

For local API serving only:

- no external API credentials are required;
- the service runs entirely from the saved local model artifacts.

For dataset recollection or retraining from osu! API:

- use the local ignored `.env.local` workflow already established in the repo;
- keep OAuth credentials out of Git.

## Verify Installation

Run:

```powershell
python -m unittest discover -s tests -v
```

If this passes, the local environment is good enough for:

- feature engineering tests
- model loading tests
- comparison tests
- API endpoint tests

## Next Step

After setup, continue with:

- [training.md](training.md) for model artifact generation
- [api_usage.md](api_usage.md) for running and calling the service
