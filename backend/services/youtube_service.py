"""YouTube Data API v3 integration: upload produced videos as private drafts.

Authenticates with an OAuth refresh token (YOUTUBE_CLIENT_ID /
YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN from .env). Tokens are refreshed
automatically by google-auth.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, List, Tuple

from core.config import config
from core.logger import get_logger

log = get_logger(__name__)

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _require_creds() -> None:
    missing = [
        name
        for name, val in (
            ("YOUTUBE_CLIENT_ID", config.YOUTUBE_CLIENT_ID),
            ("YOUTUBE_CLIENT_SECRET", config.YOUTUBE_CLIENT_SECRET),
            ("YOUTUBE_REFRESH_TOKEN", config.YOUTUBE_REFRESH_TOKEN),
        )
        if not val
    ]
    if missing:
        raise RuntimeError(f"YouTube credentials missing in .env: {', '.join(missing)}")


def get_youtube_client() -> Any:
    """Build an authenticated YouTube Data API client from the refresh token.

    google-auth refreshes the access token automatically when it expires.
    """
    _require_creds()
    # Imported lazily so the module imports even if these heavy deps are absent.
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=config.YOUTUBE_REFRESH_TOKEN,
        client_id=config.YOUTUBE_CLIENT_ID,
        client_secret=config.YOUTUBE_CLIENT_SECRET,
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_to_youtube(
    video_path: str,
    thumbnail_path: str,
    title: str,
    description: str,
    tags: List[str],
) -> Tuple[str, str]:
    """Upload ``video_path`` as a PRIVATE draft, set its thumbnail + metadata.

    Returns (video_id, draft_url). Raises RuntimeError on failure.
    """
    _require_creds()
    if not Path(video_path).exists():
        raise RuntimeError(f"Video file not found: {video_path}")

    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    youtube = get_youtube_client()

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:15],
            "categoryId": "28",  # Science & Technology
        },
        "status": {
            "privacyStatus": "private",  # upload as private draft
            "selfDeclaredMadeForKids": False,
        },
    }

    try:
        log.info("Uploading video to YouTube: %r", title[:60])
        media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
        request = youtube.videos().insert(
            part="snippet,status", body=body, media_body=media
        )
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                log.info("Upload progress: %d%%", int(status.progress() * 100))
        video_id = response["id"]
        log.info("Uploaded video id=%s", video_id)

        # Set the custom thumbnail (best-effort; some accounts lack permission).
        if thumbnail_path and Path(thumbnail_path).exists():
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
                ).execute()
                log.info("Thumbnail set for %s", video_id)
            except HttpError as exc:
                log.warning("Could not set thumbnail for %s: %s", video_id, exc)

        draft_url = f"https://studio.youtube.com/video/{video_id}/edit"
        return video_id, draft_url
    except HttpError as exc:
        log.exception("YouTube upload failed")
        raise RuntimeError(f"YouTube upload failed: {exc}") from exc
