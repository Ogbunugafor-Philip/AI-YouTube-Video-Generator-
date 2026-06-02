"""Standalone liveness watchdog.

Runs as its OWN process (via cron, every few minutes) so it can still send an
email even when the FastAPI server is down. It pings the local health endpoint
and emails an alert on a down transition, and a recovery email when it comes
back. State is kept in TEMP_DIR/watchdog_state.json so we alert on transitions
only (no repeated spam).

Usage (installed automatically by start.sh as a cron job):
    venv/bin/python backend/watchdog.py
Environment:
    HEALTH_URL   override the health endpoint (default http://127.0.0.1:8003/api/health)
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

# Make the backend package importable when run directly from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402

from core.config import config  # noqa: E402
from core.logger import get_logger  # noqa: E402

log = get_logger("watchdog")

HEALTH_URL = os.getenv("HEALTH_URL", "http://127.0.0.1:8003/api/health")
STATE_FILE = config.TEMP_DIR / "watchdog_state.json"
# Number of consecutive failures before we declare the server down (avoids
# alerting on a single transient blip / restart).
FAIL_THRESHOLD = 2


def _read_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"status": "up", "consecutive_failures": 0}


def _write_state(state: dict) -> None:
    try:
        config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state))
    except OSError as exc:
        log.error("watchdog: could not write state: %s", exc)


def _check() -> bool:
    try:
        resp = httpx.get(HEALTH_URL, timeout=10)
        return resp.status_code == 200
    except Exception as exc:  # noqa: BLE001
        log.warning("watchdog: health check failed: %s", exc)
        return False


def _email(subject: str, body: str) -> None:
    # Imported lazily so a missing dep never crashes the check loop.
    try:
        from services import gmail_service

        gmail_service._send(subject, body)
    except Exception as exc:  # noqa: BLE001
        log.error("watchdog: could not send email: %s", exc)


def main() -> None:
    now = datetime.datetime.now().isoformat(timespec="seconds")
    state = _read_state()
    healthy = _check()

    if healthy:
        if state.get("status") == "down":
            _email(
                "✅ Video Generator is BACK UP",
                f"The server at {HEALTH_URL} is responding again as of {now}.",
            )
            log.info("watchdog: recovery detected, sent recovery email")
        _write_state({"status": "up", "consecutive_failures": 0})
        return

    # Unhealthy.
    failures = int(state.get("consecutive_failures", 0)) + 1
    if state.get("status") != "down" and failures >= FAIL_THRESHOLD:
        _email(
            "⚠️ Video Generator is DOWN",
            f"The server at {HEALTH_URL} failed {failures} consecutive health "
            f"checks (as of {now}). PM2 should be restarting it — investigate if "
            f"this persists.",
        )
        log.error("watchdog: server DOWN after %d failures, alert sent", failures)
        _write_state({"status": "down", "consecutive_failures": failures})
    else:
        _write_state(
            {"status": state.get("status", "up"), "consecutive_failures": failures}
        )


if __name__ == "__main__":
    main()
