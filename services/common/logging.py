"""Centralized logging utilities for discord-voice-lab services."""

from __future__ import annotations

import logging
import sys
from typing import Mapping, MutableMapping, Optional

from pythonjsonlogger import jsonlogger

# Default fields emitted for JSON logs.
DEFAULT_FIELDS: tuple[str, ...] = (
    "timestamp",
    "level",
    "service",
    "name",
    "message",
    "correlation_id",
    "guild_id",
    "channel_id",
    "user_id",
)


class JsonFormatter(jsonlogger.JsonFormatter):
    """Structured formatter that enforces consistent field names."""

    def add_fields(
        self,
        log_record: MutableMapping[str, object],
        record: logging.LogRecord,
        message_dict: Mapping[str, object],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        if not log_record.get("level"):
            log_record["level"] = record.levelname
        if not log_record.get("timestamp"):
            log_record["timestamp"] = self.formatTime(record, self.datefmt)
        if not log_record.get("name"):
            log_record["name"] = record.name
        service = getattr(record, "service", None)
        if service and not log_record.get("service"):
            log_record["service"] = service
        for field in DEFAULT_FIELDS:
            if field in message_dict and field not in log_record:
                log_record[field] = message_dict[field]


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that merges contextual fields into each log call."""

    def process(
        self,
        msg: str,
        kwargs: MutableMapping[str, object],
    ) -> tuple[str, MutableMapping[str, object]]:
        extra = kwargs.get("extra") or {}
        merged: MutableMapping[str, object] = dict(self.extra)
        merged.update(extra)
        kwargs["extra"] = merged
        return msg, kwargs


def configure_logging(
    level: str = "INFO",
    *,
    json_logs: bool = True,
    service_name: Optional[str] = None,
) -> logging.Logger:
    """Configure the root logger for a process."""

    logging.captureWarnings(True)
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()

    handler = logging.StreamHandler(stream=sys.stdout)
    if json_logs:
        formatter = JsonFormatter("%(timestamp)s %(level)s %(service)s %(name)s %(message)s")
    else:
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)

    if service_name:
        def _inject_service(record: logging.LogRecord) -> bool:
            if not getattr(record, "service", None):
                record.service = service_name  # type: ignore[attr-defined]
            return True

        handler.addFilter(_inject_service)

    root.addHandler(handler)
    return root


def get_logger(
    name: str,
    *,
    correlation_id: Optional[str] = None,
    service_name: Optional[str] = None,
) -> ContextLogger:
    """Return a logger adapter that injects contextual metadata."""

    extra: MutableMapping[str, object] = {}
    if correlation_id:
        extra["correlation_id"] = correlation_id
    if service_name:
        extra["service"] = service_name
    return ContextLogger(logging.getLogger(name), extra)


__all__ = ["configure_logging", "get_logger", "JsonFormatter", "ContextLogger"]
