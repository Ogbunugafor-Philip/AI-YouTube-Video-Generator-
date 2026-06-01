"""Video production router.

Owns the full production pipeline plus the SSE progress stream and the final
download endpoint. The pipeline runs as a background asyncio task; the frontend
watches progress over Server-Sent Events (no polling).
"""
from __future__ import annotations

import asyncio
import datetime
import json
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from core import jobs, stats
from core.logger import get_logger
from models.schemas import VideoProduceRequest, VideoProduceResponse
from services import fal_service, ffmpeg_service

log = get_logger(__name__)

router = APIRouter(prefix="/api/video", tags=["video"])

# Track running pipelines so we never start the same job twice.
_RUNNING: Dict[str, asyncio.Task] = {}


async def run_production(job_id: str) -> None:
    """Execute the end-to-end production pipeline for ``job_id``."""
    job = jobs.get_job(job_id)
    if job is None:
        log.error("run_production: unknown job %s", job_id)
        return

    script_text = job.get("script_text", "")
    scenes = job.get("scenes", [])
    title = job.get("title", "Untitled Video")

    try:
        await jobs.emit(job_id, event="progress", status="processing",
                        step="Generating voice narration", percentage=5)

        # 1) Narration voice.
        narration_path = await fal_service.generate_voice(script_text)

        # 2) Scene clips in parallel (emits per-scene progress 10% -> 70%).
        await jobs.emit(job_id, event="progress",
                        step=f"Generating {len(scenes)} scene clips", percentage=10)
        clips = await fal_service.generate_all_clips(scenes, job_id=job_id)

        # 3) Assemble.
        await jobs.emit(job_id, event="progress",
                        step="Assembling video", percentage=75)
        video_path = await ffmpeg_service.assemble_video(clips, narration_path)

        # 4) Thumbnail.
        await jobs.emit(job_id, event="progress",
                        step="Generating thumbnail", percentage=90)
        thumbnail_path = await fal_service.generate_thumbnail(title, script_text)

        # Record stats for the admin dashboard.
        duration = int(job.get("duration_minutes", 3))
        est_cost = round(
            stats.COST_PER_TTS_CALL
            + len(scenes) * (stats.COST_PER_VIDEO_CLIP + stats.COST_PER_IMAGE_CALL)
            + stats.COST_PER_IMAGE_CALL
            + stats.COST_PER_SCRIPT_CALL * 3,
            4,
        )
        stats.record_video(
            job_id=job_id,
            title=title,
            date=datetime.datetime.now().isoformat(timespec="seconds"),
            duration_minutes=duration,
            estimated_cost=est_cost,
        )

        await jobs.emit(
            job_id,
            event="complete",
            status="complete",
            step="Complete",
            percentage=100,
            video_path=video_path,
            thumbnail_path=thumbnail_path,
        )
        log.info("Production complete for job %s", job_id)
    except Exception as exc:  # noqa: BLE001
        log.exception("Production failed for job %s", job_id)
        await jobs.emit(job_id, event="error", status="error",
                        step=f"Error: {exc}", error=str(exc))
    finally:
        _RUNNING.pop(job_id, None)


def start_production(job_id: str) -> bool:
    """Kick off the pipeline as a background task if not already running."""
    if job_id in _RUNNING:
        return False
    task = asyncio.create_task(run_production(job_id))
    _RUNNING[job_id] = task
    jobs.update_job(job_id, status="processing")
    return True


@router.post("/produce", response_model=VideoProduceResponse)
async def produce(req: VideoProduceRequest) -> VideoProduceResponse:
    """Start the full production pipeline for a job.

    Optionally overrides stored scenes/script/title (e.g. after an edit). Returns
    immediately; progress is delivered over the SSE stream.
    """
    job = jobs.get_job(req.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")

    if req.scenes is not None:
        job["scenes"] = [s.model_dump() for s in req.scenes]
        job["scenes_total"] = len(req.scenes)
    if req.script_text is not None:
        job["script_text"] = req.script_text
    if req.title is not None:
        job["title"] = req.title

    start_production(req.job_id)
    return VideoProduceResponse(
        job_id=req.job_id,
        status=job.get("status", "processing"),
        video_path=job.get("video_path"),
        thumbnail_path=job.get("thumbnail_path"),
    )


@router.get("/progress/{job_id}")
async def progress(job_id: str) -> StreamingResponse:
    """Stream production progress for ``job_id`` as Server-Sent Events."""
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    queue = jobs.get_queue(job_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="No progress channel for job")

    async def event_stream():
        # Emit the current snapshot immediately so late subscribers catch up.
        snapshot = {
            "event": job.get("status", "progress"),
            "status": job.get("status"),
            "step": job.get("step", ""),
            "percentage": job.get("percentage", 0),
            "scenes_total": job.get("scenes_total", 0),
            "scenes_completed": job.get("scenes_completed", 0),
            "video_path": job.get("video_path"),
            "thumbnail_path": job.get("thumbnail_path"),
        }
        yield f"data: {json.dumps(snapshot)}\n\n"
        if job.get("status") in ("complete", "error"):
            return

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=20)
            except asyncio.TimeoutError:
                # Heartbeat keeps the connection alive through proxies.
                yield ": keepalive\n\n"
                continue
            # Enrich with current cumulative counts for convenience.
            payload = dict(event)
            payload.setdefault("scenes_total", job.get("scenes_total", 0))
            payload.setdefault("scenes_completed", job.get("scenes_completed", 0))
            yield f"data: {json.dumps(payload)}\n\n"
            if event.get("event") in ("complete", "error"):
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering for SSE
        },
    )


@router.get("/download/{job_id}")
async def download(job_id: str) -> FileResponse:
    """Return the final MP4 for download."""
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    video_path = job.get("video_path")
    if not video_path:
        raise HTTPException(status_code=409, detail="Video not ready yet")
    from pathlib import Path

    if not Path(video_path).exists():
        raise HTTPException(status_code=404, detail="Video file missing on disk")
    safe_title = "".join(c for c in job.get("title", "video") if c.isalnum() or c in " -_")
    filename = f"{safe_title.strip() or 'video'}.mp4"
    return FileResponse(video_path, media_type="video/mp4", filename=filename)
