"""Centralized logging utilities for discord-voice-lab services."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import IO, Any

import structlog


def _numeric_level(level: str) -> int:
    value = logging.getLevelName(level.upper())
    if isinstance(value, int):
        return value
    return logging.INFO


Processor = Callable[[Any, str, dict[str, Any]], dict[str, Any]]


def _add_service(service_name: str | None) -> Processor:
    def processor(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        if service_name and "service" not in event_dict:
            event_dict["service"] = service_name
        return event_dict

    return processor


def configure_logging(
    level: str = "INFO",
    *,
    json_logs: bool = True,
    service_name: str | None = None,
    stream: IO[str] | None = None,
) -> None:
    """Configure structlog + stdlib logging for the process.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Whether to output JSON formatted logs (True) or console format (False)
        service_name: Optional service name to include in all log messages
        stream: Optional output stream for logs (defaults to sys.stdout).
                Useful for testing to capture log output to StringIO.

    Example:
        # Production usage
        configure_logging(level="INFO", json_logs=True, service_name="discord")

        # Test usage
        from io import StringIO
        output = StringIO()
        configure_logging(level="INFO", json_logs=True, stream=output)
    """

    numeric_level = _numeric_level(level)
    output_stream = stream if stream is not None else sys.stdout

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

    handler = logging.StreamHandler(output_stream)
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

    # Set Numba logging to WARNING to reduce noise
    numba_logger = logging.getLogger("numba")
    numba_logger.setLevel(logging.WARNING)

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
    correlation_id: str | None = None,
    service_name: str | None = None,
) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound with standard metadata."""

    logger = structlog.stdlib.get_logger(name)
    if correlation_id:
        logger = logger.bind(correlation_id=correlation_id)
    if service_name:
        logger = logger.bind(service=service_name)
    return logger


def bind_correlation_id(
    logger: structlog.stdlib.BoundLogger,
    correlation_id: str | None,
) -> structlog.stdlib.BoundLogger:
    """Bind correlation ID to logger if provided.

    Args:
        logger: Base logger instance
        correlation_id: Optional correlation ID to bind

    Returns:
        Logger with correlation ID bound, or original logger if None
    """
    if correlation_id:
        return logger.bind(correlation_id=correlation_id)
    return logger


@contextmanager
def correlation_context(
    correlation_id: str | None,
) -> Generator[structlog.stdlib.BoundLogger, None, None]:
    """Context manager for correlation ID that ensures cleanup.

    Binds correlation ID to context variables and automatically clears
    them after the operation completes.

    Args:
        correlation_id: Optional correlation ID to bind

    Yields:
        Logger with correlation ID in context

    Example:
        with correlation_context("my-correlation-id") as logger:
            logger.info("processing_request")
            # correlation_id automatically included
        # correlation_id automatically cleaned up
    """
    if correlation_id:
        # Store the previous correlation_id to restore it later
        previous_correlation_id = structlog.contextvars.get_contextvars().get(
            "correlation_id"
        )
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    logger = structlog.stdlib.get_logger()

    try:
        yield logger
    finally:
        if correlation_id:
            # Restore the previous correlation_id or clear if there wasn't one
            if previous_correlation_id is not None:
                structlog.contextvars.bind_contextvars(
                    correlation_id=previous_correlation_id
                )
            else:
                structlog.contextvars.unbind_contextvars("correlation_id")


__all__ = [
    "configure_logging",
    "get_logger",
    "bind_correlation_id",
    "correlation_context",
]
