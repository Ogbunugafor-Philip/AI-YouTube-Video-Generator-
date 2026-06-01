"""Cerebras-powered script generation.

Handles turning a topic (or a user write-up) into a narration script, splitting
that script into 30-40 scenes with visual prompts, and generating a title + SEO
metadata. Every Cerebras call is wrapped in error handling and logging.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from cerebras.cloud.sdk import Cerebras

from core.config import config
from core.logger import get_logger
from core import stats

log = get_logger(__name__)

# Words-per-minute target used to size scripts by requested duration.
WORDS_PER_MINUTE = 150


def _client() -> Cerebras:
    if not config.CEREBRAS_API_KEY:
        raise RuntimeError("CEREBRAS_API_KEY is not configured in .env")
    return Cerebras(api_key=config.CEREBRAS_API_KEY)


def _chat(messages: List[Dict[str, str]], *, temperature: float = 0.7,
          max_tokens: int = 4096) -> str:
    """Single chat completion call with logging + cost tracking."""
    try:
        client = _client()
        resp = client.chat.completions.create(
            model=config.CEREBRAS_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        stats.record_api_calls(1, stats.COST_PER_SCRIPT_CALL)
        return resp.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001 - surface a clean error upstream
        log.exception("Cerebras chat completion failed")
        raise RuntimeError(f"Cerebras request failed: {exc}") from exc


def _extract_json(text: str) -> Any:
    """Best-effort extraction of a JSON array/object from model output."""
    text = text.strip()
    # Strip ```json ... ``` fences if present.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # Find the first balanced array or object.
    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    raise ValueError("Could not parse JSON from model output")


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def generate_script(topic: str, duration_minutes: int, mode: str) -> str:
    """Generate a full narration script for ``topic``.

    For ``mode == 'writeup'`` the caller should NOT call this — the user's
    content is used verbatim. This function only runs for topic mode.
    """
    target_words = duration_minutes * WORDS_PER_MINUTE
    log.info("Generating script: topic=%r duration=%dmin (~%d words)",
             topic, duration_minutes, target_words)

    system = (
        "You are a warm, clear, and engaging YouTube narrator with a "
        "Nigerian-friendly voice. You explain AI and technology concepts in a "
        "relatable, encouraging way that a broad African and global audience "
        "can follow. You speak directly to the viewer, use simple vivid "
        "language, and keep energy high without being gimmicky."
    )
    user = (
        f"Write a complete YouTube video narration script about: \"{topic}\".\n\n"
        f"Requirements:\n"
        f"- Approximately {target_words} words (for a {duration_minutes}-minute video).\n"
        f"- Warm, clear, Nigerian-friendly tone explaining AI/tech concepts.\n"
        f"- A strong hook in the first two sentences.\n"
        f"- Logical flow with a clear ending / call to action.\n"
        f"- Output ONLY the spoken narration text (no scene labels, no headers, "
        f"no stage directions)."
    )
    script = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.8,
        max_tokens=max(1024, target_words * 3),
    ).strip()
    if not script:
        raise RuntimeError("Cerebras returned an empty script")
    return script


def split_into_scenes(script_text: str) -> List[Dict[str, Any]]:
    """Split a narration script into 30-40 scenes with visual prompts.

    IMPORTANT: narration_text must be drawn from the supplied script verbatim —
    the model reorganises the text into scenes but must never rewrite it.
    """
    log.info("Splitting script into scenes (%d chars)", len(script_text))
    system = (
        "You are a video director. You split a finished narration script into "
        "sequential scenes for a video. You MUST NOT rewrite, summarise, or alter "
        "the narration wording — only segment it. For each scene you also write a "
        "vivid, detailed visual prompt suitable for an AI text-to-video model."
    )
    user = (
        "Split the following narration script into between 30 and 40 scenes.\n"
        "Rules:\n"
        "- Concatenating every scene's narration_text in order MUST reproduce the "
        "original script (do not change wording).\n"
        "- Each visual_description is a detailed, concrete prompt for an AI video "
        "generator (subject, setting, style, lighting, motion, mood).\n"
        "- Return ONLY a JSON array. Each element: "
        '{"scene_number": int, "narration_text": str, "visual_description": str}.\n\n'
        f"SCRIPT:\n{script_text}"
    )
    raw = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.4,
        max_tokens=8192,
    )
    try:
        data = _extract_json(raw)
    except ValueError as exc:
        log.error("Scene JSON parse failed, falling back to naive split: %s", exc)
        return _fallback_split(script_text)

    scenes: List[Dict[str, Any]] = []
    for i, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue
        scenes.append(
            {
                "scene_number": int(item.get("scene_number", i)),
                "narration_text": str(item.get("narration_text", "")).strip(),
                "visual_description": str(item.get("visual_description", "")).strip(),
            }
        )
    if not scenes:
        return _fallback_split(script_text)
    # Renumber sequentially to guarantee order integrity.
    for i, s in enumerate(scenes, start=1):
        s["scene_number"] = i
    log.info("Produced %d scenes", len(scenes))
    return scenes


def _fallback_split(script_text: str, target: int = 32) -> List[Dict[str, Any]]:
    """Deterministic sentence-based split used if the model output is unusable.

    Preserves the user's wording exactly (critical for write-up mode).
    """
    sentences = re.split(r"(?<=[.!?])\s+", script_text.strip())
    sentences = [s for s in sentences if s]
    if not sentences:
        sentences = [script_text.strip()]
    # Group sentences so we land near `target` scenes.
    n = min(max(len(sentences), 1), max(target, 1))
    per = max(1, len(sentences) // n)
    scenes: List[Dict[str, Any]] = []
    for i in range(0, len(sentences), per):
        chunk = " ".join(sentences[i : i + per]).strip()
        if not chunk:
            continue
        scenes.append(
            {
                "scene_number": len(scenes) + 1,
                "narration_text": chunk,
                "visual_description": (
                    f"Cinematic, high-quality visual illustrating: {chunk[:200]}. "
                    "Modern, clean, vibrant, smooth subtle motion."
                ),
            }
        )
    return scenes


def generate_title(script_text: str) -> str:
    """Generate a catchy YouTube title from the script."""
    log.info("Generating title")
    snippet = script_text[:2000]
    raw = _chat(
        [
            {
                "role": "system",
                "content": "You write irresistible, click-worthy but honest "
                "YouTube titles. Keep them under 70 characters.",
            },
            {
                "role": "user",
                "content": "Write ONE catchy YouTube title for a video with this "
                f"narration. Return only the title text, no quotes.\n\n{snippet}",
            },
        ],
        temperature=0.9,
        max_tokens=64,
    )
    title = raw.strip().strip('"').splitlines()[0] if raw.strip() else "Untitled Video"
    return title[:100]


def generate_seo(title: str, script_text: str) -> Dict[str, Any]:
    """Generate a YouTube description and exactly 15 tags."""
    log.info("Generating SEO metadata")
    snippet = script_text[:2500]
    raw = _chat(
        [
            {
                "role": "system",
                "content": "You are a YouTube SEO expert.",
            },
            {
                "role": "user",
                "content": (
                    "Given this title and narration, produce a JSON object with "
                    'keys "description" (an engaging 2-3 paragraph YouTube '
                    'description) and "tags" (an array of exactly 15 short, '
                    "relevant tag strings). Return ONLY JSON.\n\n"
                    f"TITLE: {title}\n\nNARRATION:\n{snippet}"
                ),
            },
        ],
        temperature=0.6,
        max_tokens=1024,
    )
    try:
        data = _extract_json(raw)
        description = str(data.get("description", "")).strip()
        tags = [str(t).strip() for t in data.get("tags", []) if str(t).strip()]
    except (ValueError, AttributeError) as exc:
        log.error("SEO parse failed, using fallback: %s", exc)
        description = f"{title}\n\n{script_text[:300]}"
        tags = []
    # Guarantee 15 tags.
    while len(tags) < 15:
        tags.append(f"ai video {len(tags) + 1}")
    return {"description": description, "tags": tags[:15]}
