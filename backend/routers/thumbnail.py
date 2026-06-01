"""Thumbnail regeneration router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core import jobs
from core.logger import get_logger
from models.schemas import ThumbnailRegenerateRequest, ThumbnailResponse
from services import fal_service

log = get_logger(__name__)

router = APIRouter(prefix="/api/thumbnail", tags=["thumbnail"])


@router.post("/regenerate", response_model=ThumbnailResponse)
async def regenerate(req: ThumbnailRegenerateRequest) -> ThumbnailResponse:
    """Generate a fresh thumbnail for an existing job."""
    job = jobs.get_job(req.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")

    title = req.title or job.get("title", "Untitled Video")
    script_text = job.get("script_text", "")
    try:
        path = await fal_service.generate_thumbnail(title, script_text)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    jobs.update_job(req.job_id, thumbnail_path=path, title=title)
    return ThumbnailResponse(job_id=req.job_id, thumbnail_path=path)
