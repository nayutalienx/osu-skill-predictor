from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from starlette.background import BackgroundTask

from .live import LiveService
from .schemas import (
    LiveSettingsPayload,
    LiveSettingsResponse,
    LiveSnapshotResponse,
    ShutdownResponse,
    TosuStartResponse,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"

router = APIRouter()


def get_live_service(request: Request) -> LiveService:
    service = getattr(request.app.state, "live_service", None)
    if service is not None:
        return service

    pred_service = getattr(request.app.state, "prediction_service", None)
    if pred_service is None:
        detail = getattr(request.app.state, "startup_error", None) or "Live service is not ready"
        raise HTTPException(status_code=503, detail=detail)

    try:
        service = LiveService.from_env(pred_service)
        request.app.state.live_service = service
        return service
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Live service failed to initialize: {exc}")


@router.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/api/live/settings", response_model=LiveSettingsResponse)
def live_settings(request: Request) -> LiveSettingsResponse:
    service = get_live_service(request)
    return LiveSettingsResponse(**service.settings_payload())


@router.post("/api/live/settings", response_model=LiveSettingsResponse)
def update_live_settings(payload: LiveSettingsPayload, request: Request) -> LiveSettingsResponse:
    service = get_live_service(request)
    return LiveSettingsResponse(**service.update_settings(payload.model_dump()))


@router.post("/api/live/tosu/start", response_model=TosuStartResponse)
def start_tosu(request: Request) -> TosuStartResponse:
    service = get_live_service(request)
    return TosuStartResponse(**service.start_tosu())


@router.get("/api/live/snapshot", response_model=LiveSnapshotResponse)
def live_snapshot(request: Request) -> LiveSnapshotResponse:
    service = get_live_service(request)
    return LiveSnapshotResponse(**service.snapshot())


@router.post("/api/live/shutdown", response_model=ShutdownResponse)
def shutdown(request: Request) -> JSONResponse:
    service = get_live_service(request)
    payload = service.shutdown()

    def _exit() -> None:
        if not os.environ.get("OSU_PREDICTOR_TEST"):
            os._exit(0)

    return JSONResponse(
        content={"tosu_status": payload["tosu_status"], "message": "Shutting down..."},
        background=BackgroundTask(_exit),
    )


@router.post("/api/live/user/refresh")
def refresh_user(request: Request) -> JSONResponse:
    service = get_live_service(request)
    payload = service.refresh_user_cache()
    return JSONResponse(content=payload)
