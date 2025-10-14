"""Advanced retry utilities with Discord API rate limit awareness."""

from __future__ import annotations

import asyncio
import random
from typing import Any, Optional

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_random,
    retry_if_exception_type,
)
from tenacity.wait import wait_combine

from .logging import get_logger

logger = get_logger(__name__)


class DiscordRateLimitError(httpx.HTTPStatusError):
    """Raised when Discord API returns a 429 rate limit error."""

    def __init__(self, response: httpx.Response, retry_after: Optional[float] = None):
        super().__init__(response)
        self.retry_after = retry_after


def _is_discord_rate_limit_error(exception: Exception) -> bool:
    """Check if the exception is a Discord rate limit error."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code == 429
    return False


def _extract_retry_after(exception: Exception) -> Optional[float]:
    """Extract retry_after value from Discord rate limit response."""
    if isinstance(exception, httpx.HTTPStatusError) and exception.response.status_code == 429:
        retry_after = exception.response.headers.get("retry-after")
        if retry_after:
            try:
                return float(retry_after)
            except (ValueError, TypeError):
                pass
    return None


async def _discord_rate_limit_wait(exception: Exception) -> float:
    """Calculate wait time for Discord rate limit errors."""
    retry_after = _extract_retry_after(exception)
    if retry_after:
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0.1, 0.5)
        return retry_after + jitter
    return 1.0


def create_discord_retry_strategy(
    max_attempts: int = 5,
    max_delay: float = 60.0,
    base_delay: float = 1.0,
    jitter: bool = True,
) -> AsyncRetrying:
    """
    Create a retry strategy optimized for Discord API rate limits.

    Args:
        max_attempts: Maximum number of retry attempts
        max_delay: Maximum delay between retries in seconds
        base_delay: Base delay for exponential backoff
        jitter: Whether to add random jitter to prevent thundering herd

    Returns:
        Configured AsyncRetrying instance
    """
    # Wait strategy: exponential backoff with jitter
    if jitter:
        wait_strategy = wait_combine(
            wait_exponential(multiplier=base_delay, max=max_delay),
            wait_random(min=0.1, max=1.0),
        )
    else:
        wait_strategy = wait_exponential(multiplier=base_delay, max=max_delay)

    return AsyncRetrying(
        # Stop conditions
        stop=(stop_after_attempt(max_attempts) | stop_after_delay(max_delay * 2)),  # Total time limit
        # Wait strategy
        wait=wait_strategy,
        # Retry conditions
        retry=(
            retry_if_exception_type(httpx.HTTPStatusError)
            | retry_if_exception_type(httpx.ConnectError)
            | retry_if_exception_type(httpx.TimeoutException)
            | retry_if_exception_type(httpx.RemoteProtocolError)
        ),
        # Custom wait for Discord rate limits
        wait_func=_discord_rate_limit_wait,
        # Retry on specific status codes
        retry_error_callback=lambda retry_state: logger.warning(
            "discord.retry_exhausted",
            attempt=retry_state.attempt_number,
            exception=str(retry_state.outcome.exception()) if retry_state.outcome else None,
        ),
    )


async def http_request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_attempts: int = 5,
    max_delay: float = 60.0,
    base_delay: float = 1.0,
    jitter: bool = True,
    **kwargs: Any,
) -> httpx.Response:
    """
    Make an HTTP request with Discord-optimized retry logic.

    Args:
        client: HTTP client to use
        method: HTTP method
        url: Request URL
        max_attempts: Maximum retry attempts
        max_delay: Maximum delay between retries
        base_delay: Base delay for exponential backoff
        jitter: Whether to add jitter
        **kwargs: Additional arguments for httpx request

    Returns:
        HTTP response

    Raises:
        RetryError: If all retry attempts are exhausted
        httpx.HTTPStatusError: For non-retryable HTTP errors
    """
    retry_strategy = create_discord_retry_strategy(
        max_attempts=max_attempts,
        max_delay=max_delay,
        base_delay=base_delay,
        jitter=jitter,
    )

    async def _make_request():
        response = await client.request(method, url, **kwargs)

        # Handle Discord rate limits specially
        if response.status_code == 429:
            retry_after = response.headers.get("retry-after")
            if retry_after:
                try:
                    wait_time = float(retry_after)
                    logger.warning(
                        "discord.rate_limit_hit",
                        url=url,
                        retry_after=wait_time,
                        headers=dict(response.headers),
                    )
                    await asyncio.sleep(wait_time + random.uniform(0.1, 0.5))
                except (ValueError, TypeError):
                    pass

            # Raise as rate limit error for special handling
            raise DiscordRateLimitError(response, retry_after)

        response.raise_for_status()
        return response

    try:
        async for attempt in retry_strategy:
            with attempt:
                return await _make_request()
    except RetryError as exc:
        logger.error(
            "discord.http_retry_exhausted",
            url=url,
            method=method,
            attempts=exc.retry_state.attempt_number,
            last_exception=(
                str(exc.retry_state.outcome.exception()) if exc.retry_state.outcome else None
            ),
        )
        raise


async def post_with_discord_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_attempts: int = 5,
    max_delay: float = 60.0,
    base_delay: float = 1.0,
    jitter: bool = True,
    **kwargs: Any,
) -> httpx.Response:
    """
    POST request with Discord-optimized retry logic.

    This is a convenience wrapper around http_request_with_retry for POST requests.
    """
    return await http_request_with_retry(
        client,
        "POST",
        url,
        max_attempts=max_attempts,
        max_delay=max_delay,
        base_delay=base_delay,
        jitter=jitter,
        **kwargs,
    )


async def get_with_discord_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_attempts: int = 5,
    max_delay: float = 60.0,
    base_delay: float = 1.0,
    jitter: bool = True,
    **kwargs: Any,
) -> httpx.Response:
    """
    GET request with Discord-optimized retry logic.

    This is a convenience wrapper around http_request_with_retry for GET requests.
    """
    return await http_request_with_retry(
        client,
        "GET",
        url,
        max_attempts=max_attempts,
        max_delay=max_delay,
        base_delay=base_delay,
        jitter=jitter,
        **kwargs,
    )


def create_generic_retry_strategy(
    max_attempts: int = 3,
    max_delay: float = 30.0,
    base_delay: float = 1.0,
    jitter: bool = True,
) -> AsyncRetrying:
    """
    Create a generic retry strategy for non-Discord HTTP calls.

    Args:
        max_attempts: Maximum number of retry attempts
        max_delay: Maximum delay between retries in seconds
        base_delay: Base delay for exponential backoff
        jitter: Whether to add random jitter to prevent thundering herd

    Returns:
        Configured AsyncRetrying instance
    """
    # Wait strategy: exponential backoff with jitter
    if jitter:
        wait_strategy = wait_combine(
            wait_exponential(multiplier=base_delay, max=max_delay),
            wait_random(min=0.1, max=0.5),
        )
    else:
        wait_strategy = wait_exponential(multiplier=base_delay, max=max_delay)

    return AsyncRetrying(
        # Stop conditions
        stop=(stop_after_attempt(max_attempts) | stop_after_delay(max_delay * 2)),
        # Wait strategy
        wait=wait_strategy,
        # Retry conditions
        retry=(
            retry_if_exception_type(httpx.HTTPStatusError)
            | retry_if_exception_type(httpx.ConnectError)
            | retry_if_exception_type(httpx.TimeoutException)
            | retry_if_exception_type(httpx.RemoteProtocolError)
        ),
        # Retry error callback
        retry_error_callback=lambda retry_state: logger.warning(
            "http.retry_exhausted",
            attempt=retry_state.attempt_number,
            exception=str(retry_state.outcome.exception()) if retry_state.outcome else None,
        ),
    )


async def http_request_with_generic_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_attempts: int = 3,
    max_delay: float = 30.0,
    base_delay: float = 1.0,
    jitter: bool = True,
    **kwargs: Any,
) -> httpx.Response:
    """
    Make an HTTP request with generic retry logic for non-Discord services.

    Args:
        client: HTTP client to use
        method: HTTP method
        url: Request URL
        max_attempts: Maximum retry attempts
        max_delay: Maximum delay between retries
        base_delay: Base delay for exponential backoff
        jitter: Whether to add jitter
        **kwargs: Additional arguments for httpx request

    Returns:
        HTTP response

    Raises:
        RetryError: If all retry attempts are exhausted
        httpx.HTTPStatusError: For non-retryable HTTP errors
    """
    retry_strategy = create_generic_retry_strategy(
        max_attempts=max_attempts,
        max_delay=max_delay,
        base_delay=base_delay,
        jitter=jitter,
    )

    try:
        async for attempt in retry_strategy:
            with attempt:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
    except RetryError as exc:
        logger.error(
            "http.retry_exhausted",
            url=url,
            method=method,
            attempts=exc.retry_state.attempt_number,
            last_exception=(
                str(exc.retry_state.outcome.exception()) if exc.retry_state.outcome else None
            ),
        )
        raise


async def post_with_generic_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_attempts: int = 3,
    max_delay: float = 30.0,
    base_delay: float = 1.0,
    jitter: bool = True,
    **kwargs: Any,
) -> httpx.Response:
    """
    POST request with generic retry logic.

    This is a convenience wrapper around http_request_with_generic_retry for POST requests.
    """
    return await http_request_with_generic_retry(
        client,
        "POST",
        url,
        max_attempts=max_attempts,
        max_delay=max_delay,
        base_delay=base_delay,
        jitter=jitter,
        **kwargs,
    )


async def stream_with_generic_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_attempts: int = 3,
    max_delay: float = 30.0,
    base_delay: float = 1.0,
    jitter: bool = True,
    **kwargs: Any,
) -> httpx.Response:
    """
    Make a streaming HTTP request with generic retry logic.

    This is designed for requests that need to be retried but use streaming responses.
    The retry logic is applied to the initial connection, not the streaming itself.

    Args:
        client: HTTP client to use
        method: HTTP method
        url: Request URL
        max_attempts: Maximum retry attempts
        max_delay: Maximum delay between retries
        base_delay: Base delay for exponential backoff
        jitter: Whether to add jitter
        **kwargs: Additional arguments for httpx request

    Returns:
        HTTP response (streaming)

    Raises:
        RetryError: If all retry attempts are exhausted
        httpx.HTTPStatusError: For non-retryable HTTP errors
    """
    retry_strategy = create_generic_retry_strategy(
        max_attempts=max_attempts,
        max_delay=max_delay,
        base_delay=base_delay,
        jitter=jitter,
    )

    try:
        async for attempt in retry_strategy:
            with attempt:
                # For streaming requests, we need to test the connection first
                # by making a HEAD request to check if the service is available
                try:
                    test_response = await client.request("HEAD", url, **kwargs)
                    test_response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code >= 500:
                        # Server error, retry
                        raise
                    else:
                        # Client error, don't retry
                        raise
                
                # If HEAD request succeeds, make the actual streaming request
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
    except RetryError as exc:
        logger.error(
            "http.stream_retry_exhausted",
            url=url,
            method=method,
            attempts=exc.retry_state.attempt_number,
            last_exception=(
                str(exc.retry_state.outcome.exception()) if exc.retry_state.outcome else None
            ),
        )
        raise


__all__ = [
    "DiscordRateLimitError",
    "create_discord_retry_strategy",
    "http_request_with_retry",
    "post_with_discord_retry",
    "get_with_discord_retry",
]
