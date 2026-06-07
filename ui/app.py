from __future__ import annotations

from fastapi.staticfiles import StaticFiles

from app.main import app

from .router import STATIC_DIR, router as ui_router

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(ui_router)
