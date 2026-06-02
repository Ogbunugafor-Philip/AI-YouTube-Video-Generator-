"""FFmpeg video assembly.

Concatenates scene clips in order and lays the narration audio over the full
video. FFmpeg is invoked via subprocess (no Python wrapper libraries).
"""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import List, Optional

from core.config import config
from core.logger import get_logger

log = get_logger(__name__)


def _ffmpeg_bin() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("ffmpeg executable not found on PATH")
    return path


async def _run(cmd: List[str]) -> None:
    """Run a subprocess command asynchronously, raising on non-zero exit."""
    log.info("Running: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        msg = stderr.decode(errors="replace")[-2000:]
        log.error("ffmpeg failed (%d): %s", proc.returncode, msg)
        raise RuntimeError(f"ffmpeg failed with code {proc.returncode}: {msg}")


async def _probe_duration(path: str) -> Optional[float]:
    """Return media duration in seconds via ffprobe, or None if unavailable."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    proc = await asyncio.create_subprocess_exec(
        ffprobe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    try:
        return float(out.decode().strip())
    except (ValueError, AttributeError):
        return None


async def assemble_video(
    scene_clips: List[str],
    narration_path: Optional[str],
    output_path: Optional[str] = None,
    job_id: Optional[str] = None,
) -> str:
    """Concatenate ``scene_clips`` and mux ``narration_path`` over the result.

    The final video length is locked to the narration length: if the stitched
    clips are shorter than the narration, the last frame is held (so narration is
    never cut off); if longer, the video is trimmed. Returns the path to the
    final MP4 (per-job OUTPUT_DIR/<job_id>/final_video.mp4 when ``job_id`` given).
    """
    ffmpeg = _ffmpeg_bin()
    clips = [c for c in scene_clips if c and Path(c).exists()]
    if not clips:
        raise RuntimeError("No valid scene clips to assemble")

    out_base = config.job_output_dir(job_id) if job_id else config.OUTPUT_DIR
    tmp_base = config.job_temp_dir(job_id) if job_id else config.TEMP_DIR
    out = Path(output_path) if output_path else (out_base / "final_video.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp_base.mkdir(parents=True, exist_ok=True)

    # 1) Build a concat-demuxer list file (re-encode for safety across clips that
    #    may differ in codec params).
    concat_list = tmp_base / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for clip in clips:
            f.write(f"file '{Path(clip).resolve().as_posix()}'\n")

    silent_video = tmp_base / "_assembled_silent.mp4"
    await _run(
        [
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-r", "30",
            "-an",
            str(silent_video),
        ]
    )

    # 2) Mux narration over the concatenated video, if narration exists.
    if narration_path and Path(narration_path).exists():
        audio_dur = await _probe_duration(str(narration_path))
        if audio_dur and audio_dur > 0:
            # Hold the final frame to cover any gap, then trim to the exact
            # narration length so the whole narration always plays and there's
            # no trailing black/silence.
            await _run(
                [
                    ffmpeg, "-y",
                    "-i", str(silent_video),
                    "-i", str(narration_path),
                    "-vf", f"tpad=stop_mode=clone:stop_duration={audio_dur:.3f}",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
                    "-c:a", "aac", "-b:a", "192k",
                    "-t", f"{audio_dur:.3f}",
                    str(out),
                ]
            )
        else:
            # ffprobe unavailable — fall back to ending at the shorter stream.
            await _run(
                [
                    ffmpeg, "-y",
                    "-i", str(silent_video),
                    "-i", str(narration_path),
                    "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k",
                    "-shortest",
                    "-map", "0:v:0", "-map", "1:a:0",
                    str(out),
                ]
            )
    else:
        log.warning("No narration audio; producing silent final video")
        shutil.move(str(silent_video), str(out))

    if not out.exists():
        raise RuntimeError("ffmpeg completed but output file is missing")
    log.info("Assembled final video: %s", out)
    return str(out)
