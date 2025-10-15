"""Shared HTTP helpers for async clients."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, MutableMapping
from typing import Any

import httpx
from structlog.stdlib import BoundLogger

from .logging import get_logger

DEFAULT_BACKOFF_SECONDS = 0.5


async def post_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    files: Mapping[str, tuple[str, bytes, str]] | None = None,
    data: Mapping[str, Any] | None = None,
    json: Any | None = None,
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
    while True:
        attempt += 1
        try:
            response = await client.post(
                url,
                files=files,
                data=data,
                json=json,
                headers=headers,
                params=params,
                timeout=timeout,
            )
            response.raise_for_status()
            log.debug(
                "http.post_success",
                url=url,
                attempt=attempt,
                status_code=response.status_code,
                **extra,
            )
            return response
        except Exception as exc:
            if attempt >= max_retries:
                log.error(
                    "http.post_failed",
                    url=url,
                    attempt=attempt,
                    error=str(exc),
                    **extra,
                )
                raise
            backoff = min(DEFAULT_BACKOFF_SECONDS * (2 ** (attempt - 1)), 10.0)
            log.warning(
                "http.post_retry",
                url=url,
                attempt=attempt,
                backoff=backoff,
                error=str(exc),
                **extra,
            )
            await asyncio.sleep(backoff)


__all__ = ["post_with_retries"]
