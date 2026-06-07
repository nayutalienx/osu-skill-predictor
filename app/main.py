from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .predict import PredictionService
from .schemas import HealthResponse, PredictionRequest, PredictionResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.prediction_service = None
    app.state.startup_error = None
    try:
        app.state.prediction_service = PredictionService.load()
    except Exception as exc:  # pragma: no cover - exercised through health response
        app.state.startup_error = str(exc)
    yield


app = FastAPI(
    title="osu-skill-predictor API",
    version="0.1.0",
    lifespan=lifespan,
)


def get_prediction_service(request: Request) -> PredictionService:
    service = getattr(request.app.state, "prediction_service", None)
    if service is None:
        detail = getattr(request.app.state, "startup_error", None) or "Prediction service is not ready"
        raise HTTPException(status_code=503, detail=detail)
    return service


@app.get("/health", response_model=HealthResponse)
def health(request: Request):
    service = getattr(request.app.state, "prediction_service", None)
    if service is None:
        payload = HealthResponse(
            status="error",
            models_loaded=False,
            detail=getattr(request.app.state, "startup_error", None) or "Prediction service is not ready",
        )
        return JSONResponse(status_code=503, content=payload.model_dump())
    return HealthResponse(**service.health_payload())


@app.post("/predict", response_model=PredictionResponse)
def predict(payload: PredictionRequest, request: Request) -> PredictionResponse:
    service = get_prediction_service(request)
    try:
        return service.predict(payload)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive API boundary
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}") from exc
