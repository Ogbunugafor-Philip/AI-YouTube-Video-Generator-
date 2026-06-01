"""Audio (voice narration) router.

Allows regenerating narration independently of the full pipeline.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core import jobs
from core.logger import get_logger
from models.schemas import AudioGenerateRequest, AudioResponse
from services import fal_service

log = get_logger(__name__)

router = APIRouter(prefix="/api/audio", tags=["audio"])


@router.post("/generate", response_model=AudioResponse)
async def generate(req: AudioGenerateRequest) -> AudioResponse:
    """Generate narration audio for a job's script (or supplied text)."""
    job = jobs.get_job(req.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")

    script_text = req.script_text or job.get("script_text", "")
    if not script_text.strip():
        raise HTTPException(status_code=400, detail="No script text to narrate")
    try:
        path = await fal_service.generate_voice(script_text)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AudioResponse(job_id=req.job_id, audio_path=path)
