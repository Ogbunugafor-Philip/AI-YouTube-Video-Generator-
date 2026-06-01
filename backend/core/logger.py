"""Centralised logging configuration.

Every module obtains its logger via ``get_logger(__name__)`` so all log output
shares a consistent format and level.
"""
import logging
import sys

from core.config import config

_LEVEL = logging.DEBUG if config.APP_ENV != "production" else logging.INFO

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT))
    root = logging.getLogger()
    root.setLevel(_LEVEL)
    # Avoid duplicate handlers when uvicorn reloads.
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure_root()
    logger = logging.getLogger(name)
    logger.setLevel(_LEVEL)
    return logger
