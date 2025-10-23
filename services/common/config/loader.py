"""Environment variable loading utilities for configuration system."""

from __future__ import annotations

import os
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def load_environment_variables(prefix: str = "") -> dict[str, Any]:
    """Load environment variables with optional prefix.

    Args:
        prefix: Optional prefix to filter environment variables

    Returns:
        Dictionary of environment variables
    """
    env_vars = {}
    for key, value in os.environ.items():
        if not prefix or key.startswith(prefix):
            env_vars[key] = value
    return env_vars


def get_environment_type() -> str:
    """Get current environment type from environment variables.

    Returns:
        Environment type (development, testing, production, docker)
    """
    return os.getenv("ENVIRONMENT", "docker").lower()


def load_config_from_env(config_class: type[Any], **overrides: Any) -> Any:
    """Load configuration from environment variables.

    Args:
        config_class: Configuration class to instantiate
        **overrides: Override values for configuration

    Returns:
        Configured instance
    """
    try:
        return config_class(**overrides)
    except Exception as exc:
        logger.error(
            "config.load_failed", config_class=config_class.__name__, error=str(exc)
        )
        raise


def validate_required_env_vars(required_vars: list[str]) -> None:
    """Validate that required environment variables are set.

    Args:
        required_vars: List of required environment variable names

    Raises:
        ValueError: If any required variables are missing
    """
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        raise ValueError(f"Missing required environment variables: {missing_vars}")


def get_env_with_default(key: str, default: Any, env_type: type = str) -> Any:
    """Get environment variable with default value and type conversion.

    Args:
        key: Environment variable name
        default: Default value if not set
        env_type: Type to convert value to

    Returns:
        Environment variable value or default
    """
    value = os.getenv(key)
    if value is None:
        return default

    try:
        if env_type == bool:
            return value.lower() in ("true", "1", "yes", "on")
        elif env_type == int:
            return int(value)
        elif env_type == float:
            return float(value)
        elif env_type == list:
            return [item.strip() for item in value.split(",")]
        else:
            return value
    except (ValueError, TypeError) as exc:
        logger.warning(
            "config.env_conversion_failed",
            key=key,
            value=value,
            target_type=env_type.__name__,
            error=str(exc),
        )
        return default
