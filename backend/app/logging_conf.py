"""Structured application logging.

Production deployments set LOG_FORMAT=json to emit one JSON object per line
(parseable by CloudWatch/ELK/etc.). Development keeps human-readable console
output.

A single configured root logger means FastAPI, uvicorn, SQLAlchemy, and RQ
all flow through the same pipeline. Every AURORA module gets its logger via
app.logging_conf.get_logger(__name__).

Usage:

    logger = get_logger(__name__)
    logger.info("Analysis completed", extra_keys={"analysis_id": 1})

``extra_keys`` is merged into the emitted record (and therefore the JSON
line); logging itself does not need to know about it -- AuroraLogger
translates it into the standard ``extra`` you would pass to Python logging.
"""

import json
import logging
import sys
from typing import Any

from app.config import get_settings

# Sentinel: AuroraLogger accepts this as a keyword without polluting other
# logging implementations we might swap in later.
_EXTRA_KEYS = "extra_keys"


class JsonFormatter(logging.Formatter):
    """Emit structured, single-line JSON records with a stable key set."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, _EXTRA_KEYS, None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, default=str)


def _configure_handlers() -> None:
    settings = get_settings()
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    if getattr(settings, "LOG_FORMAT", "text").lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
    root.addHandler(handler)
    # uvicorn's access log duplicates our request logging; SQLAlchemy query
    # logging is noise unless explicitly enabled; quiet both.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


_configured = False


def setup_logging() -> None:
    """Configure root logging once per process (idempotent)."""
    global _configured
    if _configured:
        return
    _configure_handlers()
    logging.getLogger("app").debug("AURORA structured logging initialised")
    _configured = True


class AuroraLogger:
    """logging.Logger facade that forwards ``extra_keys`` into ``extra``.

    Lets call sites write ``logger.info("msg", extra_keys={...})``, keeping
    structured fields natural to read, while under the hood it feeds
    standard-library logging exactly what it expects.
    """

    def __init__(self, name: str, base_extra: dict[str, Any] | None = None):
        self._logger = logging.getLogger(name)
        self._base_extra = base_extra or {}

    def __getattr__(self, item):
        return getattr(self._logger, item)

    def _log(self, level: int, msg: str, args=(), *, exc_info=None, extra=None, extra_keys=None, **kwargs):
        combined = dict(self._base_extra)
        if extra_keys:
            combined.update(extra_keys)
        if combined:
            extra = dict(extra or {})
            extra[_EXTRA_KEYS] = combined
        self._logger.log(level, msg, *args, exc_info=exc_info, extra=extra, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self._log(logging.DEBUG, msg, args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._log(logging.INFO, msg, args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._log(logging.WARNING, msg, args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._log(logging.ERROR, msg, args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self._log(logging.CRITICAL, msg, args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        kwargs["exc_info"] = kwargs.get("exc_info", True)
        self._log(logging.ERROR, msg, args, **kwargs)

    def log(self, level: int, msg, *args, **kwargs):
        self._log(level, msg, args, **kwargs)


def get_logger(name: str, extra_keys: dict | None = None):
    return AuroraLogger(name, extra_keys)
