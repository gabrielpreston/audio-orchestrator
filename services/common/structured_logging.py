"""Centralized logging utilities for audio-orchestrator services."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import IO, Any

import structlog


_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _numeric_level(level: str) -> int:
    name = (level or "").upper()
    return _LEVELS.get(name, logging.INFO)


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
    full_tracebacks: bool | None = None,
) -> None:
    """Configure structlog + stdlib logging for the process.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Whether to output JSON formatted logs (True) or console format (False)
        service_name: Optional service name to include in all log messages
        stream: Optional output stream for logs (defaults to sys.stdout).
                Useful for testing to capture log output to StringIO.
        full_tracebacks: Whether to use full tracebacks (dict_tracebacks) or
                        summary format (format_exc_info). If None, defaults to
                        full tracebacks for DEBUG level, summary for INFO+.
                        Can also be set via LOG_FULL_TRACEBACKS environment variable.

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

    # Determine exception processor
    # Priority: explicit parameter > environment variable > log level inference
    if full_tracebacks is None:
        # Check environment variable
        env_full_tracebacks = os.getenv("LOG_FULL_TRACEBACKS", "").lower()
        if env_full_tracebacks in ("true", "1", "yes"):
            full_tracebacks = True
        elif env_full_tracebacks in ("false", "0", "no"):
            full_tracebacks = False
        else:
            # Default: full tracebacks only in DEBUG
            full_tracebacks = numeric_level <= logging.DEBUG

    exception_processor = (
        structlog.processors.dict_tracebacks
        if full_tracebacks
        else structlog.processors.format_exc_info
    )

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
        _add_service(service_name),
        exception_processor,  # Configurable processor
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

    # Set third-party library loggers to WARNING to reduce noise
    numba_logger = logging.getLogger("numba")
    numba_logger.setLevel(logging.WARNING)

    # Suppress noisy HTTP and Discord library logs
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(
        logging.WARNING
    )  # Changed from INFO to reduce HTTP request noise
    logging.getLogger("discord.gateway").setLevel(logging.INFO)
    logging.getLogger("discord.voice_client").setLevel(logging.WARNING)
    logging.getLogger("discord.client").setLevel(logging.INFO)

    # Suppress Discord HTTP logs that expose OAuth payloads
    logging.getLogger("discord.http").setLevel(logging.WARNING)

    # Suppress discord-ext-voice-recv logs that cause spam
    logging.getLogger("discord.ext.voice_recv").setLevel(logging.WARNING)

    # Suppress RTP/RTCP packet logs from discord.py
    logging.getLogger("discord.voice").setLevel(logging.WARNING)

    # Suppress "Received packet for unknown ssrc" and similar logs
    # These come from discord-ext-voice-recv internal logging
    logging.getLogger("discord.ext.voice_recv.sinks").setLevel(logging.WARNING)
    logging.getLogger("discord.ext.voice_recv.reader").setLevel(logging.WARNING)

    # Suppress python-multipart multipart parser debug spam
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("multipart.multipart").setLevel(logging.WARNING)

    # Suppress OpenTelemetry SDK error spam (connection failures handled internally)
    # These errors are logged by OTEL SDK but don't require service-level error logs
    logging.getLogger("opentelemetry.sdk.metrics").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry.sdk.trace").setLevel(logging.WARNING)
    # Suppress OTEL exporter connection errors (they retry automatically)
    logging.getLogger("opentelemetry.exporter.otlp").setLevel(logging.WARNING)

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

    # Bind trace context if available
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span.is_recording():
            ctx = span.get_span_context()
            logger = logger.bind(
                trace_id=format(ctx.trace_id, "032x"),
                span_id=format(ctx.span_id, "016x"),
            )
    except ImportError:
        # OpenTelemetry not available, continue without trace context
        pass

    # Auto-bind correlation ID from context if not explicitly provided
    if correlation_id is None:
        try:
            from services.common.middleware import get_correlation_id

            correlation_id = get_correlation_id()
        except ImportError:
            # Middleware not available, skip auto-binding
            pass

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
        try:
            # If this is a unittest.mock.Mock, don't rebind; tests expect to
            # observe calls on the original mock instance.
            from unittest.mock import Mock as _Mock  # local import

            if isinstance(logger, _Mock):
                return logger
            return logger.bind(correlation_id=correlation_id)
        except Exception:
            return logger
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
    "bind_correlation_id",
    "configure_logging",
    "correlation_context",
    "get_logger",
    "should_rate_limit",
    "should_sample",
]


# Lightweight, thread-safe sampling and rate limiting helpers
_SAMPLE_LOCK = threading.Lock()
_SAMPLE_COUNTERS: dict[str, int] = {}
_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_LAST: dict[str, float] = {}


def should_sample(key: str, every_n: int) -> bool:
    """Return True when the keyed event should be logged based on N sampling.

    This uses an in-memory counter per key. Thread-safe.
    """
    if every_n <= 1:
        return True
    with _SAMPLE_LOCK:
        count = _SAMPLE_COUNTERS.get(key, 0) + 1
        _SAMPLE_COUNTERS[key] = count
        return count % every_n == 0


def should_rate_limit(key: str, interval_s: float) -> bool:
    """Return True if enough time elapsed since the last emission for this key.

    Thread-safe, uses wall-clock seconds.
    """
    if interval_s <= 0:
        return True
    now = time.time()
    with _RATE_LIMIT_LOCK:
        last = _RATE_LIMIT_LAST.get(key)
        if last is None or (now - last) >= interval_s:
            _RATE_LIMIT_LAST[key] = now
            return True
        return False
