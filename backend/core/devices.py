"""Persistent FCM device-token registry, stored as OUTPUT_DIR/devices.json.

One record per device_id; registering an existing device_id replaces its token
(handles app reinstalls / token refresh). Guarded by a lock since the scheduler
and API may touch it concurrently.
"""
from __future__ import annotations

import datetime
import json
import threading
from typing import Any, Dict, List

from core.config import config
from core.logger import get_logger

log = get_logger(__name__)

_lock = threading.Lock()


def _read() -> List[Dict[str, Any]]:
    path = config.devices_file
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Failed reading devices.json, treating as empty: %s", exc)
        return []


def _write(devices: List[Dict[str, Any]]) -> None:
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = config.devices_file.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(devices, f, indent=2)
    tmp.replace(config.devices_file)


def register(device_token: str, device_id: str, platform: str = "android") -> Dict[str, Any]:
    """Register (or update) a device. Keyed by device_id."""
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    with _lock:
        devices = _read()
        record = {
            "device_id": device_id,
            "device_token": device_token,
            "platform": platform,
            "updated_at": timestamp,
        }
        devices = [d for d in devices if d.get("device_id") != device_id]
        # Also drop any other device that happens to share this exact token.
        devices = [d for d in devices if d.get("device_token") != device_token]
        devices.append(record)
        _write(devices)
    log.info("Registered device %s (%s)", device_id, platform)
    return record


def all_tokens() -> List[str]:
    return [d["device_token"] for d in _read() if d.get("device_token")]


def all_devices() -> List[Dict[str, Any]]:
    return _read()


def remove_token(device_token: str) -> None:
    with _lock:
        devices = _read()
        kept = [d for d in devices if d.get("device_token") != device_token]
        if len(kept) != len(devices):
            _write(kept)
            log.info("Removed stale device token")
