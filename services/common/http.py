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

    # Log request initiation
    log.info(
        "http.post_request_start",
        url=url,
        max_retries=max_retries,
        has_files=files is not None,
        has_data=data is not None,
        has_json=json is not None,
        has_headers=headers is not None,
        has_params=params is not None,
        timeout=timeout,
        **extra,
    )

    # Log request details at debug level
    log.debug(
        "http.post_request_details",
        url=url,
        files_count=len(files) if files else 0,
        data_keys=list(data.keys()) if data else [],
        json_keys=list(json.keys()) if isinstance(json, dict) else None,
        headers_keys=list(headers.keys()) if headers else [],
        params_keys=list(params.keys()) if params else [],
        timeout=timeout,
        **extra,
    )

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

        # Log successful response
        log.info(
            "http.post_success",
            url=url,
            status_code=response.status_code,
            response_size=len(response.content) if hasattr(response, "content") else None,
            response_headers_count=len(response.headers) if hasattr(response, "headers") else 0,
            **extra,
        )

        # Log detailed response information at debug level
        log.debug(
            "http.post_response_details",
            url=url,
            status_code=response.status_code,
            response_headers=dict(response.headers) if hasattr(response, "headers") else {},
            response_size=len(response.content) if hasattr(response, "content") else None,
            response_time_ms=(
                response.elapsed.total_seconds() * 1000 if hasattr(response, "elapsed") else None
            ),
            **extra,
        )

        return response

    except Exception as exc:  # noqa: BLE001
        # Log detailed error information
        log.error(
            "http.post_failed",
            url=url,
            error=str(exc),
            error_type=type(exc).__name__,
            max_retries=max_retries,
            **extra,
        )

        # Log additional debug information for troubleshooting
        log.debug(
            "http.post_error_details",
            url=url,
            error=str(exc),
            error_type=type(exc).__name__,
            error_args=getattr(exc, "args", None),
            request_files=files is not None,
            request_data=data is not None,
            request_json=json is not None,
            **extra,
        )
        raise


__all__ = ["post_with_retries"]
