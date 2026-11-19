"""Structured JSON logging (python-json-logger), secrets never logged."""

from __future__ import annotations

import logging
import sys

from pythonjsonlogger.json import JsonFormatter

from app.config import get_settings

_SECRET_HINTS = ("api_key", "apikey", "authorization", "secret", "password", "token")


class _RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__):
            if any(h in key.lower() for h in _SECRET_HINTS) and key not in {"total_tokens"}:
                record.__dict__[key] = "[redacted]"
        return True


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_json:
        handler.setFormatter(
            JsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
                rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
            )
        )
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    handler.addFilter(_RedactFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(settings.log_level.upper())
    for noisy in ("httpx", "httpcore", "LiteLLM", "litellm", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
