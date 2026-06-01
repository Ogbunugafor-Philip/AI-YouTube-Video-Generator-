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


async def assemble_video(
    scene_clips: List[str],
    narration_path: Optional[str],
    output_path: Optional[str] = None,
) -> str:
    """Concatenate ``scene_clips`` and mux ``narration_path`` over the result.

    Returns the path to the final MP4 (OUTPUT_DIR/final_video.mp4 by default).
    """
    ffmpeg = _ffmpeg_bin()
    clips = [c for c in scene_clips if c and Path(c).exists()]
    if not clips:
        raise RuntimeError("No valid scene clips to assemble")

    out = Path(output_path) if output_path else (config.OUTPUT_DIR / "final_video.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    config.TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Build a concat-demuxer list file (re-encode for safety across clips that
    #    may differ in codec params).
    concat_list = config.TEMP_DIR / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for clip in clips:
            f.write(f"file '{Path(clip).resolve().as_posix()}'\n")

    silent_video = config.TEMP_DIR / "_assembled_silent.mp4"
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
        await _run(
            [
                ffmpeg, "-y",
                "-i", str(silent_video),
                "-i", str(narration_path),
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                # End at the shorter stream so we don't trail silence/black.
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
