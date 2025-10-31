"""Unified FastAPI middleware for observability (correlation IDs, logging, timing, metrics)."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any, ClassVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from services.common.structured_logging import get_logger

logger = get_logger(__name__)

# Context variable for storing correlation ID in async context
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    """Get correlation ID from async context."""
    return _correlation_id.get()


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Unified middleware for correlation IDs, request/response logging, and timing.

    This middleware combines:
    - Correlation ID extraction/generation and propagation
    - Request/response logging with timing
    - Automatic correlation_id binding to logger context
    """

    CORRELATION_HEADER = "X-Correlation-ID"
    # Paths to exclude from verbose logging
    EXCLUDED_PATHS: ClassVar[set[str]] = {"/health/live", "/health/ready", "/metrics"}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # 1. Extract or generate correlation ID
        correlation_id = (
            request.headers.get(self.CORRELATION_HEADER)
            or request.query_params.get("correlation_id")
            or str(uuid.uuid4())
        )

        # 2. Store in context variable for this request
        _correlation_id.set(correlation_id)

        # 3. Determine if we should log (exclude health checks and metrics)
        should_log = request.url.path not in self.EXCLUDED_PATHS
        start_time = time.perf_counter() if should_log else None

        # 4. Get HTTP metrics from app state (if available)
        http_metrics: dict[str, Any] | None = None
        service_name: str | None = None
        if hasattr(request.app, "state"):
            http_metrics = getattr(request.app.state, "http_metrics", None)
            service_name = getattr(request.app.state, "service_name", None)
            if should_log and not http_metrics:
                logger.debug(
                    "metrics.not_available",
                    has_state=hasattr(request.app, "state"),
                    service=service_name,
                    path=request.url.path,
                )

        # 5. Log request start (if not excluded)
        if should_log:
            logger.info(
                "http.request.start",
                method=request.method,
                path=request.url.path,
                correlation_id=correlation_id,
                query_params=dict(request.query_params)
                if request.query_params
                else None,
            )

        try:
            # 6. Process request
            response = await call_next(request)

            # 7. Record HTTP metrics
            if http_metrics and start_time:
                duration_seconds = time.perf_counter() - start_time
                status = "success" if 200 <= response.status_code < 400 else "error"
                method = request.method
                route = request.url.path

                try:
                    # Record request count
                    if "http_requests" in http_metrics:
                        attributes: dict[str, Any] = {
                            "method": method,
                            "route": route,
                            "status": status,
                        }
                        if service_name:
                            attributes["service"] = service_name
                        http_metrics["http_requests"].add(1, attributes=attributes)
                        logger.debug(
                            "metric.recorded",
                            metric="http_requests_total",
                            value=1,
                            attributes=attributes,
                            service=service_name,
                        )
                    else:
                        logger.warning(
                            "metric.missing_key",
                            key="http_requests",
                            available_keys=list(http_metrics.keys())
                            if http_metrics
                            else [],
                            service=service_name,
                        )

                    # Record request duration
                    if "http_request_duration" in http_metrics:
                        attributes = {
                            "method": method,
                            "route": route,
                        }
                        if service_name:
                            attributes["service"] = service_name
                        http_metrics["http_request_duration"].record(
                            duration_seconds, attributes=attributes
                        )
                        logger.debug(
                            "metric.recorded",
                            metric="http_request_duration_seconds",
                            value=duration_seconds,
                            attributes=attributes,
                            service=service_name,
                        )
                    else:
                        logger.warning(
                            "metric.missing_key",
                            key="http_request_duration",
                            available_keys=list(http_metrics.keys())
                            if http_metrics
                            else [],
                            service=service_name,
                        )
                except Exception as metric_exc:
                    logger.exception(
                        "metric.recording_failed",
                        error=str(metric_exc),
                        error_type=type(metric_exc).__name__,
                        service=service_name,
                        method=method,
                        route=route,
                    )

            # 8. Log response with timing (if not excluded)
            if should_log and start_time:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.info(
                    "http.request.complete",
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=round(duration_ms, 2),
                    correlation_id=correlation_id,
                )

            # 9. Include correlation ID in response headers
            response.headers[self.CORRELATION_HEADER] = correlation_id
            return response

        except Exception as exc:
            # 10. Record error metrics
            if http_metrics and start_time:
                duration_seconds = (
                    (time.perf_counter() - start_time) if start_time else 0
                )
                method = request.method
                route = request.url.path

                # Record request count (error)
                if "http_requests" in http_metrics:
                    attributes = {
                        "method": method,
                        "route": route,
                        "status": "error",
                    }
                    if service_name:
                        attributes["service"] = service_name
                    http_metrics["http_requests"].add(1, attributes=attributes)

                # Record request duration (error)
                if "http_request_duration" in http_metrics:
                    attributes = {
                        "method": method,
                        "route": route,
                    }
                    if service_name:
                        attributes["service"] = service_name
                    http_metrics["http_request_duration"].record(
                        duration_seconds, attributes=attributes
                    )

            # 11. Log errors with timing (if not excluded)
            if should_log and start_time:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error(
                    "http.request.error",
                    method=request.method,
                    path=request.url.path,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    duration_ms=round(duration_ms, 2),
                    correlation_id=correlation_id,
                )
            raise


__all__ = ["ObservabilityMiddleware", "get_correlation_id"]
