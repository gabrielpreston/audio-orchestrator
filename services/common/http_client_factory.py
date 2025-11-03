"""Factory for creating ResilientHTTPClient instances with environment-based configuration."""

from __future__ import annotations

from typing import Any

from .circuit_breaker import CircuitBreakerConfig
from .config.loader import get_env_with_default
from .resilient_http import ResilientHTTPClient


def create_resilient_client(
    service_name: str,
    base_url: str | None = None,
    env_prefix: str | None = None,
    **kwargs: Any,
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
        **kwargs: Additional keyword arguments to override any ResilientHTTPClient
                 parameter. These take precedence over environment variables.
                 Valid parameters: timeout, health_check_interval,
                 health_check_startup_grace_seconds, health_check_timeout,
                 max_connections, max_keepalive_connections, circuit_config.

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

        # Overriding parameters via kwargs
        client = create_resilient_client(
            "orchestrator",
            health_check_startup_grace_seconds=0.0,
            timeout=15.0,
        )
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

    # Build configuration dict from environment variables
    config: dict[str, Any] = {
        "service_name": service_name,
        "base_url": resolved_base_url,
        "circuit_config": circuit_config,
        "timeout": get_env_with_default(
            f"{prefix}_TIMEOUT_SECONDS",
            30.0,
            float,
        ),
        "health_check_interval": get_env_with_default(
            f"{prefix}_HEALTH_CHECK_INTERVAL",
            10.0,
            float,
        ),
        "health_check_startup_grace_seconds": get_env_with_default(
            f"{prefix}_HEALTH_CHECK_STARTUP_GRACE_SECONDS",
            30.0,
            float,
        ),
        "health_check_timeout": get_env_with_default(
            f"{prefix}_HEALTH_CHECK_TIMEOUT_SECONDS",
            10.0,
            float,
        ),
        "max_connections": get_env_with_default(
            f"{prefix}_MAX_CONNECTIONS",
            10,
            int,
        ),
        "max_keepalive_connections": get_env_with_default(
            f"{prefix}_MAX_KEEPALIVE_CONNECTIONS",
            5,
            int,
        ),
    }

    # Apply kwargs overrides (kwargs take precedence over env vars)
    config.update(kwargs)

    # Create client with all configuration
    return ResilientHTTPClient(**config)


def create_dependency_health_client(
    service_name: str,
    base_url: str | None = None,
    env_prefix: str | None = None,
    **kwargs: Any,
) -> ResilientHTTPClient:
    """Create a ResilientHTTPClient for dependency health checks.

    This is a convenience wrapper around `create_resilient_client()` that sets
    `health_check_startup_grace_seconds=0.0` by default. This is appropriate
    for dependency health checks where you want accurate readiness detection
    without a startup grace period.

    Args:
        service_name: Name of the service (used for circuit breaker naming and defaults)
        base_url: Base URL for the service. If not provided, will try to load from
                 environment variable `{PREFIX}_BASE_URL`, or default to
                 `http://{service_name.lower()}`
        env_prefix: Prefix for environment variables (e.g., "LLM").
                   If not provided, defaults to `service_name.upper()`.
        **kwargs: Additional keyword arguments to override any ResilientHTTPClient
                 parameter. These take precedence over defaults and environment variables.

    Returns:
        Configured ResilientHTTPClient instance with grace period disabled by default

    Example:
        ```python
        # Create health check client for LLM dependency
        llm_health_client = create_dependency_health_client(
            service_name="llm",
            base_url="http://llm:8100",
            env_prefix="LLM",
        )
        # grace_period is 0.0 by default, but can be overridden:
        custom_client = create_dependency_health_client(
            service_name="llm",
            health_check_startup_grace_seconds=5.0,  # Override default
        )
        ```
    """
    # Set default grace period to 0.0 for accurate dependency health checking
    defaults = {
        "health_check_startup_grace_seconds": 0.0,
    }
    # kwargs override defaults
    defaults.update(kwargs)

    return create_resilient_client(
        service_name=service_name,
        base_url=base_url,
        env_prefix=env_prefix,
        **defaults,
    )


__all__ = ["create_resilient_client", "create_dependency_health_client"]
