"""Persistent alert store backed by OUTPUT_DIR/alerts.json.

Tracks every breaking-news alert email we send and its lifecycle status:
    pending -> processing -> completed | skipped | error
Used by the Gmail service (writes alerts), the reply checker, and the news
router. Guarded by a lock since the scheduler and API may touch it concurrently.
"""
from __future__ import annotations

import json
import threading
from typing import Any, Dict, List, Optional

from core.config import config
from core.logger import get_logger

log = get_logger(__name__)

_lock = threading.Lock()


def _read() -> List[Dict[str, Any]]:
    path = config.alerts_file
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Failed reading alerts.json, treating as empty: %s", exc)
        return []


def _write(alerts: List[Dict[str, Any]]) -> None:
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = config.alerts_file.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2)
    tmp.replace(config.alerts_file)


def add_alert(story: Dict[str, Any], timestamp: str, status: str = "pending") -> Dict[str, Any]:
    """Add (or refresh) an alert record for a story. Keyed by story_id."""
    with _lock:
        alerts = _read()
        story_id = story.get("story_id")
        record = {
            "story_id": story_id,
            "title": story.get("title", ""),
            "source": story.get("source", ""),
            "viral_score": story.get("viral_score"),
            "relevance_score": story.get("relevance_score"),
            "status": status,
            "timestamp": timestamp,
            "story": story,
        }
        # Replace any existing record with the same story_id.
        alerts = [a for a in alerts if a.get("story_id") != story_id]
        alerts.append(record)
        _write(alerts)
    log.info("Alert stored: %s (%s)", story_id, status)
    return record


def update_status(story_id: str, status: str) -> bool:
    with _lock:
        alerts = _read()
        found = False
        for a in alerts:
            if a.get("story_id") == story_id:
                a["status"] = status
                found = True
        if found:
            _write(alerts)
    if found:
        log.info("Alert %s -> %s", story_id, status)
    else:
        log.warning("update_status: alert %s not found", story_id)
    return found


def get_alert(story_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        for a in _read():
            if a.get("story_id") == story_id:
                return a
    return None


def all_alerts() -> List[Dict[str, Any]]:
    with _lock:
        return _read()


def count_by_status() -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for a in all_alerts():
        counts[a.get("status", "unknown")] = counts.get(a.get("status", "unknown"), 0) + 1
    return counts
