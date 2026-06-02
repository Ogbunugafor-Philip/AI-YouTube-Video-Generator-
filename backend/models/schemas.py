"""Pydantic request/response models shared across routers."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Core domain objects
# --------------------------------------------------------------------------- #
class Scene(BaseModel):
    scene_number: int
    narration_text: str
    visual_description: str


# --------------------------------------------------------------------------- #
# Script generation
# --------------------------------------------------------------------------- #
class ScriptGenerateRequest(BaseModel):
    mode: str = Field(..., description="'topic' or 'writeup'")
    duration_minutes: int = Field(3, ge=1, le=10)
    topic: Optional[str] = None
    content: Optional[str] = Field(
        None, description="Raw user write-up (only used when mode == 'writeup')"
    )


class ScriptGenerateResponse(BaseModel):
    job_id: str
    title: str
    script_text: str
    scenes: List[Scene]


class ScriptApproveRequest(BaseModel):
    job_id: str
    # Optional edited script (rich editor). When provided and changed, scenes
    # are re-split from it. Approve no longer auto-starts production — the
    # pre-production screens (style/voice/scene editor) come first.
    script_text: Optional[str] = None


class ScriptApproveResponse(BaseModel):
    job_id: str
    status: str
    script_text: str
    duration_minutes: int
    scenes: List[Scene]
    resplit: bool = False


# --------------------------------------------------------------------------- #
# Video production
# --------------------------------------------------------------------------- #
class VideoProduceRequest(BaseModel):
    job_id: str
    scenes: Optional[List[Scene]] = None
    script_text: Optional[str] = None
    title: Optional[str] = None
    # Phase 3 pre-production choices.
    voice: Optional[str] = None          # voice id from the catalog
    video_style: Optional[str] = None    # style id from the catalog


class VideoProduceResponse(BaseModel):
    job_id: str
    status: str
    video_path: Optional[str] = None
    thumbnail_path: Optional[str] = None


class VideoUploadRequest(BaseModel):
    job_id: str


class VideoUploadResponse(BaseModel):
    job_id: str
    youtube_video_id: str
    draft_url: str


# --------------------------------------------------------------------------- #
# Mobile / FCM
# --------------------------------------------------------------------------- #
class FcmRegisterRequest(BaseModel):
    device_token: str = Field(..., description="FCM device registration token")
    device_id: str = Field(..., description="Stable per-install device id")
    platform: str = "android"


class PublishRequest(BaseModel):
    # Publish an existing produced video to YouTube (private draft -> public).
    job_id: Optional[str] = None
    video_id: Optional[str] = None  # YouTube video id (if already uploaded)


# --------------------------------------------------------------------------- #
# Thumbnail
# --------------------------------------------------------------------------- #
class ThumbnailRegenerateRequest(BaseModel):
    job_id: str
    title: Optional[str] = None


class ThumbnailResponse(BaseModel):
    job_id: str
    thumbnail_path: str


# --------------------------------------------------------------------------- #
# Audio
# --------------------------------------------------------------------------- #
class AudioGenerateRequest(BaseModel):
    job_id: str
    script_text: Optional[str] = None


class AudioResponse(BaseModel):
    job_id: str
    audio_path: str


# --------------------------------------------------------------------------- #
# Admin / stats
# --------------------------------------------------------------------------- #
class VideoRecord(BaseModel):
    job_id: str
    title: str
    date: str
    duration_minutes: int
    estimated_cost: float


class AdminStatsResponse(BaseModel):
    total_videos: int
    total_api_calls: int
    estimated_total_cost: float
    videos: List[VideoRecord]
    # --- Phase 2: breaking-news automation ---
    news_alerts_sent: int = 0
    yes_replies: int = 0
    no_replies: int = 0
    auto_videos: int = 0
    last_news_check: Optional[str] = None
    next_news_check: Optional[str] = None
