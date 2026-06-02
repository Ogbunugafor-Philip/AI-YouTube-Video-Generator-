"""Subtitle generation.

Builds an SRT from the narration script, timed to the narration audio duration
(playai-tts gives no word-level timestamps, so we distribute time proportional
to each caption's character count — a reliable approximation). The SRT is then
burned into the final MP4 by ffmpeg_service.burn_subtitles.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from core.config import config
from core.logger import get_logger

log = get_logger(__name__)

# Aim for short, readable captions.
MAX_CHARS_PER_CAPTION = 90
MAX_WORDS_PER_CAPTION = 14


def _split_into_captions(script_text: str) -> List[str]:
    """Split script into caption-sized chunks on sentence then length bounds."""
    text = re.sub(r"\s+", " ", script_text.strip())
    if not text:
        return []
    # Split into sentences first.
    sentences = re.split(r"(?<=[.!?])\s+", text)
    captions: List[str] = []
    for sentence in sentences:
        words = sentence.split()
        if not words:
            continue
        # Break long sentences into <= MAX_WORDS chunks.
        chunk: List[str] = []
        for word in words:
            chunk.append(word)
            joined = " ".join(chunk)
            if len(chunk) >= MAX_WORDS_PER_CAPTION or len(joined) >= MAX_CHARS_PER_CAPTION:
                captions.append(joined)
                chunk = []
        if chunk:
            captions.append(" ".join(chunk))
    return captions


def _fmt_ts(seconds: float) -> str:
    """Format seconds as SRT timestamp HH:MM:SS,mmm."""
    if seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(script_text: str, audio_duration: float, job_id: str) -> str:
    """Write an SRT file (timed to ``audio_duration``) and return its path."""
    captions = _split_into_captions(script_text)
    if not captions:
        raise RuntimeError("No caption text to generate subtitles from")
    if not audio_duration or audio_duration <= 0:
        # Fallback: assume ~2.2 words/sec narration pace.
        words = sum(len(c.split()) for c in captions)
        audio_duration = max(1.0, words / 2.2)

    total_chars = sum(len(c) for c in captions) or 1
    dest = config.job_temp_dir(job_id) / "subtitles.srt"

    lines: List[str] = []
    cursor = 0.0
    for i, caption in enumerate(captions, start=1):
        share = len(caption) / total_chars
        dur = max(0.8, audio_duration * share)
        start = cursor
        end = min(audio_duration, start + dur)
        if i == len(captions):
            end = audio_duration  # snap last caption to the very end
        cursor = end
        lines.append(str(i))
        lines.append(f"{_fmt_ts(start)} --> {_fmt_ts(end)}")
        lines.append(caption)
        lines.append("")

    dest.write_text("\n".join(lines), encoding="utf-8")
    log.info("Wrote %d captions to %s (%.1fs)", len(captions), dest, audio_duration)
    return str(dest)
