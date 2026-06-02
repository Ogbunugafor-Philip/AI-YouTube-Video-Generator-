"""Firebase Cloud Messaging push notifications (FCM HTTP v1 via firebase-admin).

Credentials come ONLY from the service-account JSON whose path is in the
FIREBASE_SERVICE_ACCOUNT_PATH env var — nothing is hardcoded here. If Firebase
isn't configured, every send is a no-op (logged) so the pipeline never breaks.

Public API:
    send_push(device_token, title, body, data={})
    send_breaking_news_push(device_token, headline, story_id)
    send_draft_ready_push(device_token, video_title, youtube_draft_url)
Broadcast helpers (used by the scheduler / pipeline) push to every registered
device and prune tokens FCM reports as unregistered:
    broadcast_breaking_news(headline, story_id)
    broadcast_draft_ready(video_title, youtube_draft_url)
"""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from core import devices
from core.config import config
from core.logger import get_logger

log = get_logger(__name__)

_init_lock = threading.Lock()
_app = None  # firebase_admin app singleton


def _ensure_app():
    """Initialise the firebase_admin app once, from the service-account file."""
    global _app
    if _app is not None:
        return _app
    with _init_lock:
        if _app is not None:
            return _app
        path = config.firebase_service_account_file
        if not config.FIREBASE_SERVICE_ACCOUNT_PATH or not path.exists():
            log.warning("FCM not configured (service account file missing: %s)", path)
            return None
        try:
            import firebase_admin
            from firebase_admin import credentials

            if firebase_admin._apps:  # already initialised elsewhere
                _app = firebase_admin.get_app()
            else:
                cred = credentials.Certificate(str(path))
                _app = firebase_admin.initialize_app(cred)
            log.info("Firebase Admin initialised (project=%s)", config.FIREBASE_PROJECT_ID)
        except Exception as exc:  # noqa: BLE001
            log.exception("Failed to initialise Firebase Admin: %s", exc)
            _app = None
    return _app


def is_configured() -> bool:
    return bool(config.FIREBASE_SERVICE_ACCOUNT_PATH) and config.firebase_service_account_file.exists()


def _str_data(data: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """FCM data values must be strings."""
    return {str(k): str(v) for k, v in (data or {}).items()}


def send_push(
    device_token: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Send a single notification. Returns the FCM message id, or None.

    Never raises. On an unregistered/invalid token the token is pruned.
    """
    app = _ensure_app()
    if app is None or not device_token:
        return None
    try:
        from firebase_admin import messaging

        message = messaging.Message(
            token=device_token,
            notification=messaging.Notification(title=title, body=body),
            data=_str_data(data),
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    title=title,
                    body=body,
                    channel_id="default",
                    # Lets the app attach action buttons (YES/NO) by category.
                    click_action=(data or {}).get("category"),
                ),
            ),
        )
        msg_id = messaging.send(message)
        log.info("FCM push sent (%s): %s", (data or {}).get("type", "generic"), msg_id)
        return msg_id
    except Exception as exc:  # noqa: BLE001
        name = type(exc).__name__
        if name in ("UnregisteredError", "SenderIdMismatchError"):
            log.info("Pruning invalid FCM token (%s)", name)
            devices.remove_token(device_token)
        else:
            log.error("FCM send failed: %s", exc)
        return None


def send_breaking_news_push(
    device_token: str, headline: str, story_id: str
) -> Optional[str]:
    """Push a breaking-news alert carrying a YES/NO action payload."""
    return send_push(
        device_token,
        title="🔴 Breaking AI News",
        body=headline,
        data={
            "type": "breaking_news",
            "story_id": story_id,
            "category": "breaking_news",
            "actions": "YES,NO",
        },
    )


def send_draft_ready_push(
    device_token: str, video_title: str, youtube_draft_url: str
) -> Optional[str]:
    """Push a draft-ready notification with a preview deep-link."""
    return send_push(
        device_token,
        title="✅ Video Draft Ready",
        body=video_title,
        data={
            "type": "draft_ready",
            "category": "draft_ready",
            "draft_url": youtube_draft_url,
            "title": video_title,
        },
    )


# --------------------------------------------------------------------------- #
# Broadcast helpers — push to every registered device.
# --------------------------------------------------------------------------- #
def broadcast_breaking_news(headline: str, story_id: str) -> int:
    sent = 0
    for token in devices.all_tokens():
        if send_breaking_news_push(token, headline, story_id):
            sent += 1
    log.info("Breaking-news push broadcast to %d device(s)", sent)
    return sent


def broadcast_draft_ready(video_title: str, youtube_draft_url: str) -> int:
    sent = 0
    for token in devices.all_tokens():
        if send_draft_ready_push(token, video_title, youtube_draft_url):
            sent += 1
    log.info("Draft-ready push broadcast to %d device(s)", sent)
    return sent
