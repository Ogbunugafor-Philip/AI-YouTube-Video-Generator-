"""Video style catalog.

Each style prepends a prefix to every scene's visual_description before it's
sent to fal.ai, steering the look of all generated clips. ``apply_style`` is a
pure helper used by both the interactive and news pipelines.
"""
from __future__ import annotations

from typing import Dict, List

STYLE_CATALOG: List[Dict[str, str]] = [
    {
        "id": "cinematic",
        "name": "Cinematic",
        "prefix": "cinematic film style, dramatic lighting, shallow depth of field",
        "description": "Filmic look with dramatic lighting and shallow depth of field.",
    },
    {
        "id": "minimalist",
        "name": "Minimalist",
        "prefix": "clean minimal aesthetic, white space, simple geometric visuals",
        "description": "Clean, simple, lots of white space and geometric shapes.",
    },
    {
        "id": "corporate",
        "name": "Corporate",
        "prefix": "professional corporate style, clean modern office aesthetic",
        "description": "Polished, professional, modern office aesthetic.",
    },
    {
        "id": "vibrant",
        "name": "Vibrant",
        "prefix": "vibrant colorful style, bold colors, high energy visuals",
        "description": "Bold colors and high-energy, eye-catching visuals.",
    },
]

_BY_ID = {s["id"]: s for s in STYLE_CATALOG}


def style_prefix(style_id: str) -> str:
    """Return the prompt prefix for a style id, or '' if unknown/blank."""
    s = _BY_ID.get((style_id or "").lower())
    return s["prefix"] if s else ""


def apply_style(scenes: List[Dict], style_id: str) -> List[Dict]:
    """Return a copy of ``scenes`` with the style prefix prepended to each
    visual_description. No-op when the style is blank/unknown."""
    prefix = style_prefix(style_id)
    if not prefix:
        return scenes
    styled = []
    for s in scenes:
        c = dict(s)
        vd = (c.get("visual_description") or "").strip()
        c["visual_description"] = f"{prefix}. {vd}" if vd else prefix
        styled.append(c)
    return styled
