"""Factory for creating ResilientHTTPClient instances with environment-based configuration."""

from __future__ import annotations

from .circuit_breaker import CircuitBreakerConfig
from .config.loader import get_env_with_default
from .resilient_http import ResilientHTTPClient


def create_resilient_client(
    service_name: str,
    base_url: str | None = None,
    env_prefix: str | None = None,
) -> ResilientHTTPClient:
    """Create a ResilientHTTPClient with environment-based configuration.

    This factory function loads configuration from environment variables using
    a prefix pattern. All configuration values have sensible defaults, so
    services can use this factory without requiring environment variables.

    Args:
        service_name: Name of the service (used for circuit breaker naming and defaults)
        base_url: Base URL for the service. If not provided, will try to load from
                 environment variable `{PREFIX}_BASE_URL`, or default to
                 `http://{service_name.lower()}`
        env_prefix: Prefix for environment variables (e.g., "ORCHESTRATOR").
                   If not provided, defaults to `service_name.upper()`.

    Returns:
        Configured ResilientHTTPClient instance

    Example:
        ```python
        # Using default prefix (service name uppercased)
        client = create_resilient_client("orchestrator")
        # Loads from: ORCHESTRATOR_BASE_URL, ORCHESTRATOR_CIRCUIT_FAILURE_THRESHOLD, etc.

        # Using custom prefix
        client = create_resilient_client("orchestrator", env_prefix="MY_SERVICE")
        # Loads from: MY_SERVICE_BASE_URL, MY_SERVICE_CIRCUIT_FAILURE_THRESHOLD, etc.

        # Providing base_url directly
        client = create_resilient_client("orchestrator", base_url="http://custom:8000")
        ```
    """
    prefix = (env_prefix or service_name).upper()

    # Load base URL
    resolved_base_url = base_url or get_env_with_default(
        f"{prefix}_BASE_URL",
        f"http://{service_name.lower()}",
        str,
    )

    # Create circuit breaker config from environment variables
    circuit_config = CircuitBreakerConfig(
        failure_threshold=get_env_with_default(
            f"{prefix}_CIRCUIT_FAILURE_THRESHOLD",
            5,
            int,
        ),
        success_threshold=get_env_with_default(
            f"{prefix}_CIRCUIT_SUCCESS_THRESHOLD",
            2,
            int,
        ),
        timeout_seconds=get_env_with_default(
            f"{prefix}_CIRCUIT_TIMEOUT_SECONDS",
            30.0,
            float,
        ),
    )

    # Create client with all configuration from environment
    return ResilientHTTPClient(
        service_name=service_name,
        base_url=resolved_base_url,
        circuit_config=circuit_config,
        timeout=get_env_with_default(
            f"{prefix}_TIMEOUT_SECONDS",
            30.0,
            float,
        ),
        health_check_interval=get_env_with_default(
            f"{prefix}_HEALTH_CHECK_INTERVAL",
            10.0,
            float,
        ),
        health_check_startup_grace_seconds=get_env_with_default(
            f"{prefix}_HEALTH_CHECK_STARTUP_GRACE_SECONDS",
            30.0,
            float,
        ),
        health_check_timeout=get_env_with_default(
            f"{prefix}_HEALTH_CHECK_TIMEOUT_SECONDS",
            10.0,
            float,
        ),
        max_connections=get_env_with_default(
            f"{prefix}_MAX_CONNECTIONS",
            10,
            int,
        ),
        max_keepalive_connections=get_env_with_default(
            f"{prefix}_MAX_KEEPALIVE_CONNECTIONS",
            5,
            int,
        ),
    )


__all__ = ["create_resilient_client"]
