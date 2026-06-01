"""Lightweight persistent stats tracking, stored as JSON in OUTPUT_DIR/stats.json.

Tracks every produced video plus a running tally of API calls and estimated
cost. Concurrency is guarded with a simple lock since this is a single-process
personal tool.
"""
from __future__ import annotations

import json
import threading
from typing import Any, Dict, List

from core.config import config
from core.logger import get_logger

log = get_logger(__name__)

_lock = threading.Lock()

# Rough per-call cost estimates (USD). Tunable; used only for the admin dashboard.
COST_PER_SCRIPT_CALL = 0.002
COST_PER_VIDEO_CLIP = 0.05
COST_PER_TTS_CALL = 0.02
COST_PER_IMAGE_CALL = 0.01

_DEFAULT: Dict[str, Any] = {
    "total_api_calls": 0,
    "estimated_total_cost": 0.0,
    "videos": [],
    # --- Phase 2: breaking-news automation counters ---
    "news_alerts_sent": 0,
    "yes_replies": 0,
    "no_replies": 0,
    "auto_videos": 0,
    "last_news_check": None,
}


def _read() -> Dict[str, Any]:
    path = config.stats_file
    if not path.exists():
        return json.loads(json.dumps(_DEFAULT))
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Backfill any missing keys.
        for k, v in _DEFAULT.items():
            data.setdefault(k, v)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Failed to read stats file, resetting: %s", exc)
        return json.loads(json.dumps(_DEFAULT))


def _write(data: Dict[str, Any]) -> None:
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = config.stats_file.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(config.stats_file)


def record_api_calls(count: int = 1, cost: float = 0.0) -> None:
    """Increment the global API-call and cost counters."""
    with _lock:
        data = _read()
        data["total_api_calls"] += count
        data["estimated_total_cost"] = round(data["estimated_total_cost"] + cost, 4)
        _write(data)


def record_video(
    *, job_id: str, title: str, date: str, duration_minutes: int, estimated_cost: float
) -> None:
    with _lock:
        data = _read()
        data["videos"].append(
            {
                "job_id": job_id,
                "title": title,
                "date": date,
                "duration_minutes": duration_minutes,
                "estimated_cost": round(estimated_cost, 4),
            }
        )
        _write(data)
    log.info("Recorded produced video %s (%s)", job_id, title)


def record_alert_sent(count: int = 1) -> None:
    with _lock:
        data = _read()
        data["news_alerts_sent"] += count
        _write(data)


def record_reply(decision: str) -> None:
    key = "yes_replies" if decision.upper() == "YES" else "no_replies"
    with _lock:
        data = _read()
        data[key] += 1
        _write(data)


def record_auto_video() -> None:
    with _lock:
        data = _read()
        data["auto_videos"] += 1
        _write(data)


def set_last_news_check(timestamp: str) -> None:
    with _lock:
        data = _read()
        data["last_news_check"] = timestamp
        _write(data)


def get_news_stats() -> Dict[str, Any]:
    with _lock:
        data = _read()
    return {
        "news_alerts_sent": data.get("news_alerts_sent", 0),
        "yes_replies": data.get("yes_replies", 0),
        "no_replies": data.get("no_replies", 0),
        "auto_videos": data.get("auto_videos", 0),
        "last_news_check": data.get("last_news_check"),
    }


def get_stats() -> Dict[str, Any]:
    with _lock:
        data = _read()
    videos: List[Dict[str, Any]] = data.get("videos", [])
    return {
        "total_videos": len(videos),
        "total_api_calls": data.get("total_api_calls", 0),
        "estimated_total_cost": round(data.get("estimated_total_cost", 0.0), 4),
        "videos": videos,
        "news_alerts_sent": data.get("news_alerts_sent", 0),
        "yes_replies": data.get("yes_replies", 0),
        "no_replies": data.get("no_replies", 0),
        "auto_videos": data.get("auto_videos", 0),
        "last_news_check": data.get("last_news_check"),
    }
