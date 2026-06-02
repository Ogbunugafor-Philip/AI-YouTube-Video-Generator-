"""Pre-production options: voice catalog + previews, and video styles."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core.logger import get_logger
from services import fal_service, styles, voices

log = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["options"])


@router.get("/voice/options")
async def voice_options():
    """Return the selectable voices (id, name, description, preview url)."""
    return {
        "default": voices.DEFAULT_VOICE_ID,
        "voices": [
            {
                "id": v["id"],
                "name": v["name"],
                "description": v["description"],
                "preview_url": f"/api/voice/preview/{v['id']}",
            }
            for v in voices.VOICE_CATALOG
        ],
    }


@router.get("/voice/preview/{voice_id}")
async def voice_preview(voice_id: str) -> FileResponse:
    """Generate (cache) and return a short audio preview for a voice."""
    voice = voices.get_voice(voice_id)
    if voice["id"] != voice_id:
        raise HTTPException(status_code=404, detail="Unknown voice id")
    try:
        path = await fal_service.generate_voice_preview(
            voice["id"], voice["voice"], voices.PREVIEW_TEXT
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return FileResponse(path, media_type="audio/wav")


@router.get("/style/options")
async def style_options():
    """Return the four video styles (id, name, description)."""
    return {
        "styles": [
            {"id": s["id"], "name": s["name"], "description": s["description"]}
            for s in styles.STYLE_CATALOG
        ]
    }
