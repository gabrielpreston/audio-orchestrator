"""Centralized logging utilities for discord-voice-lab services."""

from __future__ import annotations

import logging
import sys
import traceback
import warnings
from typing import Any, Callable, Dict, Optional

import structlog

from .correlation import ensure_correlation_id


def _numeric_level(level: str) -> int:
    value = logging.getLevelName(level.upper())
    if isinstance(value, int):
        return value
    return logging.INFO


Processor = Callable[[Any, str, dict[str, Any]], dict[str, Any]]


def _add_service(service_name: Optional[str]) -> Processor:
    def processor(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        if service_name and "service" not in event_dict:
            event_dict["service"] = service_name
        return event_dict

    return processor


def configure_logging(
    level: str = "INFO",
    *,
    json_logs: bool = True,
    service_name: Optional[str] = None,
) -> None:
    """Configure structlog + stdlib logging for the process."""

    numeric_level = _numeric_level(level)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
        _add_service(service_name),
        structlog.processors.dict_tracebacks,
    ]
    if json_logs:
        formatter_processors = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ]
    else:
        formatter_processors = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(),
        ]

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=formatter_processors,
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(numeric_level)
    logging.captureWarnings(True)

    # Suppress specific deprecation warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="webrtcvad")
    warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(
    name: str,
    *,
    correlation_id: Optional[str] = None,
    service_name: Optional[str] = None,
) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound with standard metadata."""

    logger = structlog.stdlib.get_logger(name)

    # Use provided correlation_id or ensure one exists in context
    if correlation_id is None:
        correlation_id = ensure_correlation_id()

    if correlation_id:
        logger = logger.bind(correlation_id=correlation_id)
    if service_name:
        logger = logger.bind(service=service_name)
    return logger


def log_exception(
    logger: structlog.stdlib.BoundLogger,
    exc: Exception,
    context: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Log exceptions in structured format."""
    logger.error(
        "exception.occurred",
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        traceback=traceback.format_exc(),
        context=context or {},
        correlation_id=correlation_id,
    )


def log_service_startup(
    logger: structlog.stdlib.BoundLogger,
    service_name: str,
    **kwargs: Any,
) -> None:
    """Standardized service startup logging."""
    logger.info(
        "service.startup",
        service=service_name,
        status="started",
        **kwargs,
    )


def log_service_health(
    logger: structlog.stdlib.BoundLogger,
    service_name: str,
    status: str = "healthy",
    **kwargs: Any,
) -> None:
    """Log service health status."""
    logger.info(
        "service.health_check",
        service=service_name,
        status=status,
        **kwargs,
    )


__all__ = [
    "configure_logging",
    "get_logger",
    "log_exception",
    "log_service_startup",
    "log_service_health",
]
