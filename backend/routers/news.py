"""Breaking-news automation router.

Manual endpoints for testing the news pipeline without waiting for the
scheduler: fetch + score stories, send a test alert, list stored alerts, and
trigger production for a specific story.
"""
from __future__ import annotations

import asyncio
import datetime
import hashlib

from fastapi import APIRouter, HTTPException

from core import alerts, jobs
from core.logger import get_logger
from services import gmail_service, news_service

log = get_logger(__name__)

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/latest")
async def latest():
    """Manually fetch + score news and return the qualifying top stories.

    Runs the (blocking) fetch/score work in a thread so the event loop is free.
    """
    try:
        stories = await asyncio.to_thread(news_service.get_top_stories)
    except Exception as exc:  # noqa: BLE001
        log.exception("news/latest failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"count": len(stories), "stories": stories}


@router.post("/test-alert")
async def test_alert():
    """Send a test alert email with a dummy story to confirm the email flow."""
    now = datetime.datetime.now()
    dummy_id = "test" + hashlib.sha1(now.isoformat().encode()).hexdigest()[:8]
    dummy = {
        "story_id": dummy_id,
        "title": "TEST — OpenAI announces breakthrough reasoning model",
        "summary": (
            "This is a test alert from your AI YouTube Video Generator. If you "
            "received this email, your Gmail SMTP configuration is working. "
            "Reply YES to test the auto-production flow, or NO to skip."
        ),
        "url": "https://example.com/test-story",
        "source": "Test Harness",
        "published_date": now.isoformat(timespec="seconds"),
        "viral_score": 9,
        "relevance_score": 9,
        "estimated_views": "high",
        "recommended_duration": 3,
        "suggested_title": "BREAKING: The AI Model That Changes Everything",
    }
    try:
        records = await asyncio.to_thread(gmail_service.send_news_alert, [dummy])
    except Exception as exc:  # noqa: BLE001
        log.exception("test-alert failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not records:
        raise HTTPException(status_code=502, detail="Alert email was not sent")
    return {
        "status": "sent",
        "to": gmail_service.config.GMAIL_ADDRESS,
        "story_id": dummy_id,
    }


@router.get("/alerts")
async def list_alerts():
    """Return all stored alerts (story_id, title, status, timestamp, ...)."""
    records = alerts.all_alerts()
    # Most recent first.
    records = sorted(records, key=lambda a: a.get("timestamp", ""), reverse=True)
    return {"count": len(records), "alerts": records}


@router.post("/trigger/{story_id}")
async def trigger(story_id: str):
    """Manually trigger production for a stored story, bypassing email."""
    alert = alerts.get_alert(story_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Unknown story_id")
    alerts.update_status(story_id, "processing")

    async def _run():
        try:
            await jobs.produce_news_video(alert["story"])
            alerts.update_status(story_id, "completed")
        except Exception:  # noqa: BLE001
            log.exception("Manual trigger production failed for %s", story_id)
            alerts.update_status(story_id, "error")

    asyncio.create_task(_run())
    return {"status": "processing", "story_id": story_id}
