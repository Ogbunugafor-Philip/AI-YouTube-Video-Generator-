"""FastAPI application entrypoint for the AI YouTube Video Generator.

Run with:  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import config
from core.logger import get_logger
from routers import admin, audio, script, thumbnail, video

log = get_logger(__name__)

app = FastAPI(
    title="AI YouTube Video Generator",
    description="Generate YouTube-ready MP4 videos automatically.",
    version="1.0.0",
)

# CORS — permissive for a local single-creator tool; tighten for real deploys.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers.
app.include_router(script.router)
app.include_router(video.router)
app.include_router(audio.router)
app.include_router(thumbnail.router)
app.include_router(admin.router)

# Serve produced media (final video, thumbnail) so the frontend can display it.
config.ensure_dirs()
app.mount("/media", StaticFiles(directory=str(config.OUTPUT_DIR)), name="media")


@app.on_event("startup")
async def _startup() -> None:
    config.ensure_dirs()
    missing = config.missing_keys()
    if missing:
        log.warning("Missing required config keys: %s", ", ".join(missing))
    log.info("AI YouTube Video Generator started (env=%s)", config.APP_ENV)
    log.info("OUTPUT_DIR=%s TEMP_DIR=%s", config.OUTPUT_DIR, config.TEMP_DIR)


@app.get("/api/health")
async def health() -> dict:
    """Simple health check + config readiness."""
    return {
        "status": "ok",
        "env": config.APP_ENV,
        "missing_keys": config.missing_keys(),
        "models": {
            "script": config.CEREBRAS_MODEL,
            "video": config.FAL_VIDEO_MODEL,
            "image": config.FAL_IMAGE_MODEL,
            "tts": config.FAL_TTS_MODEL,
        },
    }
