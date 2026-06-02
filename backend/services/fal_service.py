"""fal.ai integration: scene video clips, voice narration, and thumbnails.

All generation runs through the ``fal-client`` SDK, which authenticates from the
FAL_KEY environment variable (populated from FAL_API_KEY in core.config). Result
media (hosted on fal's CDN) is downloaded to local TEMP_DIR / OUTPUT_DIR.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import fal_client
import httpx

from core.config import config
from core.logger import get_logger
from core import jobs, stats

log = get_logger(__name__)

# How many scene clips to generate concurrently. Kept modest to respect rate
# limits while still being meaningfully parallel.
MAX_CONCURRENCY = 5


def _require_key() -> None:
    if not config.FAL_API_KEY:
        raise RuntimeError("FAL_API_KEY is not configured in .env")


def _first_url(result: Dict[str, Any], *keys: str) -> Optional[str]:
    """Pull the first media URL out of a fal result, tolerating shape variation."""
    if not isinstance(result, dict):
        return None
    for key in keys:
        val = result.get(key)
        if isinstance(val, dict) and "url" in val:
            return val["url"]
        if isinstance(val, list) and val:
            item = val[0]
            if isinstance(item, dict) and "url" in item:
                return item["url"]
            if isinstance(item, str):
                return item
        if isinstance(val, str) and val.startswith("http"):
            return val
    return None


async def _download(url: str, dest: Path) -> Path:
    """Download a remote URL to ``dest`` (created parents)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading %s -> %s", url, dest)
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return dest


async def _fal_run(model: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Run a fal model and return its result dict."""
    _require_key()
    log.info("Calling fal model %s", model)
    try:
        result = await fal_client.subscribe_async(model, arguments=arguments)
        stats.record_api_calls(1)
        return result or {}
    except Exception as exc:  # noqa: BLE001
        log.exception("fal model %s failed", model)
        raise RuntimeError(f"fal request to {model} failed: {exc}") from exc


# --------------------------------------------------------------------------- #
# Video clips
# --------------------------------------------------------------------------- #
async def generate_video_clip(
    visual_description: str, scene_number: int, job_id: Optional[str] = None
) -> str:
    """Generate a short (5-8s) clip for one scene and save it to TEMP_DIR.

    The configured video model (e.g. SVD) is image-conditioned, so we first
    render a still from the visual description with the image model, then animate
    it. Returns the local clip path. Written into a per-job temp dir when
    ``job_id`` is given so concurrent productions never overwrite each other.
    """
    base = config.job_temp_dir(job_id) if job_id else config.TEMP_DIR
    dest = base / f"scene_{scene_number}.mp4"
    log.info("Generating clip for scene %d", scene_number)

    # 1) Render a conditioning still from the prompt.
    image_url: Optional[str] = None
    try:
        img_res = await _fal_run(
            config.FAL_IMAGE_MODEL,
            {
                "prompt": visual_description,
                "image_size": "landscape_16_9",
                "num_images": 1,
            },
        )
        stats.record_api_calls(0, stats.COST_PER_IMAGE_CALL)
        image_url = _first_url(img_res, "images", "image")
    except RuntimeError as exc:
        log.warning("Scene %d still render failed (%s); trying text-only video",
                    scene_number, exc)

    # 2) Animate into a short clip.
    args: Dict[str, Any] = {"prompt": visual_description, "motion_bucket_id": 127}
    if image_url:
        args["image_url"] = image_url
    video_res = await _fal_run(config.FAL_VIDEO_MODEL, args)
    stats.record_api_calls(0, stats.COST_PER_VIDEO_CLIP)

    video_url = _first_url(video_res, "video", "videos")
    if not video_url:
        raise RuntimeError(f"No video URL returned for scene {scene_number}")
    await _download(video_url, dest)
    return str(dest)


async def generate_all_clips(
    scenes: List[Dict[str, Any]], job_id: Optional[str] = None
) -> List[str]:
    """Generate every scene clip in parallel, emitting progress as each finishes.

    Returns clip paths in scene order. A failed scene yields an empty string so
    the caller can decide how to handle gaps; failures are logged.
    """
    total = len(scenes)
    log.info("Generating %d scene clips (concurrency=%d)", total, MAX_CONCURRENCY)
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    results: List[str] = [""] * total
    completed = 0
    lock = asyncio.Lock()

    async def worker(idx: int, scene: Dict[str, Any]) -> None:
        nonlocal completed
        async with semaphore:
            try:
                path = await generate_video_clip(
                    scene.get("visual_description", ""),
                    scene.get("scene_number", idx + 1),
                    job_id=job_id,
                )
                results[idx] = path
            except Exception as exc:  # noqa: BLE001
                log.error("Scene %d failed: %s", idx + 1, exc)
            finally:
                async with lock:
                    completed += 1
                    if job_id:
                        # Scene generation spans 10% -> 70% of the pipeline.
                        pct = 10 + int(60 * completed / max(total, 1))
                        await jobs.emit(
                            job_id,
                            step=f"Generating scene {completed} of {total}",
                            scenes_completed=completed,
                            percentage=pct,
                        )

    await asyncio.gather(*(worker(i, s) for i, s in enumerate(scenes)))
    succeeded = [p for p in results if p]
    log.info("Scene clips done: %d/%d succeeded", len(succeeded), total)
    if not succeeded:
        raise RuntimeError("All scene clip generations failed")
    return results


# --------------------------------------------------------------------------- #
# Voice narration
# --------------------------------------------------------------------------- #
DEFAULT_TTS_VOICE = "af_heart"


def _tts_args(text: str, voice: str) -> Dict[str, Any]:
    """Build TTS request args. fal-ai/kokoro takes ``prompt`` + ``voice``."""
    return {"prompt": text, "voice": voice}


async def generate_voice(
    script_text: str, job_id: Optional[str] = None, voice: Optional[str] = None
) -> str:
    """Generate professional narration audio and save it to TEMP_DIR/narration.wav.

    ``voice`` is the TTS voice code (kokoro); falls back to the default.
    """
    base = config.job_temp_dir(job_id) if job_id else config.TEMP_DIR
    dest = base / "narration.wav"
    voice_name = voice or DEFAULT_TTS_VOICE
    log.info("Generating narration audio (%d chars) voice=%r", len(script_text), voice_name)
    if not script_text.strip():
        raise RuntimeError("Cannot generate voice from empty script")
    result = await _fal_run(config.FAL_TTS_MODEL, _tts_args(script_text, voice_name))
    stats.record_api_calls(0, stats.COST_PER_TTS_CALL)
    audio_url = _first_url(result, "audio", "audio_url", "audio_file")
    if not audio_url:
        raise RuntimeError("No audio URL returned from TTS model")
    await _download(audio_url, dest)
    return str(dest)


async def generate_voice_preview(voice_id: str, voice: str, text: str) -> str:
    """Generate (and cache) a short preview clip for a catalog voice.

    Saved to OUTPUT_DIR/voice_previews/<voice_id>.wav so it's only generated
    once per voice.
    """
    dest = config.OUTPUT_DIR / "voice_previews" / f"{voice_id}.wav"
    if dest.exists() and dest.stat().st_size > 0:
        return str(dest)
    log.info("Generating voice preview for %s (%r)", voice_id, voice)
    result = await _fal_run(config.FAL_TTS_MODEL, _tts_args(text, voice))
    stats.record_api_calls(0, stats.COST_PER_TTS_CALL)
    audio_url = _first_url(result, "audio", "audio_url", "audio_file")
    if not audio_url:
        raise RuntimeError("No audio URL returned from TTS model")
    await _download(audio_url, dest)
    return str(dest)


# --------------------------------------------------------------------------- #
# Thumbnail
# --------------------------------------------------------------------------- #
async def generate_thumbnail(
    title: str, script_text: str, job_id: Optional[str] = None
) -> str:
    """Generate a striking YouTube thumbnail saved to OUTPUT_DIR/thumbnail.jpg."""
    base = config.job_output_dir(job_id) if job_id else config.OUTPUT_DIR
    dest = base / "thumbnail.jpg"
    log.info("Generating thumbnail for title %r", title)
    theme = script_text[:300].replace("\n", " ")
    prompt = (
        f"A bold, eye-catching YouTube thumbnail. Large bold text overlay reading "
        f"\"{title}\" in a thick, high-impact sans-serif font. High contrast, "
        f"vivid saturated colors, dramatic lighting, striking central subject "
        f"related to: {theme}. Professional, clickable, 16:9 composition, "
        f"sharp focus, trending YouTube style."
    )
    result = await _fal_run(
        config.FAL_IMAGE_MODEL,
        {"prompt": prompt, "image_size": "landscape_16_9", "num_images": 1},
    )
    stats.record_api_calls(0, stats.COST_PER_IMAGE_CALL)
    image_url = _first_url(result, "images", "image")
    if not image_url:
        raise RuntimeError("No image URL returned for thumbnail")
    await _download(image_url, dest)
    return str(dest)
