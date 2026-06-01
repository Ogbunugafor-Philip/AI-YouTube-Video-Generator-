"""In-memory job store + per-job progress event channels.

This is a single-creator personal tool, so an in-process store is sufficient.
Each job tracks its current production state and owns an ``asyncio.Queue`` that
production code pushes progress events onto and the SSE endpoint drains.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger(__name__)

# job_id -> job dict
_JOBS: Dict[str, Dict[str, Any]] = {}
# job_id -> asyncio.Queue of progress event dicts
_QUEUES: Dict[str, "asyncio.Queue[Dict[str, Any]]"] = {}


def new_job_id() -> str:
    return uuid.uuid4().hex[:12]


def create_job(
    *,
    title: str = "",
    script_text: str = "",
    scenes: Optional[List[Dict[str, Any]]] = None,
    duration_minutes: int = 3,
    mode: str = "topic",
) -> str:
    job_id = new_job_id()
    _JOBS[job_id] = {
        "job_id": job_id,
        "title": title,
        "script_text": script_text,
        "scenes": scenes or [],
        "duration_minutes": duration_minutes,
        "mode": mode,
        "status": "created",          # created | approved | processing | complete | error
        "step": "",
        "percentage": 0,
        "scenes_total": len(scenes or []),
        "scenes_completed": 0,
        "video_path": None,
        "thumbnail_path": None,
        "error": None,
    }
    _QUEUES[job_id] = asyncio.Queue()
    log.info("Created job %s", job_id)
    return job_id


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    return _JOBS.get(job_id)


def update_job(job_id: str, **fields: Any) -> None:
    job = _JOBS.get(job_id)
    if job is None:
        log.warning("update_job: unknown job %s", job_id)
        return
    job.update(fields)


def get_queue(job_id: str) -> Optional["asyncio.Queue[Dict[str, Any]]"]:
    return _QUEUES.get(job_id)


async def emit(job_id: str, **event: Any) -> None:
    """Update job state and push a progress event to the job's SSE queue."""
    update_job(job_id, **{k: v for k, v in event.items() if k in _JOBS.get(job_id, {})})
    queue = _QUEUES.get(job_id)
    if queue is not None:
        await queue.put(event)
    log.debug("Job %s event: %s", job_id, event)
