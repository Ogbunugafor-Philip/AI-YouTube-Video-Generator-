"""fal.ai-powered script generation.

Handles turning a topic (or a user write-up) into a narration script, splitting
that script into 30-40 scenes with visual prompts, and generating a title + SEO
metadata. Every model call is wrapped in error handling and logging.

Backed by fal.ai's ``fal-ai/any-llm`` endpoint via the ``fal_client`` SDK, using
``FAL_LLM_CHAT_MODEL`` as the model. fal_client authenticates from the FAL_KEY
environment variable (mirrored from FAL_API_KEY in core.config).

The public API is unchanged from previous LLM backends:
    generate_script(topic, duration_minutes, mode)
    split_into_scenes(script_text)
    generate_title(script_text)
    generate_seo(title, script_text)
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import fal_client

from core.config import config
from core.logger import get_logger
from core import stats

log = get_logger(__name__)

# Words-per-minute target used to size scripts by requested duration.
WORDS_PER_MINUTE = 150

# fal.ai LLM application id (any-llm exposes many underlying chat models).
FAL_LLM_APP = "fal-ai/any-llm"


def _messages_to_prompt(messages: List[Dict[str, str]]) -> tuple[str, str]:
    """Split chat messages into (system_prompt, user_prompt) for any-llm.

    any-llm takes a single ``prompt`` plus optional ``system_prompt``. We
    concatenate all system messages and all user/assistant messages respectively
    so the existing role-based prompts carry over unchanged.
    """
    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    user_parts = [m["content"] for m in messages if m.get("role") != "system"]
    return "\n\n".join(system_parts).strip(), "\n\n".join(user_parts).strip()


def _chat(messages: List[Dict[str, str]], *, temperature: float = 0.7,
          max_tokens: int = 4096) -> str:
    """Single chat completion call with logging + cost tracking.

    Calls ``fal-ai/any-llm`` with the configured ``FAL_LLM_CHAT_MODEL``.
    """
    if not config.FAL_API_KEY:
        raise RuntimeError("FAL_API_KEY is not configured in .env")

    system_prompt, user_prompt = _messages_to_prompt(messages)
    arguments: Dict[str, Any] = {
        "model": config.FAL_LLM_CHAT_MODEL,
        "prompt": user_prompt,
        # Give long structured outputs (scene JSON) enough room to finish.
        "max_tokens": max_tokens,
    }
    if system_prompt:
        arguments["system_prompt"] = system_prompt

    try:
        result = fal_client.subscribe(FAL_LLM_APP, arguments=arguments)
        stats.record_api_calls(1, stats.COST_PER_SCRIPT_CALL)
        if isinstance(result, dict):
            if result.get("error"):
                raise RuntimeError(str(result["error"]))
            return (result.get("output") or result.get("text") or "").strip()
        return ""
    except Exception as exc:  # noqa: BLE001
        log.exception("fal.ai LLM request failed")
        raise RuntimeError(f"fal.ai LLM request failed: {exc}") from exc


def _extract_json(text: str) -> Any:
    """Best-effort extraction of a JSON array/object from model output.

    Strategy: strip markdown/backticks -> try ``json.loads`` directly -> regex
    extract the first balanced array/object (tolerating trailing commas).
    Raises ValueError if nothing parses.
    """
    if not text or not text.strip():
        raise ValueError("empty model output")
    text = text.strip()

    # 1) Strip markdown code fences / stray backticks.
    if "```" in text:
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        text = (fence.group(1) if fence else text.replace("```", "")).strip()
    text = text.strip("`").strip()

    # 2) Try a direct parse of the whole (cleaned) string first.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3) Regex-extract the first JSON array (preferred) or object, and retry,
    #    tolerating trailing commas before closing brackets.
    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            for attempt in (candidate, re.sub(r",\s*([\]}])", r"\1", candidate)):
                try:
                    return json.loads(attempt)
                except json.JSONDecodeError:
                    continue
    raise ValueError("Could not parse JSON from model output")


def _salvage_objects(text: str) -> List[Dict[str, Any]]:
    """Extract every complete top-level ``{...}`` JSON object from ``text``.

    Scans balanced braces while respecting strings/escapes, so it survives
    markdown code fences, leading/trailing prose, and a truncated final object
    (the incomplete tail is simply dropped). Returns the parsed objects in order.
    """
    objects: List[Dict[str, Any]] = []
    depth = 0
    start: int | None = None
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        objects.append(json.loads(text[start : i + 1]))
                    except json.JSONDecodeError:
                        pass
                    start = None
    return objects


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def generate_script(topic: str, duration_minutes: int, mode: str) -> str:
    """Generate a full narration script for ``topic``.

    For ``mode == 'writeup'`` the caller should NOT call this — the user's
    content is used verbatim. This function only runs for topic / news modes.
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
    if mode == "news":
        # Breaking-news framing for auto-produced stories.
        system = (
            "You are a sharp, trustworthy AI & tech news presenter with a warm, "
            "clear, Nigerian-friendly voice. You break down breaking technology "
            "news so any viewer understands why it matters, staying factual and "
            "engaging without sensationalism."
        )
        user = (
            f"Write a complete breaking-news YouTube narration script about this "
            f"story:\n\n\"{topic}\"\n\n"
            f"Requirements:\n"
            f"- Approximately {target_words} words (for a {duration_minutes}-minute video).\n"
            f"- Open with an urgent, curiosity-driven hook.\n"
            f"- Explain what happened, why it matters, and what it means going forward.\n"
            f"- Warm, clear, Nigerian-friendly news-presenter tone.\n"
            f"- End with a call to subscribe for more AI/tech news.\n"
            f"- Output ONLY the spoken narration text (no labels or stage directions)."
        )
    else:
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
        raise RuntimeError("fal.ai LLM returned an empty script")
    return script


def split_into_scenes(script_text: str) -> List[Dict[str, Any]]:
    """Split a narration script into 30-40 scenes with visual prompts.

    IMPORTANT: narration_text must be drawn from the supplied script verbatim —
    the model reorganises the text into scenes but must never rewrite it.
    """
    log.info("Splitting script into scenes (%d chars)", len(script_text))
    system = (
        "You are a professional video director and AI prompt engineer. You split a "
        "finished narration script into sequential video scenes. You MUST NOT "
        "rewrite, summarise, or alter the narration wording — only segment it. You "
        "ALWAYS respond with a single valid JSON array and absolutely nothing else."
    )
    user = (
        "Split the narration script below into between 30 and 40 sequential scenes.\n\n"
        "STRICT OUTPUT RULES:\n"
        "- Return ONLY a JSON array. No prose, no explanation, no markdown, no code "
        "fences, no backticks.\n"
        "- The FIRST character of your response must be '[' and the LAST must be ']'.\n"
        "- Each array element is an object with EXACTLY these three fields:\n"
        '    "scene_number": integer starting at 1, increasing by 1;\n'
        '    "narration_text": string taken VERBATIM from the script (never reworded);\n'
        '    "visual_description": string.\n'
        "- Concatenating every narration_text in order MUST reproduce the original "
        "script exactly (do not change, add, or drop any words).\n"
        "- visual_description must be a RICH, SPECIFIC, CINEMATIC prompt for an AI "
        "video generator: name the subject, the setting/location, lighting, camera "
        "angle, mood and style. Avoid generic templates.\n"
        '- Example of a good visual_description: "A sleek Nigerian bank interior in '
        "Lagos, modern teller stations with holographic AI displays, well-dressed "
        'bank staff assisting customers, warm lighting, 4K cinematic quality".\n\n'
        f"SCRIPT:\n{script_text}"
    )
    raw = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.3,
        max_tokens=8192,
    )

    # Robust parse, in order of preference:
    #   1) json.loads / regex array extraction (clean output),
    #   2) brace-scan salvage of complete objects (handles fences/trailing/truncation),
    #   3) deterministic sentence splitter (last resort, with a warning).
    data: Any = None
    try:
        data = _extract_json(raw)
    except ValueError as exc:
        log.warning("Scene array parse failed (%s); attempting object salvage", exc)

    if not isinstance(data, list):
        salvaged = _salvage_objects(raw)
        if salvaged:
            log.info("Salvaged %d scene objects from non-array output", len(salvaged))
            data = salvaged
        else:
            log.warning("⚠ Scene JSON parse FAILED. Falling back to sentence "
                        "splitter. Raw model output was:\n%s", raw[:1500])
            return _fallback_split(script_text)

    scenes: List[Dict[str, Any]] = []
    for i, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue
        narration = str(item.get("narration_text", "")).strip()
        if not narration:
            continue
        scenes.append(
            {
                "scene_number": int(item.get("scene_number", i)),
                "narration_text": narration,
                "visual_description": str(item.get("visual_description", "")).strip(),
            }
        )
    if not scenes:
        log.warning("⚠ Parsed JSON produced no usable scenes. Falling back to "
                    "sentence splitter. Raw output:\n%s", raw[:1500])
        return _fallback_split(script_text)
    # Renumber sequentially to guarantee order integrity.
    for i, s in enumerate(scenes, start=1):
        s["scene_number"] = i
    log.info("Produced %d scenes from LLM JSON", len(scenes))
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


def chat(messages: List[Dict[str, str]], *, temperature: float = 0.7,
         max_tokens: int = 4096) -> str:
    """Public chat helper so other services (e.g. news scoring) can reuse the LLM."""
    return _chat(messages, temperature=temperature, max_tokens=max_tokens)


def parse_json(text: str) -> Any:
    """Public JSON extractor mirroring the internal helper."""
    return _extract_json(text)


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
