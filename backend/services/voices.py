"""Voice catalog for narration (fal-ai/playai-tts).

A curated set of distinct AI voice styles the user can pick from before
production. Each entry maps a friendly id + description to the exact ``voice``
string the playai-tts model expects. ``DEFAULT_VOICE_ID`` is used when the user
skips selection (it matches the voice Phase 1/2 already used).
"""
from __future__ import annotations

from typing import Dict, List, Optional

# Short sample line used to generate voice previews.
PREVIEW_TEXT = (
    "Hello! This is a quick preview of how your video narration will sound."
)

# Voices are fal-ai/kokoro voice codes (American voice set available on the
# account). DEFAULT_VOICE_ID matches the narration default used elsewhere.
DEFAULT_VOICE_ID = "heart"

VOICE_CATALOG: List[Dict[str, str]] = [
    {
        "id": "heart",
        "name": "Aria",
        "voice": "af_heart",
        "description": "Warm and conversational — friendly female (default).",
    },
    {
        "id": "adam",
        "name": "Adam",
        "voice": "am_adam",
        "description": "Authoritative and clear — deep, confident male.",
    },
    {
        "id": "bella",
        "name": "Bella",
        "voice": "af_bella",
        "description": "Energetic and youthful — bright, expressive female.",
    },
    {
        "id": "onyx",
        "name": "Onyx",
        "voice": "am_onyx",
        "description": "Smooth and professional — polished, deep male.",
    },
    {
        "id": "nova",
        "name": "Nova",
        "voice": "af_nova",
        "description": "Friendly and bright — clear, upbeat female.",
    },
]

_BY_ID = {v["id"]: v for v in VOICE_CATALOG}


def get_voice(voice_id: Optional[str]) -> Dict[str, str]:
    """Return the catalog entry for ``voice_id`` (falls back to the default)."""
    return _BY_ID.get(voice_id or "", _BY_ID[DEFAULT_VOICE_ID])


def resolve_voice_string(voice_id: Optional[str]) -> str:
    """Return the playai-tts ``voice`` string for a given id (or default)."""
    return get_voice(voice_id)["voice"]
