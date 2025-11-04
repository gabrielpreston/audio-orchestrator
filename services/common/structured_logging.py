"""Centralized logging utilities for audio-orchestrator services."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
import warnings
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

    # Suppress FutureWarnings from third-party libraries (known issues, will be resolved by dependency updates)
    warnings.filterwarnings(
        "ignore",
        category=FutureWarning,
        module="bark.generation",
        message=".*torch.load.*weights_only.*",
    )
    warnings.filterwarnings(
        "ignore",
        category=FutureWarning,
        module="torch.nn.utils.weight_norm",
        message=".*parametrizations.weight_norm.*",
    )

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
    # Suppress pkg_resources warnings from OpenTelemetry instrumentation
    # These warnings appear during import and don't require action
    logging.getLogger("opentelemetry.instrumentation.dependencies").setLevel(
        logging.ERROR
    )

    # Suppress pkg_resources deprecation warnings (setuptools 81+ migration)
    # These warnings appear frequently during import and don't require action
    logging.getLogger("pkg_resources").setLevel(logging.ERROR)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure uvicorn access logger for structured JSON logging
    # This sets up structured JSON format matching other service logs
    _configure_uvicorn_access_logger(output_stream, json_logs, service_name)


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


def _parse_uvicorn_access_log(message: str) -> dict[str, Any]:
    """Parse uvicorn access log message into structured fields.

    Uvicorn access logs follow format: "IP:PORT - \"METHOD PATH HTTP_VERSION\" STATUS_CODE"
    Example: '172.18.0.15:46132 - "GET /health/ready HTTP/1.1" 503'

    Args:
        message: Raw uvicorn access log message

    Returns:
        Dictionary with parsed fields: client_ip, client_port, method, path,
        http_version, status_code, and raw message
    """
    import re

    # Pattern: IP:PORT - "METHOD PATH HTTP/VERSION" STATUS_CODE
    # Example: 172.18.0.15:46132 - "GET /health/ready HTTP/1.1" 503
    pattern = r'^(.+?):(\d+) - "(\w+) ([^"]+) (HTTP/\d\.\d)" (\d+)$'
    match = re.match(pattern, message.strip())

    if match:
        client_ip, client_port, method, path, http_version, status_code = match.groups()
        return {
            "event": "uvicorn.access",
            "client_ip": client_ip,
            "client_port": int(client_port),
            "method": method,
            "path": path,
            "http_version": http_version,
            "status_code": int(status_code),
        }

    # Fallback: return message as-is if parsing fails
    return {
        "event": "uvicorn.access",
        "message": message,
    }


def _uvicorn_access_processor(
    _logger: Any, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Processor to convert uvicorn access log messages to structured format.

    This processor extracts the message from event_dict (which comes from stdlib logging),
    parses it, and replaces it with structured fields.

    For stdlib logging, the message is typically in the 'event' key.

    Args:
        _logger: Logger instance (required by structlog processor signature, unused)
        _method_name: Method name (required by structlog processor signature, unused)
        event_dict: Event dictionary containing log data
    """
    # Get message from event_dict (stdlib logging puts it in 'event')
    message = event_dict.get("event", "")
    if not message:
        # Fallback: check 'message' key
        message = event_dict.get("message", "")

    # Only parse if it looks like a uvicorn access log and we haven't already parsed it
    if isinstance(message, str) and message.strip() and "status_code" not in event_dict:
        parsed = _parse_uvicorn_access_log(message)
        # Replace message/event with structured fields
        event_dict.pop("event", None)
        event_dict.pop("message", None)
        event_dict.update(parsed)

    return event_dict


class HealthCheckFilter(logging.Filter):
    """Filter to reduce health check spam in uvicorn access logs.

    Health check endpoints are called frequently by monitoring tools and don't
    need to be logged at INFO level. This filter:
    - Suppresses health check logs when status is 200 (healthy)
    - Suppresses health check logs when status is 503 (expected during startup/dependency unready)
    - Allows other endpoints through normally
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter health check logs based on path and status code."""
        # Check if structured fields are already available (from processor)
        path = getattr(record, "path", None)
        status_code = getattr(record, "status_code", None)

        # If not available as attributes, try parsing from message
        if path is None or status_code is None:
            message = getattr(record, "msg", "")
            if not isinstance(message, str):
                # If msg is a format string with args, get the formatted message
                try:
                    message = record.getMessage()
                except Exception:
                    return True  # Can't parse, allow through

            # Check if this looks like an access log and parse it
            if '"' in message and "HTTP" in message:
                parsed = _parse_uvicorn_access_log(message)
                path = parsed.get("path")
                status_code = parsed.get("status_code")
                # Ensure status_code is an int for comparison
                if status_code is not None:
                    try:
                        status_code = int(status_code)
                    except (ValueError, TypeError):
                        status_code = None
            else:
                # Not an access log format, allow through
                return True

        # Filter health check endpoints
        if path and path.startswith("/health/"):
            # Ensure status_code is comparable
            if status_code is None:
                return True  # Can't determine status, allow through
            # Suppress successful health checks (200) - these are noise
            if status_code == 200:
                return False
            # Suppress 503 during startup/degraded - expected behavior, too noisy
            if status_code == 503:
                return False

        return True


def _configure_uvicorn_access_logger(
    stream: IO[str], json_logs: bool, service_name: str | None
) -> None:
    """Configure uvicorn access logger for structured JSON logging.

    This function configures the uvicorn.access logger to emit structured JSON
    logs matching the format used by other service logs. It wraps stdlib logging
    messages to go through structlog processors.

    Args:
        stream: Output stream for log handlers
        json_logs: Whether to use JSON format (True) or console format (False)
        service_name: Optional service name to include in logs
    """
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False  # Prevent double logging through root logger

    # Add filter to reduce health check spam
    access_logger.addFilter(HealthCheckFilter())

    # Shared processors for access logs (process stdlib logs into structured format)
    shared_processors = [
        structlog.stdlib.add_log_level,  # Add log level from stdlib
        structlog.stdlib.add_logger_name,  # Add logger name
        structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
        _add_service(service_name),
        _uvicorn_access_processor,  # Parse access log messages into structured fields
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

    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=formatter_processors,
        )
    )
    # Also add filter to handler (defense in depth)
    handler.addFilter(HealthCheckFilter())

    # Clear existing handlers and add our structured handler
    access_logger.handlers = [handler]


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
