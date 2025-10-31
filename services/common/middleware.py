"""Unified FastAPI middleware for observability (correlation IDs, logging, timing)."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import ClassVar

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

        # 4. Log request start (if not excluded)
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
            # 5. Process request
            response = await call_next(request)

            # 6. Log response with timing (if not excluded)
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

            # 7. Include correlation ID in response headers
            response.headers[self.CORRELATION_HEADER] = correlation_id
            return response

        except Exception as exc:
            # 8. Log errors with timing (if not excluded)
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
