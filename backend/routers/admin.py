"""Admin / stats router."""
from __future__ import annotations

from fastapi import APIRouter

from core import stats
from core.logger import get_logger
from models.schemas import AdminStatsResponse

log = get_logger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsResponse)
async def get_stats() -> AdminStatsResponse:
    """Return aggregate production stats and the full video history."""
    data = stats.get_stats()
    return AdminStatsResponse(**data)
