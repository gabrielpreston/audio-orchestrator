"""Validation framework for configuration system."""

from __future__ import annotations

import re
from typing import Any
from collections.abc import Callable

from services.common.logging import get_logger

logger = get_logger(__name__)


def validate_url(url: str) -> bool:
    """Validate URL format.

    Args:
        url: URL to validate

    Returns:
        True if valid URL, False otherwise
    """
    if not url:
        return False

    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain
        r"localhost|"  # localhost
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # IP
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    return bool(url_pattern.match(url))


def validate_port(port: int) -> bool:
    """Validate port number.

    Args:
        port: Port number to validate

    Returns:
        True if valid port, False otherwise
    """
    return 1 <= port <= 65535


def validate_sample_rate(rate: int) -> bool:
    """Validate audio sample rate.

    Args:
        rate: Sample rate to validate

    Returns:
        True if valid sample rate, False otherwise
    """
    valid_rates = [8000, 16000, 22050, 44100, 48000]
    return rate in valid_rates


def validate_audio_channels(channels: Any) -> bool:
    """Validate audio channel count.

    Args:
        channels: Number of channels to validate

    Returns:
        True if valid channel count, False otherwise
    """
    if not isinstance(channels, int):
        return False
    return channels in [1, 2]


def validate_timeout(timeout: float) -> bool:
    """Validate timeout value.

    Args:
        timeout: Timeout value to validate

    Returns:
        True if valid timeout, False otherwise
    """
    return 0.1 <= timeout <= 300.0


def validate_positive_int(value: int) -> bool:
    """Validate positive integer.

    Args:
        value: Integer to validate

    Returns:
        True if positive, False otherwise
    """
    return value > 0


def validate_positive_float(value: float) -> bool:
    """Validate positive float.

    Args:
        value: Float to validate

    Returns:
        True if positive, False otherwise
    """
    return value > 0.0


def validate_range(value: float, min_val: float, max_val: float) -> bool:
    """Validate value is within range.

    Args:
        value: Value to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        True if within range, False otherwise
    """
    return min_val <= value <= max_val


def validate_choice(value: Any, choices: list[Any]) -> bool:
    """Validate value is in choices list.

    Args:
        value: Value to validate
        choices: List of valid choices

    Returns:
        True if value is in choices, False otherwise
    """
    return value in choices


def validate_pattern(value: str, pattern: str) -> bool:
    """Validate string matches pattern.

    Args:
        value: String to validate
        pattern: Regex pattern to match

    Returns:
        True if matches pattern, False otherwise
    """
    return bool(re.match(pattern, value))


def create_validator(
    validator_func: Callable[[Any], bool], _error_msg: str
) -> Callable[[Any], bool]:
    """Create a validator function with custom error message.

    Args:
        validator_func: Validation function
        error_msg: Error message for validation failure

    Returns:
        Validator function
    """

    def validator(value: Any) -> bool:
        try:
            return validator_func(value)
        except Exception as exc:
            logger.warning(
                "config.validator_error",
                validator=validator_func.__name__,
                value=value,
                error=str(exc),
            )
            return False

    return validator


# Common validators
validate_http_url = create_validator(validate_url, "Invalid HTTP URL")
validate_audio_sample_rate = create_validator(
    validate_sample_rate, "Invalid audio sample rate"
)
validate_audio_channels_validator = create_validator(
    validate_audio_channels, "Invalid audio channel count"
)
validate_timeout_value = create_validator(validate_timeout, "Invalid timeout value")
validate_positive_integer = create_validator(
    validate_positive_int, "Must be positive integer"
)
validate_positive_float_value = create_validator(
    validate_positive_float, "Must be positive float"
)
