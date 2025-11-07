"""Environment variable loading utilities for configuration system."""

from __future__ import annotations

import os
from typing import Any, TypeVar

from services.common.structured_logging import get_logger


T = TypeVar("T")

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


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, preserving nested structures.

    Args:
        base: Base dictionary (will be modified in-place)
        override: Override dictionary (values take precedence)

    Returns:
        Merged dictionary (same reference as base)
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            _deep_merge_dict(base[key], value)
        else:
            # Override or add new key
            base[key] = value
    return base


def load_config_from_env(config_class: type[T], **overrides: Any) -> T:
    """Load configuration from environment variables.

    Args:
        config_class: Configuration class to instantiate
        **overrides: Override values for configuration

    Returns:
        Configured instance
    """
    try:
        # Use NestedConfig for complex nested structures
        if config_class.__name__ == "ServiceConfig":
            from .base import NestedConfig

            # Apply environment variable overrides with deep merge
            env_overrides = _get_env_overrides()
            _deep_merge_dict(overrides, env_overrides)

            return NestedConfig(**overrides)  # type: ignore[return-value]
        return config_class(**overrides)
    except Exception as exc:
        logger.error(
            "config.load_failed", config_class=config_class.__name__, error=str(exc)
        )
        raise


def _get_env_overrides() -> dict[str, Any]:
    """Get environment variable overrides for configuration."""
    overrides: dict[str, Any] = {}

    # Wake detection configuration
    wake_enabled = os.getenv("WAKE_DETECTION_ENABLED")
    if wake_enabled is not None:
        # Handle explicit true/false values
        if wake_enabled.lower() in ("true", "1", "yes", "on"):
            overrides.setdefault("wake", {})["enabled"] = True
        elif wake_enabled.lower() in ("false", "0", "no", "off"):
            overrides.setdefault("wake", {})["enabled"] = False
        else:
            # Empty string or invalid values are treated as false
            overrides.setdefault("wake", {})["enabled"] = False

    # Wake phrases (comma-separated list)
    wake_phrases = os.getenv("WAKE_PHRASES")
    if wake_phrases is not None:
        overrides.setdefault("wake", {})["wake_phrases"] = [
            phrase.strip() for phrase in wake_phrases.split(",") if phrase.strip()
        ]

    # Wake threshold (float validation)
    wake_threshold = os.getenv("WAKE_THRESHOLD")
    if wake_threshold is not None:
        try:
            threshold = float(wake_threshold)
            if 0.0 <= threshold <= 1.0:
                overrides.setdefault("wake", {})["activation_threshold"] = threshold
            else:
                logger.warning(
                    "config.wake_threshold_invalid",
                    value=wake_threshold,
                    message="Must be between 0.0 and 1.0",
                )
        except ValueError:
            logger.warning(
                "config.wake_threshold_invalid",
                value=wake_threshold,
            )

    # Wake sample rate (int validation)
    wake_sample_rate = os.getenv("WAKE_SAMPLE_RATE")
    if wake_sample_rate is not None:
        try:
            overrides.setdefault("wake", {})["target_sample_rate_hz"] = int(
                wake_sample_rate
            )
        except ValueError:
            logger.warning(
                "config.wake_sample_rate_invalid",
                value=wake_sample_rate,
            )

    # Wake model paths (comma-separated list, empty string means empty list)
    wake_model_paths = os.getenv("WAKE_MODEL_PATHS")
    if wake_model_paths is not None:
        overrides.setdefault("wake", {})["model_paths"] = [
            path.strip() for path in wake_model_paths.split(",") if path.strip()
        ]

    # Wake inference framework (onnx or tflite)
    wake_inference_framework = os.getenv("WAKE_INFERENCE_FRAMEWORK")
    if wake_inference_framework is not None:
        framework = wake_inference_framework.lower().strip()
        if framework in ("onnx", "tflite"):
            overrides.setdefault("wake", {})["inference_framework"] = framework
        else:
            logger.warning(
                "config.wake_inference_framework_invalid",
                value=wake_inference_framework,
                message="Must be 'onnx' or 'tflite', defaulting to 'onnx'",
            )
            overrides.setdefault("wake", {})["inference_framework"] = "onnx"

    # Discord configuration
    discord_token = os.getenv("DISCORD_BOT_TOKEN")
    if discord_token is not None:
        overrides.setdefault("discord", {})["token"] = discord_token

    discord_guild_id = os.getenv("DISCORD_GUILD_ID")
    if discord_guild_id is not None:
        try:
            overrides.setdefault("discord", {})["guild_id"] = int(discord_guild_id)
        except ValueError:
            logger.warning(
                "config.discord_guild_id_invalid",
                value=discord_guild_id,
                message="DISCORD_GUILD_ID must be a valid integer",
            )

    discord_channel_id = os.getenv("DISCORD_VOICE_CHANNEL_ID")
    if discord_channel_id is not None:
        try:
            overrides.setdefault("discord", {})["voice_channel_id"] = int(
                discord_channel_id
            )
        except ValueError:
            logger.warning(
                "config.discord_channel_id_invalid",
                value=discord_channel_id,
                message="DISCORD_VOICE_CHANNEL_ID must be a valid integer",
            )

    discord_auto_join = os.getenv("DISCORD_AUTO_JOIN")
    if discord_auto_join is not None:
        overrides.setdefault("discord", {})["auto_join"] = (
            discord_auto_join.lower()
            in (
                "true",
                "1",
                "yes",
                "on",
            )
        )

    discord_intents = os.getenv("DISCORD_INTENTS")
    if discord_intents is not None:
        overrides.setdefault("discord", {})["intents"] = [
            intent.strip() for intent in discord_intents.split(",")
        ]

    # Voice connection configuration
    discord_connect_timeout = os.getenv("DISCORD_VOICE_CONNECT_TIMEOUT")
    if discord_connect_timeout is not None:
        try:
            overrides.setdefault("discord", {})["voice_connect_timeout_seconds"] = (
                float(discord_connect_timeout)
            )
        except ValueError:
            logger.warning(
                "config.discord_connect_timeout_invalid",
                value=discord_connect_timeout,
            )

    discord_connect_attempts = os.getenv("DISCORD_VOICE_CONNECT_ATTEMPTS")
    if discord_connect_attempts is not None:
        try:
            overrides.setdefault("discord", {})["voice_connect_max_attempts"] = int(
                discord_connect_attempts
            )
        except ValueError:
            logger.warning(
                "config.discord_connect_attempts_invalid",
                value=discord_connect_attempts,
            )

    discord_reconnect_base = os.getenv("DISCORD_VOICE_RECONNECT_BASE_DELAY")
    if discord_reconnect_base is not None:
        try:
            overrides.setdefault("discord", {})[
                "voice_reconnect_initial_backoff_seconds"
            ] = float(discord_reconnect_base)
        except ValueError:
            logger.warning(
                "config.discord_reconnect_base_invalid",
                value=discord_reconnect_base,
            )

    discord_reconnect_max = os.getenv("DISCORD_VOICE_RECONNECT_MAX_DELAY")
    if discord_reconnect_max is not None:
        try:
            overrides.setdefault("discord", {})[
                "voice_reconnect_max_backoff_seconds"
            ] = float(discord_reconnect_max)
        except ValueError:
            logger.warning(
                "config.discord_reconnect_max_invalid",
                value=discord_reconnect_max,
            )

    # Gateway session validation configuration
    discord_gateway_validation_timeout = os.getenv(
        "DISCORD_VOICE_GATEWAY_VALIDATION_TIMEOUT"
    )
    if discord_gateway_validation_timeout is not None:
        try:
            overrides.setdefault("discord", {})[
                "voice_gateway_validation_timeout_seconds"
            ] = float(discord_gateway_validation_timeout)
        except ValueError:
            logger.warning(
                "config.discord_gateway_validation_timeout_invalid",
                value=discord_gateway_validation_timeout,
            )

    discord_gateway_min_delay = os.getenv("DISCORD_VOICE_GATEWAY_MIN_DELAY")
    if discord_gateway_min_delay is not None:
        try:
            overrides.setdefault("discord", {})["voice_gateway_min_delay_seconds"] = (
                float(discord_gateway_min_delay)
            )
        except ValueError:
            logger.warning(
                "config.discord_gateway_min_delay_invalid",
                value=discord_gateway_min_delay,
            )

    # Discord warm-up configuration
    discord_warmup_audio = os.getenv("DISCORD_WARMUP_AUDIO")
    if discord_warmup_audio is not None:
        overrides.setdefault("telemetry", {})["discord_warmup_audio"] = (
            discord_warmup_audio.lower() in ("true", "1", "yes", "on")
        )

    return overrides


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
        if env_type is bool:
            return value.lower() in ("true", "1", "yes", "on")
        elif env_type is int:
            return int(value)
        elif env_type is float:
            return float(value)
        elif env_type is list:
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
