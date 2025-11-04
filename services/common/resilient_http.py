"""Resilient HTTP client with circuit breaker and health checks."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .http_client import post_with_retries
from .http_headers import inject_correlation_id
from .structured_logging import get_logger


class ServiceUnavailableError(Exception):
    """Raised when service is unavailable."""


class ResilientHTTPClient:
    """HTTP client with circuit breaker and health checks."""

    def __init__(
        self,
        service_name: str,
        base_url: str,
        circuit_config: CircuitBreakerConfig | None = None,
        timeout: float = 30.0,
        health_check_interval: float = 10.0,
        health_check_startup_grace_seconds: float = 30.0,
        health_check_timeout: float = 10.0,
        max_connections: int = 10,
        max_keepalive_connections: int = 5,
    ):
        self._service_name = service_name
        self._base_url = base_url.rstrip("/")
        self._circuit = CircuitBreaker(
            service_name, circuit_config or CircuitBreakerConfig()
        )
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout
        self._logger = get_logger(__name__)
        # Initialize to current time to prevent stampede on first check
        self._last_health_check: float = time.time()
        self._health_check_interval = health_check_interval
        self._health_check_startup_grace_seconds = health_check_startup_grace_seconds
        self._health_check_timeout = health_check_timeout
        self._service_start_time: float = time.time()
        self._is_healthy: bool = False
        self._max_connections = max_connections
        self._max_keepalive_connections = max_keepalive_connections
        self._last_timeout_log: float = 0.0  # Track last timeout log to reduce noise
        self._health_check_lock: asyncio.Lock = asyncio.Lock()
        self._consecutive_failures: int = (
            0  # Track consecutive failures for exponential backoff
        )
        self._max_backoff_interval: float = 120.0  # Max interval of 2 minutes

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            limits = httpx.Limits(
                max_connections=self._max_connections,
                max_keepalive_connections=self._max_keepalive_connections,
            )
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                limits=limits,
            )
        return self._client

    def _get_effective_check_interval(self) -> float:
        """Get effective check interval based on startup phase.

        Returns:
            - 1.0s during startup phase (first 120s)
            - Existing exponential backoff logic after 120s
        """
        elapsed = time.time() - self._service_start_time
        if elapsed < 120.0:
            return 1.0  # Startup: check every 1s
        else:
            # Use existing exponential backoff logic
            base = self._health_check_interval
            backoff = min(
                2.0**self._consecutive_failures, self._max_backoff_interval / base
            )
            return base * backoff

    async def check_health(self) -> bool:
        """Check if service is healthy via /health/ready.

        Uses async lock to prevent concurrent health checks and exponential backoff
        on consecutive failures to reduce traffic to unhealthy services.
        """
        now = time.time()

        # Fast path: skip if checked recently (outside lock for performance)
        # Calculate effective interval with startup-aware logic
        effective_interval = self._get_effective_check_interval()

        if now - self._last_health_check < effective_interval:
            return self._is_healthy

        # Acquire lock to prevent concurrent health checks
        async with self._health_check_lock:
            # Re-check interval inside lock (another call may have updated it)
            # Recalculate effective interval in case it changed
            effective_interval = self._get_effective_check_interval()
            if now - self._last_health_check < effective_interval:
                return self._is_healthy

            # Check if we're still in startup grace period
            elapsed_since_startup = now - self._service_start_time
            if elapsed_since_startup < self._health_check_startup_grace_seconds:
                self._logger.debug(
                    "resilient_http.health_check_grace_period",
                    service=self._service_name,
                    elapsed_seconds=elapsed_since_startup,
                    grace_period=self._health_check_startup_grace_seconds,
                )
                # During grace period, assume healthy to allow startup
                self._is_healthy = True
                self._last_health_check = now
                self._consecutive_failures = 0  # Reset failures during grace
                return True

            try:
                client = await self._get_client()
                response = await client.get(
                    f"{self._base_url}/health/ready", timeout=self._health_check_timeout
                )

                is_healthy: bool = response.status_code == 200
                self._is_healthy = is_healthy
                self._last_health_check = now

                if is_healthy:
                    # Reset backoff on success
                    if self._consecutive_failures > 0:
                        self._logger.debug(
                            "resilient_http.health_check_recovered",
                            service=self._service_name,
                            consecutive_failures=self._consecutive_failures,
                        )
                    self._consecutive_failures = 0
                    self._last_timeout_log = 0.0
                else:
                    # Increment failure count for exponential backoff
                    self._consecutive_failures += 1
                    # Calculate next check interval with new failure count
                    base_interval = self._health_check_interval
                    next_backoff = min(
                        2.0**self._consecutive_failures,
                        self._max_backoff_interval / base_interval,
                    )
                    next_check_interval = base_interval * next_backoff
                    elapsed_since_startup = now - self._service_start_time
                    # 503 during startup is expected (service not ready yet)
                    is_expected_during_startup = (
                        response.status_code == 503 and elapsed_since_startup < 120.0
                    )
                    log_level = "debug" if is_expected_during_startup else "warning"
                    getattr(self._logger, log_level)(
                        "resilient_http.health_check_failed",
                        service=self._service_name,
                        status_code=response.status_code,
                        url=f"{self._base_url}/health/ready",
                        elapsed_since_startup_seconds=round(elapsed_since_startup, 1),
                        is_expected_during_startup=is_expected_during_startup,
                        consecutive_failures=self._consecutive_failures,
                        next_check_interval=next_check_interval,
                    )

                return is_healthy

            except Exception as exc:
                self._is_healthy = False
                self._last_health_check = now
                # Increment failure count for exponential backoff
                self._consecutive_failures += 1
                # Calculate next check interval with new failure count
                base_interval = self._health_check_interval
                next_backoff = min(
                    2.0**self._consecutive_failures,
                    self._max_backoff_interval / base_interval,
                )
                next_check_interval = base_interval * next_backoff

                # Categorize errors and determine logging behavior
                error_type = type(exc).__name__
                is_timeout = error_type in ("ReadTimeout", "ConnectTimeout", "Timeout")
                is_connection_error = error_type in ("ConnectError", "ConnectTimeout")

                # Check if we're still in startup phase (extended grace for connection errors)
                elapsed_since_startup = now - self._service_start_time
                startup_grace_period = max(
                    self._health_check_startup_grace_seconds,
                    60.0,  # Extended grace period for connection errors (services may be starting)
                )
                is_startup_phase = (
                    elapsed_since_startup < startup_grace_period and is_connection_error
                )

                # Determine log level based on error type and startup phase
                if is_startup_phase:
                    # Connection errors during startup are expected - use debug level
                    log_level = "debug"
                    log_interval = 60.0  # Log max once per minute during startup
                elif is_timeout:
                    log_level = "debug"
                    log_interval = 30.0
                else:
                    # Other errors are unexpected - always log at warning
                    log_level = "warning"
                    log_interval = 0.0  # Always log

                # Rate limit expected errors (timeouts and connection errors during startup)
                should_log = (
                    log_interval == 0.0  # Always log unexpected errors
                    or (now - self._last_timeout_log) >= log_interval
                )

                if should_log:
                    getattr(self._logger, log_level)(
                        "resilient_http.health_check_error",
                        service=self._service_name,
                        url=f"{self._base_url}/health/ready",
                        error=str(exc),
                        error_type=error_type,
                        is_timeout=is_timeout,
                        is_connection_error=is_connection_error,
                        is_startup_phase=is_startup_phase,
                        elapsed_since_startup_seconds=round(elapsed_since_startup, 1),
                        startup_grace_period_seconds=startup_grace_period,
                        consecutive_failures=self._consecutive_failures,
                        next_check_interval=next_check_interval,
                    )
                    if log_interval > 0.0:
                        self._last_timeout_log = now

                return False

    async def post_with_retry(
        self,
        endpoint: str,
        *,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        data: dict[str, Any] | None = None,
        json: Any | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        max_retries: int = 3,
        log_fields: dict[str, Any] | None = None,
        logger: Any | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> httpx.Response:
        """POST with circuit breaker protection."""
        request_logger = logger or self._logger

        # Check circuit breaker availability
        circuit_available = self._circuit.is_available()
        circuit_state = self._circuit.get_state().value
        if not circuit_available:
            request_logger.warning(
                "resilient_http.decision",
                service=self._service_name,
                endpoint=endpoint,
                circuit_state=circuit_state,
                decision="request_blocked",
                reason="circuit_breaker_open",
            )
            raise ServiceUnavailableError(f"{self._service_name} circuit is open")

        # Check health before attempting request
        health_status = await self.check_health()
        if not health_status:
            request_logger.warning(
                "resilient_http.decision",
                service=self._service_name,
                endpoint=endpoint,
                circuit_state=circuit_state,
                decision="request_blocked",
                reason="service_not_healthy",
            )
            raise ServiceUnavailableError(f"{self._service_name} is not healthy")

        request_logger.debug(
            "resilient_http.decision",
            service=self._service_name,
            endpoint=endpoint,
            circuit_state=circuit_state,
            health_status=health_status,
            decision="proceeding_with_request",
        )

        # Auto-inject correlation ID from context
        request_headers = inject_correlation_id(headers)

        client = await self._get_client()
        url = f"{self._base_url}{endpoint}"

        # Use the circuit breaker to protect the request
        return await self._circuit.call(
            post_with_retries,
            client,
            url,
            files=files,
            data=data,
            json=json,
            content=content,
            headers=request_headers,
            params=params,
            max_retries=max_retries,
            log_fields=log_fields,
            logger=logger,
            timeout=timeout,
        )

    async def get(
        self,
        endpoint: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> httpx.Response:
        """GET request with circuit breaker protection."""
        if not self._circuit.is_available():
            raise ServiceUnavailableError(f"{self._service_name} circuit is open")

        # Auto-inject correlation ID from context
        request_headers = inject_correlation_id(headers)

        client = await self._get_client()
        url = f"{self._base_url}{endpoint}"

        return await self._circuit.call(
            client.get,
            url,
            headers=request_headers,
            params=params,
            timeout=timeout,
        )

    async def put(
        self,
        endpoint: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        content: bytes | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> httpx.Response:
        """PUT request with circuit breaker protection."""
        if not self._circuit.is_available():
            raise ServiceUnavailableError(f"{self._service_name} circuit is open")

        # Auto-inject correlation ID from context
        request_headers = inject_correlation_id(headers)

        client = await self._get_client()
        url = f"{self._base_url}{endpoint}"

        return await self._circuit.call(
            client.put,
            url,
            headers=request_headers,
            params=params,
            json=json,
            content=content,
            timeout=timeout,
        )

    async def delete(
        self,
        endpoint: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> httpx.Response:
        """DELETE request with circuit breaker protection."""
        if not self._circuit.is_available():
            raise ServiceUnavailableError(f"{self._service_name} circuit is open")

        # Auto-inject correlation ID from context
        request_headers = inject_correlation_id(headers)

        client = await self._get_client()
        url = f"{self._base_url}{endpoint}"

        return await self._circuit.call(
            client.delete,
            url,
            headers=request_headers,
            params=params,
            timeout=timeout,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_circuit_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        return self._circuit.get_stats()

    async def __aenter__(self) -> ResilientHTTPClient:
        """Async context manager entry."""
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
    ) -> None:
        """Async context manager exit."""
        await self.close()


__all__ = ["ResilientHTTPClient", "ServiceUnavailableError"]
