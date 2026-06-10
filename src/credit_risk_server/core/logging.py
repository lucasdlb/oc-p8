"""Structured JSON logging setup for the API.

Provides:
- DevFormatter: Human-readable logs with extra fields appended.
- JSONFormatter: Production JSON logs with ISO-8601 timestamps, exceptions,
  stack traces, and extra fields.
- CorrelationFilter: Adds request-scoped correlation_id to every log record.
- setup_logging(): Idempotent configuration based on AppSettings.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Literal

_CONFIGURED = False

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationFilter(logging.Filter):
    """Inject the current correlation_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get()  # type: ignore[attr-defined]
        return True


_SKIP_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "relativeCreated",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "pathname",
        "filename",
        "module",
        "thread",
        "threadName",
        "process",
        "processName",
        "levelname",
        "levelno",
        "message",
        "msecs",
        "taskName",
        "correlation_id",
    }
)


def _extract_extras(record: logging.LogRecord) -> dict[str, Any]:
    """Pull non-standard attributes from a LogRecord into a dict."""
    return {
        k: v for k, v in record.__dict__.items() if k not in _SKIP_ATTRS and not k.startswith("_")
    }


class DevFormatter(logging.Formatter):
    """Human-readable formatter that appends extra fields to each line."""

    _DEV_FMT = "%(asctime)s | %(name)-40s | %(levelname)-8s | %(correlation_id)-38s | %(message)s"

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = _extract_extras(record)
        if extras:
            pairs = " ".join(f"{k}={v}" for k, v in extras.items())
            return f"{base} | {pairs}"
        return base


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for production environments."""

    def format(self, record: logging.LogRecord) -> str:
        log: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        correlation = getattr(record, "correlation_id", None)
        if correlation:
            log["correlation_id"] = correlation

        if record.exc_info and record.exc_info[0]:
            log["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            log["stack_info"] = self.formatStack(record.stack_info)

        for key, value in _extract_extras(record).items():
            log[key] = value

        return json.dumps(log, ensure_ascii=False, default=str)


def setup_logging(
    log_level: str,
    env: Literal["dev", "prod"],
    log_path: Path,
) -> None:
    """Configure application logging based on environment settings.

    Idempotent - subsequent calls are no-ops.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    level_name = log_level.upper()
    level = getattr(logging, level_name, logging.INFO)
    is_dev = env == "dev"

    if is_dev:
        formatter: logging.Formatter = DevFormatter(DevFormatter._DEV_FMT)
    else:
        formatter = JSONFormatter()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    console_handler.addFilter(CorrelationFilter())

    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10_485_760,
        backupCount=5,
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    file_handler.addFilter(CorrelationFilter())

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    if is_dev:
        logging.getLogger("uvicorn.access").setLevel(logging.INFO)
        logging.getLogger("urllib3").setLevel(logging.INFO)
    else:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)


class Timer:
    """Context manager that logs elapsed time on exit.

    Logs at INFO level on success, WARNING level on exception.
    """

    def __init__(self, logger: logging.Logger, action: str, **extra: Any) -> None:
        self._logger = logger
        self._action = action
        self._extra = extra
        self._start: float = 0.0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, *exc: Any) -> None:
        elapsed_ms = (time.perf_counter() - self._start) * 1000
        if exc_type is not None:
            self._logger.warning(
                "%s failed after %.1f ms",
                self._action,
                elapsed_ms,
                extra=self._extra,
            )
        else:
            self._logger.info(
                "%s completed in %.1f ms",
                self._action,
                elapsed_ms,
                extra=self._extra,
            )
