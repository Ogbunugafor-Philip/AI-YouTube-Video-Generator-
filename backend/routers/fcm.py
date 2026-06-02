"""FCM device registration + push testing (mobile app)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core import devices
from core.logger import get_logger
from models.schemas import FcmRegisterRequest

import push_fcm_service

log = get_logger(__name__)

router = APIRouter(prefix="/api/fcm", tags=["fcm"])


@router.post("/register-device")
async def register_device(req: FcmRegisterRequest):
    """Store (or refresh) an FCM device token. Idempotent per device_id."""
    if not req.device_token or not req.device_id:
        raise HTTPException(status_code=400, detail="device_token and device_id required")
    record = devices.register(req.device_token, req.device_id, req.platform)
    return {"status": "ok", "device_id": record["device_id"]}


@router.get("/devices")
async def list_devices():
    """List registered devices (tokens masked) — for debugging."""
    out = []
    for d in devices.all_devices():
        tok = d.get("device_token", "")
        out.append(
            {
                "device_id": d.get("device_id"),
                "platform": d.get("platform"),
                "token_preview": (tok[:12] + "…") if tok else "",
                "updated_at": d.get("updated_at"),
            }
        )
    return {"count": len(out), "devices": out, "fcm_configured": push_fcm_service.is_configured()}


@router.post("/test-push")
async def test_push():
    """Send a test push to all registered devices (confirms FCM wiring)."""
    sent = 0
    for token in devices.all_tokens():
        if push_fcm_service.send_push(
            token,
            "🔔 VidGen Studio",
            "Push notifications are working!",
            data={"type": "test"},
        ):
            sent += 1
    return {"status": "sent", "devices": sent, "fcm_configured": push_fcm_service.is_configured()}
