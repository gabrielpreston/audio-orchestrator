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

from services.common.logging import get_logger

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
        """Load values from environment variables."""
        for field_def in self.get_field_definitions():
            if field_def.env_var and field_def.name not in self._values:
                env_value = os.getenv(field_def.env_var)
                if env_value is not None:
                    self._values[field_def.name] = self._convert_env_value(
                        env_value, field_def.field_type
                    )

    def _convert_env_value(self, value: str, field_type: type[Any]) -> Any:
        """Convert environment variable string to appropriate type."""
        if field_type == bool:
            return value.lower() in ("true", "1", "yes", "on")
        elif field_type == int:
            return int(value)
        elif field_type == float:
            return float(value)
        elif field_type == list:
            return [item.strip() for item in value.split(",")]
        else:
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
                self._values[field_def.name] = value

    def _validate_field(self, field_def: FieldDefinition, value: Any) -> None:
        """Validate a single field value."""
        # Type validation
        if not isinstance(value, field_def.field_type):
            raise ValidationError(
                field_def.name, value, f"Expected {field_def.field_type.__name__}"
            )

        # Choices validation
        if field_def.choices and value not in field_def.choices:
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
                name="service_url",
                field_type=str,
                default="http://audio-processor:9100",
                description="Audio processor service URL",
                env_var="AUDIO_SERVICE_URL",
            ),
            FieldDefinition(
                name="service_timeout",
                field_type=int,
                default=20,
                description="Audio processor service timeout in milliseconds",
                env_var="AUDIO_SERVICE_TIMEOUT",
                min_value=1,
                max_value=1000,
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
