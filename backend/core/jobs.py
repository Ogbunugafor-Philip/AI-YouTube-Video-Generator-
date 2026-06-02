"""In-memory job store + per-job progress event channels.

This is a single-creator personal tool, so an in-process store is sufficient.
Each job tracks its current production state and owns an ``asyncio.Queue`` that
production code pushes progress events onto and the SSE endpoint drains.
"""
from __future__ import annotations

import asyncio
import datetime
import time
import uuid
from pathlib import Path
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


# =========================================================================== #
# Phase 2: Breaking-news automation — scheduled jobs (APScheduler)
# =========================================================================== #
# All service imports are done lazily *inside* the job functions to avoid import
# cycles (services import this module). The scheduler is created on startup.

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # noqa: E402
from apscheduler.triggers.interval import IntervalTrigger  # noqa: E402

_scheduler: Optional[AsyncIOScheduler] = None

NEWS_MONITOR_INTERVAL_HOURS = 3
REPLY_CHECKER_INTERVAL_MINUTES = 5
CLEANUP_INTERVAL_HOURS = 24
TEMP_MAX_AGE_SECONDS = 24 * 3600


async def produce_news_video(story: Dict[str, Any]) -> Dict[str, Any]:
    """Run the full auto-production pipeline for an approved news story.

    Steps: script -> scenes -> title -> seo -> voice -> clips -> assemble ->
    thumbnail -> YouTube draft upload -> draft-ready email. Returns a result dict
    with video_id / draft_url. Raises on failure (caller updates alert status).
    """
    from services import (  # lazy to avoid cycles
        llm_service,
        fal_service,
        ffmpeg_service,
        youtube_service,
        gmail_service,
        push_service,
    )
    from core import stats
    from core.config import config

    # Each auto-production gets its own job_id so its media lives in isolated
    # per-job dirs — concurrent runs never collide and cleanup is exact.
    job_id = story.get("story_id") or new_job_id()
    title = story.get("title", "Breaking AI News")
    summary = story.get("summary") or story.get("title", "")
    duration = int(story.get("recommended_duration", 3))
    log.info("Auto-producing news video: %r (%d min) job=%s", title[:60], duration, job_id)

    # 1-4: scripting (LLM calls are sync — run off the event loop).
    script = await asyncio.to_thread(
        llm_service.generate_script, summary, duration, "news"
    )
    scenes = await asyncio.to_thread(llm_service.split_into_scenes, script)
    gen_title = await asyncio.to_thread(llm_service.generate_title, script)
    seo = await asyncio.to_thread(llm_service.generate_seo, gen_title, script)

    # 5-8: media generation (already async), scoped to this job_id.
    narration = await fal_service.generate_voice(script, job_id=job_id)
    clips = await fal_service.generate_all_clips(scenes, job_id=job_id)
    video_path = await ffmpeg_service.assemble_video(clips, narration, job_id=job_id)
    thumbnail_path = await fal_service.generate_thumbnail(
        gen_title, script, job_id=job_id
    )

    # 9: upload to YouTube. Optionally auto-schedule the draft to publish later.
    publish_at = None
    if config.YOUTUBE_AUTO_SCHEDULE_HOURS > 0:
        publish_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            hours=config.YOUTUBE_AUTO_SCHEDULE_HOURS
        )
    video_id, draft_url = await asyncio.to_thread(
        youtube_service.upload_to_youtube,
        video_path,
        thumbnail_path,
        gen_title,
        seo.get("description", ""),
        seo.get("tags", []),
        publish_at,
    )

    # 10: notify the creator (push + email).
    await asyncio.to_thread(push_service.send_draft_ready_push, gen_title, draft_url)
    await asyncio.to_thread(
        gmail_service.send_draft_ready_notification, gen_title, draft_url
    )

    # Record in stats history.
    stats.record_auto_video()
    stats.record_video(
        job_id=job_id,
        title=gen_title,
        date=datetime.datetime.now().isoformat(timespec="seconds"),
        duration_minutes=duration,
        estimated_cost=round(
            stats.COST_PER_TTS_CALL
            + len(scenes) * (stats.COST_PER_VIDEO_CLIP + stats.COST_PER_IMAGE_CALL)
            + stats.COST_PER_IMAGE_CALL
            + stats.COST_PER_SCRIPT_CALL * 4,
            4,
        ),
    )

    # 11: the upload succeeded — delete this job's produced files from the VPS.
    cleanup_job_files(job_id)

    log.info("News video produced + cleaned up: video_id=%s", video_id)
    return {"video_id": video_id, "draft_url": draft_url, "title": gen_title}


def cleanup_job_files(job_id: str) -> int:
    """Delete a job's per-job temp + output dirs (final video, thumbnail, clips).

    Called after a confirmed YouTube upload so produced media doesn't pile up on
    the VPS. Returns the number of bytes freed. Never raises.
    """
    import shutil
    from core.config import config

    freed = 0
    for base in (config.TEMP_DIR / job_id, config.OUTPUT_DIR / job_id):
        if base.exists():
            try:
                for p in base.glob("**/*"):
                    if p.is_file():
                        freed += p.stat().st_size
                shutil.rmtree(base, ignore_errors=True)
            except OSError as exc:
                log.warning("cleanup_job_files: could not remove %s: %s", base, exc)
    log.info("cleanup_job_files(%s): freed %.2f MB", job_id, freed / (1024 * 1024))
    return freed


async def news_monitor_job() -> None:
    """Every 3h: fetch + score news, email alerts for the top stories."""
    from services import news_service, gmail_service
    from core import stats

    log.info("[news_monitor_job] starting")
    try:
        stories = await asyncio.to_thread(news_service.get_top_stories)
        records = await asyncio.to_thread(gmail_service.send_news_alert, stories)
        stats.record_alert_sent(len(records))
        stats.set_last_news_check(datetime.datetime.now().isoformat(timespec="seconds"))
        log.info(
            "[news_monitor_job] %d stories found, %d alerts sent",
            len(stories), len(records),
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("[news_monitor_job] failed")
        try:
            await asyncio.to_thread(
                gmail_service.send_failure_alert, "news_monitor_job", str(exc)
            )
        except Exception:  # noqa: BLE001
            log.error("[news_monitor_job] could not send failure alert")


async def reply_checker_job() -> None:
    """Every 5min: poll Gmail for YES/NO replies and act on them."""
    from services import gmail_service
    from core import alerts, stats

    log.info("[reply_checker_job] starting")
    try:
        replies = await asyncio.to_thread(gmail_service.check_replies)
    except Exception as exc:  # noqa: BLE001
        log.exception("[reply_checker_job] reply fetch failed: %s", exc)
        return

    for reply in replies:
        story_id = reply.get("story_id")
        decision = reply.get("reply", "").upper()
        alert = alerts.get_alert(story_id) if story_id else None
        if not alert:
            log.warning("[reply_checker_job] no alert for story_id=%s", story_id)
            continue

        stats.record_reply(decision)

        if decision == "YES":
            alerts.update_status(story_id, "processing")
            try:
                await produce_news_video(alert["story"])
                alerts.update_status(story_id, "completed")
            except Exception as exc:  # noqa: BLE001
                log.exception("[reply_checker_job] production failed for %s", story_id)
                alerts.update_status(story_id, "error")
                try:
                    await asyncio.to_thread(
                        gmail_service.send_failure_alert,
                        f"production for story {story_id}", str(exc),
                    )
                except Exception:  # noqa: BLE001
                    pass
        else:  # NO
            alerts.update_status(story_id, "skipped")


async def cleanup_job() -> None:
    """Every 24h: delete TEMP_DIR files older than 24h; log storage freed."""
    from core.config import config

    log.info("[cleanup_job] starting")
    freed = 0
    removed = 0
    now = time.time()
    try:
        for path in Path(config.TEMP_DIR).glob("**/*"):
            if path.is_file() and (now - path.stat().st_mtime) > TEMP_MAX_AGE_SECONDS:
                size = path.stat().st_size
                try:
                    path.unlink()
                    freed += size
                    removed += 1
                except OSError as exc:
                    log.warning("[cleanup_job] could not delete %s: %s", path, exc)
        log.info("[cleanup_job] removed %d files, freed %.2f MB",
                 removed, freed / (1024 * 1024))
    except Exception:  # noqa: BLE001
        log.exception("[cleanup_job] failed")


def start_scheduler() -> AsyncIOScheduler:
    """Create + start the APScheduler with all three jobs. Idempotent."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        news_monitor_job,
        IntervalTrigger(hours=NEWS_MONITOR_INTERVAL_HOURS),
        id="news_monitor_job",
        name="News monitor (every 3h)",
        replace_existing=True,
        # Kick off shortly after boot so there's an initial run.
        next_run_time=datetime.datetime.now() + datetime.timedelta(seconds=30),
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        reply_checker_job,
        IntervalTrigger(minutes=REPLY_CHECKER_INTERVAL_MINUTES),
        id="reply_checker_job",
        name="Reply checker (every 5min)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        cleanup_job,
        IntervalTrigger(hours=CLEANUP_INTERVAL_HOURS),
        id="cleanup_job",
        name="Temp cleanup (every 24h)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    log.info("APScheduler started with jobs: %s",
             [j.id for j in _scheduler.get_jobs()])
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("APScheduler shut down")
    _scheduler = None


def get_scheduler() -> Optional[AsyncIOScheduler]:
    return _scheduler


def jobs_info() -> List[Dict[str, Any]]:
    """Return registered jobs and their next run times (for admin/testing)."""
    if _scheduler is None:
        return []
    info = []
    for job in _scheduler.get_jobs():
        info.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat()
                if job.next_run_time else None,
            }
        )
    return info


def next_run_time(job_id: str) -> Optional[str]:
    if _scheduler is None:
        return None
    job = _scheduler.get_job(job_id)
    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None
