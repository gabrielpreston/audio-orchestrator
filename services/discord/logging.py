"""Logging configuration for the Python Discord voice bot."""

from __future__ import annotations

import logging
from typing import Mapping, MutableMapping, Optional

from pythonjsonlogger import jsonlogger


class CorrelationAdapter(logging.LoggerAdapter):
    """Adapter that injects correlation metadata."""

    def process(self, msg: str, kwargs: MutableMapping[str, object]) -> tuple[str, MutableMapping[str, object]]:
        extra = kwargs.get("extra") or {}
        for key, value in self.extra.items():
            extra.setdefault(key, value)
        kwargs["extra"] = extra
        return msg, kwargs


class JsonFormatter(jsonlogger.JsonFormatter):
    """Structured formatter compatible with python-json-logger."""

    DEFAULT_FIELDS: tuple[str, ...] = (
        "timestamp",
        "level",
        "name",
        "message",
        "correlation_id",
        "guild_id",
        "channel_id",
        "user_id",
    )

    def add_fields(self, log_record: MutableMapping[str, object], record: logging.LogRecord, message_dict: Mapping[str, object]) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record.setdefault("level", record.levelname)
        log_record.setdefault("timestamp", self.formatTime(record, self.datefmt))
        for field in self.DEFAULT_FIELDS:
            log_record.setdefault(field, message_dict.get(field))


def configure_logging(level: str, json_logs: bool = True) -> logging.Logger:
    """Configure root logger for the bot."""

    logging.captureWarnings(True)
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    root_logger.handlers.clear()

    handler = logging.StreamHandler()
    if json_logs:
        formatter = JsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")
    else:
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    return root_logger


def get_logger(name: str, *, correlation_id: Optional[str] = None) -> logging.LoggerAdapter[logging.Logger]:
    """Return a correlation-aware adapter."""

    logger = logging.getLogger(name)
    extra: MutableMapping[str, object] = {}
    if correlation_id:
        extra["correlation_id"] = correlation_id
    return CorrelationAdapter(logger, extra)


__all__ = ["configure_logging", "get_logger", "CorrelationAdapter", "JsonFormatter"]
