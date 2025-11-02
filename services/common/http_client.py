"""Shared HTTP helpers for async clients."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, MutableMapping
from typing import Any

import httpx
from structlog.stdlib import BoundLogger

from .http_headers import inject_correlation_id
from .structured_logging import get_logger


DEFAULT_BACKOFF_SECONDS = 0.5


async def post_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    files: Mapping[str, tuple[str, bytes, str]] | None = None,
    data: Mapping[str, Any] | None = None,
    json: Any | None = None,
    content: bytes | None = None,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, Any] | None = None,
    max_retries: int = 3,
    log_fields: MutableMapping[str, Any] | None = None,
    logger: BoundLogger | None = None,
    timeout: float | httpx.Timeout | None = None,
) -> httpx.Response:
    """POST helper that retries with exponential backoff and structured logs."""

    attempt = 0
    log = logger or get_logger(__name__)
    extra = dict(log_fields or {})
    # Auto-inject correlation ID from context using shared utility
    request_headers = inject_correlation_id(headers)

    # Calculate payload size for logging
    payload_size = 0
    if files:
        payload_size = sum(
            len(f[1]) if isinstance(f[1], bytes) else 0 for f in files.values()
        )
    elif content:
        payload_size = len(content)
    elif json:
        import json as json_module

        payload_size = len(json_module.dumps(json).encode())

    while True:
        attempt += 1
        # Log first attempt with decision context
        if attempt == 1:
            log.info(
                "http.post_attempt",
                url=url,
                attempt=attempt,
                max_retries=max_retries,
                payload_size=payload_size,
                timeout=timeout,
                decision="making_http_request",
                **extra,
            )

        try:
            response = await client.post(
                url,
                files=files,
                data=data,
                json=json,
                content=content,
                headers=request_headers,
                params=params,
                timeout=timeout,
            )
            response.raise_for_status()
            log.info(
                "http.post_success",
                url=url,
                attempt=attempt,
                status_code=response.status_code,
                decision="request_succeeded",
                **extra,
            )
            return response
        except Exception as exc:
            if attempt >= max_retries:
                log.error(
                    "http.post_failed",
                    url=url,
                    attempt=attempt,
                    max_retries=max_retries,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    decision="max_retries_exceeded",
                    **extra,
                )
                raise
            backoff = min(DEFAULT_BACKOFF_SECONDS * (2 ** (attempt - 1)), 10.0)
            log.warning(
                "http.post_retry",
                url=url,
                attempt=attempt,
                max_retries=max_retries,
                backoff=backoff,
                error=str(exc),
                error_type=type(exc).__name__,
                decision="retrying_after_error",
                **extra,
            )
            await asyncio.sleep(backoff)


__all__ = ["post_with_retries"]
