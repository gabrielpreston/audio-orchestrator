"""Resilient HTTP client with circuit breaker and health checks."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .http import post_with_retries
from .logging import get_logger


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
    ):
        self._service_name = service_name
        self._base_url = base_url.rstrip("/")
        self._circuit = CircuitBreaker(
            service_name, circuit_config or CircuitBreakerConfig()
        )
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout
        self._logger = get_logger(__name__)
        self._last_health_check: float = 0
        self._health_check_interval = health_check_interval
        self._is_healthy: bool = False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def check_health(self) -> bool:
        """Check if service is healthy via /health/ready."""
        now = time.time()

        # Skip health check if we checked recently
        if now - self._last_health_check < self._health_check_interval:
            return self._is_healthy

        try:
            client = await self._get_client()
            response = await client.get(f"{self._base_url}/health/ready", timeout=5.0)

            self._is_healthy = response.status_code == 200
            self._last_health_check = now

            if not self._is_healthy:
                self._logger.debug(
                    "resilient_http.health_check_failed",
                    service=self._service_name,
                    status_code=response.status_code,
                )

            return self._is_healthy

        except Exception as exc:
            self._is_healthy = False
            self._last_health_check = now
            self._logger.debug(
                "resilient_http.health_check_error",
                service=self._service_name,
                error=str(exc),
            )
            return False

    async def post_with_retry(
        self,
        endpoint: str,
        *,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        data: dict[str, Any] | None = None,
        json: Any | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        max_retries: int = 3,
        log_fields: dict[str, Any] | None = None,
        logger: Any | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> httpx.Response:
        """POST with circuit breaker protection."""
        if not self._circuit.is_available():
            raise ServiceUnavailableError(f"{self._service_name} circuit is open")

        # Check health before attempting request
        if not await self.check_health():
            raise ServiceUnavailableError(f"{self._service_name} is not healthy")

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
            headers=headers,
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

        client = await self._get_client()
        url = f"{self._base_url}{endpoint}"

        return await self._circuit.call(
            client.get,
            url,
            headers=headers,
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
