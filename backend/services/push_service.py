"""Push notifications via ntfy.sh.

Sends a real phone push when an auto-produced draft is ready. Configure by
setting NTFY_TOPIC in .env and subscribing to that topic in the free ntfy app
(https://ntfy.sh) on your phone. If NTFY_TOPIC is unset, pushes are silently
skipped (the email notification still goes out as a fallback).
"""
from __future__ import annotations

from typing import Optional

import httpx

from core.config import config
from core.logger import get_logger

log = get_logger(__name__)


def is_configured() -> bool:
    return bool(config.NTFY_TOPIC)


def send_push(
    title: str,
    message: str,
    *,
    click_url: Optional[str] = None,
    priority: str = "high",
    tags: str = "tv,sparkles",
) -> bool:
    """Send a push notification. Returns True on success, False otherwise.

    Never raises — a failed push must not abort the production pipeline.
    """
    if not is_configured():
        log.info("ntfy push skipped (NTFY_TOPIC not set)")
        return False

    url = f"{config.NTFY_SERVER.rstrip('/')}/{config.NTFY_TOPIC}"
    headers = {
        "Title": title.encode("ascii", "ignore").decode() or "Video Generator",
        "Priority": priority,
        "Tags": tags,
    }
    if click_url:
        headers["Click"] = click_url
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(url, content=message.encode("utf-8"), headers=headers)
            resp.raise_for_status()
        log.info("Push sent via ntfy topic %s", config.NTFY_TOPIC)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("ntfy push failed: %s", exc)
        return False


def send_draft_ready_push(title: str, draft_url: str) -> bool:
    return send_push(
        "✅ Video Draft Ready",
        f"{title}\n\nTap to preview the YouTube draft.",
        click_url=draft_url,
    )
