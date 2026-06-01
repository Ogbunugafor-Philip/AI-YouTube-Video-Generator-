"""Application configuration.

All settings are loaded from the project-level ``.env`` file. No secret is ever
hardcoded here — every value comes from the environment.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Project root is two levels up from this file: backend/core/config.py -> vid_gen/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

# Load .env explicitly from the project root so the app works regardless of CWD.
load_dotenv(ENV_PATH)


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default) or default


class Config:
    """Typed accessors for every environment variable the app needs."""

    # --- fal.ai (LLM / video / image / tts) ---
    FAL_API_KEY: str = _get("FAL_API_KEY")
    FAL_VIDEO_MODEL: str = _get("FAL_VIDEO_MODEL", "fal-ai/fast-svd-lcm")
    FAL_IMAGE_MODEL: str = _get("FAL_IMAGE_MODEL", "fal-ai/flux/schnell")
    FAL_TTS_MODEL: str = _get("FAL_TTS_MODEL", "fal-ai/playai-tts")
    # LLM (script generation) via fal-ai/any-llm.
    FAL_LLM_MODEL: str = _get("FAL_LLM_MODEL", "fal-ai/any-llm")
    FAL_LLM_CHAT_MODEL: str = _get("FAL_LLM_CHAT_MODEL", "openai/gpt-oss-120b")

    # --- Gmail (alerts + reply polling) ---
    GMAIL_ADDRESS: str = _get("GMAIL_ADDRESS")
    GMAIL_APP_PASSWORD: str = _get("GMAIL_APP_PASSWORD")

    # --- YouTube Data API v3 (draft upload) ---
    YOUTUBE_CLIENT_ID: str = _get("YOUTUBE_CLIENT_ID")
    YOUTUBE_CLIENT_SECRET: str = _get("YOUTUBE_CLIENT_SECRET")
    YOUTUBE_REFRESH_TOKEN: str = _get("YOUTUBE_REFRESH_TOKEN")

    # --- App ---
    APP_SECRET_KEY: str = _get("APP_SECRET_KEY", "change-me")
    APP_ENV: str = _get("APP_ENV", "development")

    # --- Storage ---
    OUTPUT_DIR: Path = Path(_get("OUTPUT_DIR", str(BASE_DIR / "outputs")))
    TEMP_DIR: Path = Path(_get("TEMP_DIR", str(BASE_DIR / "temp")))

    @property
    def stats_file(self) -> Path:
        return self.OUTPUT_DIR / "stats.json"

    @property
    def alerts_file(self) -> Path:
        return self.OUTPUT_DIR / "alerts.json"

    def ensure_dirs(self) -> None:
        """Make sure output/temp directories exist."""
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)

    def missing_keys(self) -> list[str]:
        """Return a list of required secret keys that are empty (for diagnostics)."""
        required = {
            "FAL_API_KEY": self.FAL_API_KEY,
        }
        return [k for k, v in required.items() if not v]


config = Config()
config.ensure_dirs()

# fal-client reads the FAL_KEY environment variable for auth. Mirror our config
# value into it so the SDK is authenticated without any hardcoded credentials.
if config.FAL_API_KEY:
    os.environ.setdefault("FAL_KEY", config.FAL_API_KEY)
