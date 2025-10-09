"""Shared HTTP helpers for async clients."""

from __future__ import annotations

import asyncio
from typing import Any, Mapping, MutableMapping, Optional

import httpx

from structlog.stdlib import BoundLogger

from .logging import get_logger

DEFAULT_BACKOFF_SECONDS = 0.5


async def post_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    files: Optional[Mapping[str, tuple[str, bytes, str]]] = None,
    data: Optional[Mapping[str, Any]] = None,
    json: Optional[Any] = None,
    headers: Optional[Mapping[str, str]] = None,
    max_retries: int = 3,
    log_fields: Optional[MutableMapping[str, Any]] = None,
    logger: Optional[BoundLogger] = None,
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
        except Exception as exc:  # noqa: BLE001
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
