"""fal.ai-powered script generation.

Handles turning a topic (or a user write-up) into a narration script, splitting
that script into duration-bounded scenes (<=17) with coherent visual prompts,
and generating a title + SEO metadata. Every model call is wrapped in error
handling and logging.

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


def _max_scenes(duration_minutes: int) -> int:
    """Maximum scene count for a video duration. Hard cap of 17 scenes.

    3 min -> 10, 4 min -> 13, 5 min (and above) -> 17.
    """
    try:
        d = int(duration_minutes)
    except (TypeError, ValueError):
        d = 3
    if d <= 3:
        return 10
    if d == 4:
        return 13
    return 17  # 5+ minutes, never more than 17


def _segment_narration(script_text: str, n: int) -> List[str]:
    """Split the script into exactly ``n`` contiguous, roughly-equal segments.

    Every word is covered (verbatim, in order), segments are near-equal in
    length, and the final segment always ends on the last word of the script.
    Splits on sentence boundaries when there are enough sentences, otherwise on
    words. Returns fewer than ``n`` only when the script has fewer than ``n``
    words.
    """
    text = re.sub(r"\s+", " ", (script_text or "").strip())
    if not text:
        return []
    n = max(1, int(n))
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    units = sentences if len(sentences) >= n else text.split()
    n = min(n, len(units)) or 1
    total = len(units)
    segments: List[str] = []
    for k in range(n):
        start = (k * total) // n
        end = ((k + 1) * total) // n
        seg = " ".join(units[start:end]).strip()
        if seg:
            segments.append(seg)
    return segments


def split_into_scenes(
    script_text: str, duration_minutes: int = 3
) -> List[Dict[str, Any]]:
    """Split a narration script into duration-bounded scenes with clean visuals.

    Scene count is capped by duration (3min->10, 4min->13, 5min->17, hard cap
    17). Narration is segmented deterministically so every word is covered,
    segments are roughly equal, and the last scene ends on the last word. Each
    visual description is validated for coherent English (10-50 words) and any
    failure is regenerated automatically before returning.
    """
    n = _max_scenes(duration_minutes)
    log.info(
        "Splitting script into <=%d scenes (%d chars, %s min)",
        n, len(script_text), duration_minutes,
    )

    segments = _segment_narration(script_text, n)
    if not segments:
        return []
    descriptions = _generate_visual_descriptions(segments)

    scenes: List[Dict[str, Any]] = []
    for i, (narration, desc) in enumerate(zip(segments, descriptions), start=1):
        scenes.append(
            {
                "scene_number": i,
                "narration_text": narration,
                "visual_description": desc,
            }
        )
    log.info("Produced %d scenes (cap %d)", len(scenes), n)
    return scenes


# --------------------------------------------------------------------------- #
# Visual description generation + coherence validation (anti-gibberish)
# --------------------------------------------------------------------------- #
_DESC_MIN_WORDS = 10
_DESC_MAX_WORDS = 50


def _clean_desc(text: str) -> str:
    """Strip fences/quotes/labels, collapse whitespace, cap at MAX words."""
    t = (text or "").strip()
    if "```" in t:
        t = re.sub(r"```(?:json)?", "", t).replace("```", "")
    t = t.strip().strip('"').strip("'").strip()
    # Drop a leading "Scene 3:" / "1." style label if the model added one.
    t = re.sub(r"^\s*(scene\s*\d+\s*[:\-\.]|\d+\s*[:\-\.])\s*", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    words = t.split()
    if len(words) > _DESC_MAX_WORDS:
        t = " ".join(words[:_DESC_MAX_WORDS]).rstrip(",;:- ") + "."
    return t


def _is_coherent_description(desc: str) -> bool:
    """Validate a visual description: 10-50 words of coherent English.

    Rejects gibberish — random consonant runs, over-long tokens, or mostly
    non-alphabetic content.
    """
    if not desc or not desc.strip():
        return False
    n_words = len(desc.split())
    if n_words < _DESC_MIN_WORDS or n_words > _DESC_MAX_WORDS:
        return False
    letters = re.findall(r"[A-Za-z']+", desc)
    if len(letters) < 8:
        return False

    def _wordish(w: str) -> bool:
        # Real English-ish word: sane length and contains a vowel.
        return 2 <= len(w) <= 18 and bool(re.search(r"[aeiouy]", w, re.I))

    good = sum(1 for w in letters if _wordish(w))
    return (good / len(letters)) >= 0.75


def _fallback_description(narration: str) -> str:
    """Deterministic, always-valid cinematic description from the narration."""
    subject = " ".join(
        re.sub(r"[^A-Za-z0-9 ]", " ", narration).split()[:10]
    ).strip()
    if not subject:
        subject = "the topic being narrated"
    return (
        f"Cinematic wide establishing shot illustrating {subject}, with natural "
        "lighting, clear focused composition and smooth subtle camera motion."
    )


def _regenerate_description(narration: str, attempts: int = 3) -> str:
    """Regenerate one coherent visual description, with a safe fallback."""
    for _ in range(attempts):
        try:
            raw = _chat(
                [
                    {
                        "role": "system",
                        "content": "You are a cinematographer. You reply with ONE "
                        "clean, coherent visual shot description in plain English, "
                        "and nothing else.",
                    },
                    {
                        "role": "user",
                        "content": (
                            "Write ONE concrete, coherent, cinematic visual shot "
                            "description (1-2 sentences, between 10 and 50 words, "
                            "plain English, absolutely no gibberish) that an AI "
                            "video generator can render for this narration line:\n\n"
                            f"\"{narration[:400]}\"\n\n"
                            "Name a clear subject, setting and lighting. Return ONLY "
                            "the description text."
                        ),
                    },
                ],
                temperature=0.5,
                max_tokens=120,
            )
        except RuntimeError:
            break
        cand = _clean_desc(raw)
        if _is_coherent_description(cand):
            return cand
    return _fallback_description(narration)


def _salvage_desc_lines(raw: str) -> List[str]:
    """Recover descriptions from a near-JSON / numbered list the parser rejected.

    Best-effort: strips brackets, quotes and numbering line by line. Anything
    salvaged still passes through coherence validation, so a bad guess is simply
    regenerated — this only avoids unnecessary per-scene LLM calls.
    """
    out: List[str] = []
    for line in raw.splitlines():
        s = line.strip().strip(",").strip("[]").strip()
        s = re.sub(r"^\s*\d+\s*[\.\)\:]\s*", "", s)
        s = s.strip().strip('"').strip("'").strip()
        if len(s.split()) >= 5:
            out.append(_clean_desc(s))
    return out


def _generate_visual_descriptions(segments: List[str]) -> List[str]:
    """Generate a coherent cinematic description for each narration segment.

    One batched LLM call, then per-scene validation + automatic regeneration of
    any description that is gibberish or outside the 10-50 word range.
    """
    n = len(segments)
    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(segments))
    system = (
        "You are a professional cinematographer and prompt engineer. For each "
        "numbered narration line you write ONE clean, coherent, cinematic visual "
        "shot description in plain English. You ALWAYS reply with a single valid "
        "JSON array of strings and nothing else."
    )
    user = (
        f"Write exactly {n} visual shot descriptions — one per narration line "
        "below, in the same order.\n\n"
        "STRICT RULES for every description:\n"
        "- 1 to 2 sentences, between 10 and 50 words.\n"
        "- Clean, coherent, real English. NO gibberish, NO random words, NO "
        "nonsense, NO invented words.\n"
        "- Describe a concrete shot: name the subject, the setting/location, the "
        "lighting, and the camera angle/mood. It must read as a sensible "
        "instruction to an AI video generator.\n"
        "- Do NOT include the scene number or repeat the narration text.\n\n"
        f"OUTPUT: ONLY a JSON array of exactly {n} strings. The first character "
        "must be '[' and the last ']'. No markdown, no code fences, no commentary.\n\n"
        f"NARRATION LINES:\n{numbered}"
    )
    descs: List[str] = []
    raw = ""
    try:
        raw = _chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.4,
            max_tokens=2048,
        )
    except RuntimeError as exc:
        log.warning("Description batch LLM call failed (%s)", exc)
    if raw:
        try:
            data = _extract_json(raw)
            if isinstance(data, list):
                descs = [_clean_desc(str(x)) for x in data]
        except ValueError:
            descs = _salvage_desc_lines(raw)
        if not descs:
            descs = _salvage_desc_lines(raw)

    # Align to the number of segments.
    descs = (descs + [""] * n)[:n]

    out: List[str] = []
    regenerated = 0
    for seg, d in zip(segments, descs):
        if not _is_coherent_description(d):
            d = _regenerate_description(seg)
            regenerated += 1
        out.append(d)
    if regenerated:
        log.info(
            "Regenerated %d/%d visual descriptions that failed validation",
            regenerated, n,
        )
    return out


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
