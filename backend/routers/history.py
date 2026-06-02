"""Video history library.

Lists every produced video from the persistent store and enriches those that
were uploaded to YouTube with live statistics (pulled fresh on each request).
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from core import stats
from core.logger import get_logger
from services import youtube_service

log = get_logger(__name__)

router = APIRouter(prefix="/api/history", tags=["history"])


def _live_stats(records: List[Dict[str, Any]]):
    """Fetch Data-API stats + Analytics-API watch-time for uploaded records.

    Returns (stats_map, analytics_map). Both keyed by youtube_video_id.
    """
    ids = [r.get("youtube_video_id") for r in records if r.get("youtube_video_id")]
    if not ids:
        return {}, {}
    return youtube_service.get_video_stats(ids), youtube_service.get_analytics(ids)


def _enrich(record: Dict[str, Any], stats_map, analytics_map) -> Dict[str, Any]:
    vid = record.get("youtube_video_id")
    yt = stats_map.get(vid) if vid else None
    an = analytics_map.get(vid) if vid else None
    return {
        "job_id": record.get("job_id"),
        "title": record.get("title", ""),
        "date": record.get("date"),
        "duration_minutes": record.get("duration_minutes", 0),
        "mode": record.get("mode", "topic"),
        "video_style": record.get("video_style", ""),
        "voice": record.get("voice", ""),
        "youtube_video_id": vid,
        "youtube_url": f"https://youtu.be/{vid}" if vid else None,
        # Prefer the YouTube thumbnail (local files for news videos are cleaned
        # up after upload); fall back to the stored local media path.
        "thumbnail_url": (yt or {}).get("thumbnail") or record.get("thumbnail_url"),
        "views": (yt or {}).get("views"),
        "likes": (yt or {}).get("likes"),
        "comments": (yt or {}).get("comments"),
        # Watch-time + retention via the YouTube Analytics API (null if the
        # token lacks the yt-analytics.readonly scope).
        "watch_time_minutes": (an or {}).get("watch_time_minutes"),
        "avg_view_duration_sec": (an or {}).get("avg_view_duration_sec"),
        "avg_view_percentage": (an or {}).get("avg_view_percentage"),
        "estimated_cost": record.get("estimated_cost", 0),
    }


@router.get("")
async def list_history():
    """All produced videos, newest first, enriched with live YouTube stats."""
    records = stats.get_videos()
    stats_map, analytics_map = await asyncio.to_thread(_live_stats, records)
    items = [_enrich(r, stats_map, analytics_map) for r in records]
    items.sort(key=lambda x: x.get("date") or "", reverse=True)
    return {"count": len(items), "videos": items}


@router.get("/{job_id}")
async def history_detail(job_id: str):
    """Detail for one video: full script, scenes, and live YouTube analytics."""
    records = stats.get_videos()
    record = next((r for r in records if r.get("job_id") == job_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown video")
    stats_map, analytics_map = await asyncio.to_thread(_live_stats, [record])
    enriched = _enrich(record, stats_map, analytics_map)
    enriched["script_text"] = record.get("script_text", "")
    enriched["scenes"] = record.get("scenes", [])
    return enriched
