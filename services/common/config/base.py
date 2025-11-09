"""Core configuration primitives for audio-orchestrator services.

This module provides the foundational configuration classes and utilities
for the new hybrid configuration system.
"""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar
from collections.abc import Callable

from services.common.structured_logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class Environment(Enum):
    """Supported environment types."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"
    DOCKER = "docker"


class ConfigError(Exception):
    """Base exception for configuration-related errors."""

    pass


class ValidationError(ConfigError):
    """Exception raised when configuration validation fails."""

    def __init__(self, field_name: str, value: Any, message: str) -> None:
        self.field = field_name
        self.value = value
        self.message = message
        super().__init__(f"Validation failed for field '{field_name}': {message}")


class RequiredFieldError(ConfigError):
    """Exception raised when a required field is missing."""

    def __init__(self, field_name: str) -> None:
        self.field = field_name
        super().__init__(f"Required field '{field_name}' is missing")


@dataclass
class FieldDefinition:
    """Definition for a configuration field with validation rules."""

    name: str
    field_type: type[Any]
    default: Any = None
    required: bool = False
    description: str = ""
    validator: Callable[[Any], bool] | None = None
    env_var: str | None = None
    choices: list[Any] | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    pattern: str | None = None

    def __post_init__(self) -> None:
        """Validate field definition after initialization."""
        if self.required and self.default is not None:
            raise ValueError(
                f"Field '{self.name}' cannot be both required and have a default value"
            )
        if self.choices and self.default not in self.choices:
            raise ValueError(f"Field '{self.name}' default value not in choices")


class BaseConfig(ABC):
    """Base configuration class with validation and environment loading."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize configuration with provided values."""
        self._values: dict[str, Any] = {}
        self._load_from_kwargs(kwargs)
        self._load_from_environment()
        self._validate()

    def _load_from_kwargs(self, kwargs: dict[str, Any]) -> None:
        """Load values from constructor kwargs."""
        for field_def in self.get_field_definitions():
            if field_def.name in kwargs:
                self._values[field_def.name] = kwargs[field_def.name]

    def _load_from_environment(self) -> None:
        """Load values from environment variables.

        Environment variables override preset/default values to allow runtime
        configuration without code changes.
        """
        for field_def in self.get_field_definitions():
            if field_def.env_var:
                env_value = os.getenv(field_def.env_var)
                if env_value is not None:
                    self._values[field_def.name] = self._convert_env_value(
                        env_value, field_def.field_type
                    )

    def _convert_env_value(self, value: str, field_type: type[Any]) -> Any:
        """Convert environment variable string to appropriate type."""
        if field_type is bool:
            return value.lower() in ("true", "1", "yes", "on")
        elif field_type is int:
            return int(value)
        elif field_type is float:
            return float(value)
        elif field_type is list:
            return [item.strip() for item in value.split(",")]
        else:
            # For string fields, normalize case for fields with choices
            # This ensures case-insensitive validation for enum-like choices
            return value

    def _validate(self) -> None:
        """Validate all configuration values."""
        for field_def in self.get_field_definitions():
            value = self._values.get(field_def.name, field_def.default)

            # Check required fields
            if field_def.required and value is None:
                raise RequiredFieldError(field_def.name)

            # Apply field validation
            if value is not None:
                self._validate_field(field_def, value)
                # Use value from _values dict in case _validate_field normalized it
                if field_def.name in self._values:
                    value = self._values[field_def.name]
                self._values[field_def.name] = value

    def _validate_field(self, field_def: FieldDefinition, value: Any) -> None:
        """Validate a single field value."""
        # Type validation
        if not isinstance(value, field_def.field_type):
            raise ValidationError(
                field_def.name, value, f"Expected {field_def.field_type.__name__}"
            )

        # Choices validation with case-insensitive normalization for strings
        if field_def.choices:
            normalized_value = value
            # Normalize string values case-insensitively when choices exist
            if isinstance(value, str):
                # Try case-insensitive matching
                value_upper = value.upper()
                matching_choice = None
                for choice in field_def.choices:
                    if isinstance(choice, str) and choice.upper() == value_upper:
                        matching_choice = choice
                        break
                if matching_choice is not None:
                    normalized_value = matching_choice
                    # Update the value in _values dict to use canonical case
                    if field_def.name in self._values:
                        self._values[field_def.name] = normalized_value

            if normalized_value not in field_def.choices:
                raise ValidationError(
                    field_def.name, value, f"Must be one of {field_def.choices}"
                )

        # Range validation
        if field_def.min_value is not None and value < field_def.min_value:
            raise ValidationError(
                field_def.name, value, f"Must be >= {field_def.min_value}"
            )
        if field_def.max_value is not None and value > field_def.max_value:
            raise ValidationError(
                field_def.name, value, f"Must be <= {field_def.max_value}"
            )

        # Pattern validation
        if (
            field_def.pattern
            and isinstance(value, str)
            and not re.match(field_def.pattern, value)
        ):
            raise ValidationError(
                field_def.name, value, f"Must match pattern {field_def.pattern}"
            )

        # Custom validator
        if field_def.validator and not field_def.validator(value):
            raise ValidationError(field_def.name, value, "Custom validation failed")

    @classmethod
    @abstractmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        """Get field definitions for this configuration class."""
        pass

    def __getattr__(self, name: str) -> Any:
        """Get configuration value by name."""
        if name in self._values:
            return self._values[name]
        raise AttributeError(f"Configuration field '{name}' not found")

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return self._values.copy()


# Core configuration classes (5 classes)
class LoggingConfig(BaseConfig):
    """Logging configuration."""

    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return [
            FieldDefinition(
                name="level",
                field_type=str,
                default="INFO",
                description="Log level",
                env_var="LOG_LEVEL",
                choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            ),
            FieldDefinition(
                name="json_logs",
                field_type=bool,
                default=True,
                description="Use JSON logging format",
                env_var="LOG_JSON",
            ),
            FieldDefinition(
                name="service_name",
                field_type=str,
                default="audio-orchestrator",
                description="Service name for logging",
                env_var="SERVICE_NAME",
            ),
        ]


class HttpConfig(BaseConfig):
    """HTTP configuration."""

    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return [
            FieldDefinition(
                name="timeout",
                field_type=float,
                default=30.0,
                description="HTTP request timeout in seconds",
                env_var="HTTP_TIMEOUT",
                min_value=1.0,
                max_value=300.0,
            ),
            FieldDefinition(
                name="max_retries",
                field_type=int,
                default=3,
                description="Maximum HTTP retry attempts",
                env_var="HTTP_MAX_RETRIES",
                min_value=0,
                max_value=10,
            ),
            FieldDefinition(
                name="retry_delay",
                field_type=float,
                default=1.0,
                description="Retry delay in seconds",
                env_var="HTTP_RETRY_DELAY",
                min_value=0.1,
                max_value=10.0,
            ),
        ]


class AudioConfig(BaseConfig):
    """Unified audio configuration (consolidated from AudioConfig, ProcessingConfig, FasterWhisperConfig)."""

    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return [
            FieldDefinition(
                name="sample_rate",
                field_type=int,
                default=16000,
                description="Audio sample rate in Hz",
                env_var="AUDIO_SAMPLE_RATE",
                choices=[8000, 16000, 22050, 44100, 48000],
            ),
            FieldDefinition(
                name="channels",
                field_type=int,
                default=1,
                description="Number of audio channels",
                env_var="AUDIO_CHANNELS",
                choices=[1, 2],
            ),
            FieldDefinition(
                name="enable_enhancement",
                field_type=bool,
                default=True,
                description="Enable audio enhancement",
                env_var="AUDIO_ENABLE_ENHANCEMENT",
            ),
            FieldDefinition(
                name="enable_vad",
                field_type=bool,
                default=True,
                description="Enable voice activity detection",
                env_var="AUDIO_ENABLE_VAD",
            ),
            FieldDefinition(
                name="service_timeout",
                field_type=int,
                default=20,
                description="Audio processor service timeout in milliseconds (deprecated - kept for compatibility)",
                env_var="AUDIO_SERVICE_TIMEOUT",
                min_value=1,
                max_value=1000,
            ),
            FieldDefinition(
                name="silence_timeout_seconds",
                field_type=float,
                default=0.75,
                description="Seconds of silence before finalizing an audio segment",
                env_var="AUDIO_SILENCE_TIMEOUT",
                min_value=0.1,
                max_value=10.0,
            ),
            FieldDefinition(
                name="max_segment_duration_seconds",
                field_type=float,
                default=15.0,
                description="Maximum length of a single audio segment in seconds",
                env_var="AUDIO_MAX_SEGMENT_DURATION",
                min_value=0.5,
                max_value=60.0,
            ),
            FieldDefinition(
                name="min_segment_duration_seconds",
                field_type=float,
                default=0.3,
                description="Minimum length before a segment is considered valid speech",
                env_var="AUDIO_MIN_SEGMENT_DURATION",
                min_value=0.1,
                max_value=5.0,
            ),
            FieldDefinition(
                name="aggregation_window_seconds",
                field_type=float,
                default=1.5,
                description="Sliding window size for VAD aggregation",
                env_var="AUDIO_AGGREGATION_WINDOW",
                min_value=0.5,
                max_value=10.0,
            ),
            FieldDefinition(
                name="input_sample_rate_hz",
                field_type=int,
                default=48000,
                description="Input audio sample rate in Hz (Discord-specific, for accumulator logic)",
                env_var="AUDIO_INPUT_SAMPLE_RATE",
                choices=[8000, 16000, 22050, 44100, 48000],
            ),
            FieldDefinition(
                name="vad_sample_rate_hz",
                field_type=int,
                default=16000,
                description="Sample rate used for VAD analysis in Hz",
                env_var="AUDIO_VAD_SAMPLE_RATE",
                choices=[8000, 16000],
            ),
            FieldDefinition(
                name="vad_frame_duration_ms",
                field_type=int,
                default=30,
                description="Frame duration in milliseconds for VAD processing",
                env_var="AUDIO_VAD_FRAME_MS",
                choices=[10, 20, 30],
            ),
            FieldDefinition(
                name="vad_aggressiveness",
                field_type=int,
                default=1,
                description="WebRTC VAD aggressiveness level (0=quality, 1=low bitrate, 2=aggressive, 3=very aggressive)",
                env_var="AUDIO_VAD_AGGRESSIVENESS",
                choices=[0, 1, 2, 3],
            ),
            FieldDefinition(
                name="min_audio_rms_threshold",
                field_type=float,
                default=10.0,
                description="Minimum RMS value in int16 domain (0-32767) for frame processing (filters silent frames). Typical values: 10-100 for quiet audio, 100-1000 for normal speech.",
                env_var="AUDIO_MIN_RMS_THRESHOLD",
                min_value=0.0,
                max_value=1000.0,
            ),
            FieldDefinition(
                name="min_segment_rms_threshold",
                field_type=float,
                default=5.0,
                description="Minimum RMS value in int16 domain (0-32767) for segment creation (filters silent segments). Typical values: 5-50 for quiet audio, 50-500 for normal speech.",
                env_var="AUDIO_MIN_SEGMENT_RMS_THRESHOLD",
                min_value=0.0,
                max_value=1000.0,
            ),
            FieldDefinition(
                name="quality_min_snr_db",
                field_type=float,
                default=10.0,
                description="Minimum SNR in dB for audio quality validation",
                env_var="AUDIO_QUALITY_MIN_SNR_DB",
                min_value=0.0,
                max_value=100.0,
            ),
            FieldDefinition(
                name="quality_min_rms",
                field_type=float,
                default=100.0,
                description="Minimum RMS value in int16 domain (0-32767) for audio quality validation. Typical values: 100-500 for acceptable quality, 500-2000 for good quality.",
                env_var="AUDIO_QUALITY_MIN_RMS",
                min_value=0.0,
                max_value=10000.0,
            ),
            FieldDefinition(
                name="quality_min_clarity",
                field_type=float,
                default=0.3,
                description="Minimum clarity score (0-1) for audio quality validation",
                env_var="AUDIO_QUALITY_MIN_CLARITY",
                min_value=0.0,
                max_value=1.0,
            ),
            FieldDefinition(
                name="quality_wake_min_snr_db",
                field_type=float,
                default=10.0,
                description="Minimum SNR in dB for wake detection quality validation",
                env_var="AUDIO_QUALITY_WAKE_MIN_SNR_DB",
                min_value=0.0,
                max_value=100.0,
            ),
            FieldDefinition(
                name="quality_wake_min_rms",
                field_type=float,
                default=100.0,
                description="Minimum RMS value for wake detection quality validation",
                env_var="AUDIO_QUALITY_WAKE_MIN_RMS",
                min_value=0.0,
                max_value=10000.0,
            ),
        ]


class ServiceConfig(BaseConfig):
    """Service configuration (consolidated from PortConfig)."""

    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return [
            FieldDefinition(
                name="port",
                field_type=int,
                default=8000,
                description="Service port",
                env_var="SERVICE_PORT",
                min_value=1024,
                max_value=65535,
            ),
            FieldDefinition(
                name="host",
                field_type=str,
                default="0.0.0.0",
                description="Service host",
                env_var="SERVICE_HOST",
            ),
            FieldDefinition(
                name="workers",
                field_type=int,
                default=1,
                description="Number of worker processes",
                env_var="SERVICE_WORKERS",
                min_value=1,
                max_value=16,
            ),
        ]


class NestedConfig:
    """Configuration class that supports nested dictionary access."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize with nested configuration data."""
        self._data = kwargs

    def __getattr__(self, name: str) -> Any:
        """Get nested configuration value."""
        if name in self._data:
            value = self._data[name]
            if isinstance(value, dict):
                return NestedConfig(**value)
            return value
        raise AttributeError(f"Configuration field '{name}' not found")

    def __getitem__(self, key: str) -> Any:
        """Get configuration value by key."""
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with default."""
        return self._data.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return self._data.copy()


class TelemetryConfig(BaseConfig):
    """Telemetry configuration."""

    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return [
            FieldDefinition(
                name="enabled",
                field_type=bool,
                default=True,
                description="Enable telemetry",
                env_var="TELEMETRY_ENABLED",
            ),
            FieldDefinition(
                name="metrics_port",
                field_type=int,
                default=9090,
                description="Metrics port",
                env_var="METRICS_PORT",
                min_value=1024,
                max_value=65535,
            ),
            FieldDefinition(
                name="jaeger_endpoint",
                field_type=str,
                default="",
                description="Jaeger endpoint URL",
                env_var="JAEGER_ENDPOINT",
            ),
            FieldDefinition(
                name="discord_warmup_audio",
                field_type=bool,
                default=True,
                description="Enable Discord audio warm-up to avoid first-interaction latency spikes",
                env_var="DISCORD_WARMUP_AUDIO",
            ),
        ]


def create_field_definition(
    name: str,
    field_type: type[Any],
    default: Any = None,
    required: bool = False,
    description: str = "",
    validator: Callable[[Any], bool] | None = None,
    env_var: str | None = None,
    choices: list[Any] | None = None,
    min_value: int | float | None = None,
    max_value: int | float | None = None,
    pattern: str | None = None,
) -> FieldDefinition:
    """Convenience function for creating field definitions.

    Args:
        name: Field name
        field_type: Python type for the field
        default: Default value
        required: Whether the field is required
        description: Field description
        validator: Custom validation function
        env_var: Environment variable name
        choices: List of valid choices
        min_value: Minimum value (for numeric fields)
        max_value: Maximum value (for numeric fields)
        pattern: Regex pattern (for string fields)

    Returns:
        FieldDefinition instance
    """
    return FieldDefinition(
        name=name,
        field_type=field_type,
        default=default,
        required=required,
        description=description,
        validator=validator,
        env_var=env_var,
        choices=choices,
        min_value=min_value,
        max_value=max_value,
        pattern=pattern,
    )
