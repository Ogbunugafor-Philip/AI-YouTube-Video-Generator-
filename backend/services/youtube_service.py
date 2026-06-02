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
# upload = publishing; youtube + readonly = reading our own videos' statistics
# for the history library. The refresh token was granted these scopes.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.readonly",
]


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
    publish_at: Any = None,
) -> Tuple[str, str]:
    """Upload ``video_path`` as a PRIVATE draft, set its thumbnail + metadata.

    If ``publish_at`` is given (a datetime or an RFC3339 string), the draft is
    scheduled to auto-publish at that time (YouTube requires privacyStatus to
    stay ``private`` for scheduled videos). Otherwise it stays a private draft
    for manual review. Returns (video_id, draft_url). Raises on failure.
    """
    _require_creds()
    if not Path(video_path).exists():
        raise RuntimeError(f"Video file not found: {video_path}")

    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    youtube = get_youtube_client()

    status: dict = {
        "privacyStatus": "private",  # upload as private draft
        "selfDeclaredMadeForKids": False,
    }
    if publish_at is not None:
        # Accept a datetime or a pre-formatted RFC3339 string.
        if hasattr(publish_at, "isoformat"):
            publish_at_str = publish_at.isoformat()
            if publish_at_str.endswith("+00:00"):
                publish_at_str = publish_at_str[:-6] + "Z"
            elif "+" not in publish_at_str and "Z" not in publish_at_str:
                publish_at_str += "Z"
        else:
            publish_at_str = str(publish_at)
        status["publishAt"] = publish_at_str
        log.info("Scheduling draft to auto-publish at %s", publish_at_str)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:15],
            "categoryId": "28",  # Science & Technology
        },
        "status": status,
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


def get_video_stats(video_ids: List[str]) -> dict:
    """Fetch live statistics for up to 50 video ids in one call.

    Returns a dict keyed by video_id -> {views, likes, comments, title,
    thumbnail, privacy_status, published_at}. Missing/inaccessible ids are
    simply absent. Never raises — returns {} on failure so the history page
    still renders.
    """
    ids = [v for v in (video_ids or []) if v]
    if not ids:
        return {}
    try:
        _require_creds()
        youtube = get_youtube_client()
        out: dict = {}
        # The API accepts up to 50 ids per call.
        for i in range(0, len(ids), 50):
            chunk = ids[i : i + 50]
            resp = (
                youtube.videos()
                .list(part="statistics,snippet,status", id=",".join(chunk))
                .execute()
            )
            for item in resp.get("items", []):
                vid = item["id"]
                st = item.get("statistics", {})
                sn = item.get("snippet", {})
                thumbs = sn.get("thumbnails", {})
                thumb = (
                    thumbs.get("medium", {}).get("url")
                    or thumbs.get("default", {}).get("url")
                )
                out[vid] = {
                    "views": int(st.get("viewCount", 0)),
                    "likes": int(st.get("likeCount", 0)),
                    "comments": int(st.get("commentCount", 0)),
                    "title": sn.get("title", ""),
                    "thumbnail": thumb,
                    "privacy_status": item.get("status", {}).get("privacyStatus"),
                    "published_at": sn.get("publishedAt"),
                }
        return out
    except Exception as exc:  # noqa: BLE001
        log.error("get_video_stats failed: %s", exc)
        return {}
