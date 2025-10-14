"""Shared HTTP helpers for async clients."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Optional, Union

import httpx
from structlog.stdlib import BoundLogger

from .logging import get_logger
from .retry import post_with_discord_retry

DEFAULT_BACKOFF_SECONDS = 0.5


async def post_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    files: Optional[Mapping[str, tuple[str, bytes, str]]] = None,
    data: Optional[Mapping[str, Any]] = None,
    json: Optional[Any] = None,
    headers: Optional[Mapping[str, str]] = None,
    params: Optional[Mapping[str, Any]] = None,
    max_retries: int = 3,
    log_fields: Optional[MutableMapping[str, Any]] = None,
    logger: Optional[BoundLogger] = None,
    timeout: Optional[Union[float, httpx.Timeout]] = None,
) -> httpx.Response:
    """
    POST helper that retries with exponential backoff and structured logs.

    This function now uses the improved Discord-optimized retry logic.
    """

    log = logger or get_logger(__name__)
    extra = dict(log_fields or {})

    # Use the new Discord-optimized retry mechanism
    try:
        response = await post_with_discord_retry(
            client,
            url,
            max_attempts=max_retries,
            max_delay=60.0,
            base_delay=1.0,
            jitter=True,
            files=files,
            data=data,
            json=json,
            headers=headers,
            params=params,
            timeout=timeout,
        )

        log.debug(
            "http.post_success",
            url=url,
            status_code=response.status_code,
            **extra,
        )
        return response

    except Exception as exc:  # noqa: BLE001
        log.error(
            "http.post_failed",
            url=url,
            error=str(exc),
            **extra,
        )
        raise


__all__ = ["post_with_retries"]
