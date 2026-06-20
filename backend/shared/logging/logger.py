"""Structured JSON logging for ArchMind AI.

Provides a factory function get_logger(name) that returns a standard
logging.Logger instance configured with JSON output. All application modules
call get_logger(__name__) to obtain their logger.

JSON log format per record:
{
    "timestamp": "<ISO 8601 UTC>",
    "level": "<LEVEL>",
    "logger": "<module.name>",
    "message": "<formatted message>",
    "extra_key": "<extra_value>",   # any keys passed via extra={}
    "exception": "<traceback>"      # only on log records with exc_info
}

Dependency rule: imports only from config/ and stdlib.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

_STANDARD_LOG_RECORD_KEYS: frozenset[str] = frozenset({
    "args",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "taskName",
    "thread",
    "threadName",
})


class _JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects.

    Extra fields passed via the extra={} argument to logger.info() and
    similar methods are automatically included in the JSON output.
    """

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()

        payload: dict[str, Any] = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
        }

        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_KEYS and not key.startswith("_"):
                try:
                    json.dumps(value)
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = str(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str)


def _build_handler() -> logging.StreamHandler:
    """Create a stdout stream handler with the JSON formatter applied."""
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(_JsonFormatter())
    return handler


def _configure_root_logger(level: str) -> None:
    """Apply JSON handler and level to the root logger.

    Called once at application startup. Subsequent calls to get_logger()
    inherit this configuration through Python's logger hierarchy.
    """
    root = logging.getLogger()

    if root.handlers:
        for existing_handler in root.handlers[:]:
            root.removeHandler(existing_handler)

    root.addHandler(_build_handler())
    root.setLevel(level)

    logging.getLogger("uvicorn.access").propagate = False
    logging.getLogger("uvicorn.error").propagate = True


_logging_configured: bool = False


def configure_logging() -> None:
    """Initialise the logging subsystem from application settings.

    Must be called once at application startup (in main.py startup event).
    Safe to call multiple times: subsequent calls are no-ops.
    """
    global _logging_configured
    if _logging_configured:
        return

    try:
        from config.settings import get_settings
        level = get_settings().log_level
    except Exception:
        level = "INFO"

    _configure_root_logger(level)
    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named Logger configured for structured JSON output.

    Usage in any module:
        from shared.logging.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Repository cloned", extra={"repo_url": url, "duration_ms": 1234})

    Args:
        name: Logger name. Pass __name__ from the calling module.

    Returns:
        A logging.Logger instance that writes structured JSON to stdout.
    """
    if not _logging_configured:
        configure_logging()
    return logging.getLogger(name)
