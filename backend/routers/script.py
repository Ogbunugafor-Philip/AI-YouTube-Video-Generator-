"""Script generation + approval router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core import jobs
from core.logger import get_logger
from models.schemas import (
    ScriptApproveRequest,
    ScriptApproveResponse,
    ScriptGenerateRequest,
    ScriptGenerateResponse,
)
from services import cerebras_service
from routers.video import start_production

log = get_logger(__name__)

router = APIRouter(prefix="/api/script", tags=["script"])


@router.post("/generate", response_model=ScriptGenerateResponse)
async def generate(req: ScriptGenerateRequest) -> ScriptGenerateResponse:
    """Generate (or accept) a script, split into scenes, and propose a title.

    - topic mode: Cerebras writes the narration from the topic.
    - writeup mode: the user's content is used VERBATIM — never altered. We only
      split it into scenes.
    """
    mode = (req.mode or "topic").lower()
    log.info("Script generate request: mode=%s duration=%s", mode, req.duration_minutes)

    if mode == "writeup":
        if not req.content or not req.content.strip():
            raise HTTPException(status_code=400, detail="content is required for writeup mode")
        # Use the user's content exactly as provided.
        script_text = req.content
    elif mode == "topic":
        if not req.topic or not req.topic.strip():
            raise HTTPException(status_code=400, detail="topic is required for topic mode")
        try:
            script_text = cerebras_service.generate_script(
                req.topic, req.duration_minutes, mode
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    else:
        raise HTTPException(status_code=400, detail=f"Unknown mode: {mode}")

    try:
        scenes = cerebras_service.split_into_scenes(script_text)
        title = cerebras_service.generate_title(script_text)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    job_id = jobs.create_job(
        title=title,
        script_text=script_text,
        scenes=scenes,
        duration_minutes=req.duration_minutes,
        mode=mode,
    )

    return ScriptGenerateResponse(
        job_id=job_id, title=title, script_text=script_text, scenes=scenes
    )


@router.post("/approve", response_model=ScriptApproveResponse)
async def approve(req: ScriptApproveRequest) -> ScriptApproveResponse:
    """Approve a generated script and trigger the full production pipeline."""
    job = jobs.get_job(req.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    jobs.update_job(req.job_id, status="approved")
    started = start_production(req.job_id)
    status = "processing" if started else job.get("status", "processing")
    log.info("Job %s approved; production started=%s", req.job_id, started)
    return ScriptApproveResponse(job_id=req.job_id, status=status)
