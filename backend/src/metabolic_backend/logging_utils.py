"""Logging helpers to enforce privacy-first audit trails."""

from __future__ import annotations

import logging
import json
import os
from threading import Lock

from .orchestrator.guardrails import scrub_text

_CONFIG_LOCK = Lock()
_CONFIGURED = False


class PIIScrubberFilter(logging.Filter):
    """Scrubs common PII tokens from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = scrub_text(record.msg)

        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(scrub_text(str(arg)) for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {key: scrub_text(str(value)) for key, value in record.args.items()}

        return True


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if hasattr(record, "event"):
            payload["event"] = record.event
        if hasattr(record, "payload"):
            payload["payload"] = record.payload
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logger with PII scrubbing and consistent format."""

    global _CONFIGURED
    with _CONFIG_LOCK:
        if _CONFIGURED:
            return

        log_format = os.getenv("METABOLIC_LOG_FORMAT", "plain").lower()
        if log_format == "json":
            handler = logging.StreamHandler()
            handler.setFormatter(JSONFormatter())
            logging.basicConfig(level=level, handlers=[handler])
        else:
            logging.basicConfig(level=level, format="[%(levelname)s] %(name)s - %(message)s")

        root_logger = logging.getLogger()
        root_logger.addFilter(PIIScrubberFilter())
        _CONFIGURED = True


def log_event(event: str, payload: dict | None = None, level: int = logging.INFO) -> None:
    logger = logging.getLogger("metabolic.observability")
    logger.log(level, scrub_text(json.dumps(payload or {}, ensure_ascii=False)), extra={"event": event, "payload": payload or {}})
