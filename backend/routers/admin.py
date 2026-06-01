"""Admin / stats router."""
from __future__ import annotations

from fastapi import APIRouter

from core import jobs, stats
from core.logger import get_logger
from models.schemas import AdminStatsResponse

log = get_logger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsResponse)
async def get_stats() -> AdminStatsResponse:
    """Return aggregate production stats, video history, and news automation."""
    data = stats.get_stats()
    # Next scheduled news check comes from the live APScheduler.
    data["next_news_check"] = jobs.next_run_time("news_monitor_job")
    return AdminStatsResponse(**data)


@router.get("/jobs")
async def list_jobs():
    """Return all registered APScheduler jobs and their next run times."""
    info = jobs.jobs_info()
    scheduler = jobs.get_scheduler()
    return {
        "scheduler_running": bool(scheduler and scheduler.running),
        "count": len(info),
        "jobs": info,
    }
