"""Comprehensive configuration management library for audio-orchestrator services.

This module provides a unified, type-safe, and validated configuration system
that can be used across all Python services in the project.

Key Features:
- Type-safe configuration classes with full validation
- Environment variable loading with automatic type conversion
- Custom validators for complex validation rules
- Support for different configuration sources (env vars, files, defaults)
- Comprehensive error reporting with clear messages
- Service-specific configuration presets
- Environment-aware configuration loading
- Hybrid configuration approach (env vars + config files)

Usage:
    from services.common.config import ConfigBuilder, ServiceConfig

    # Load configuration for a specific service
    config = ConfigBuilder.for_service("discord").load()

    # Access configuration values
    print(config.discord.token)
    print(config.audio.sample_rate)

    # Validate configuration
    config.validate()
"""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar, Union, get_args, get_origin

from services.common.logging import get_logger


logger = get_logger(__name__)

T = TypeVar("T")


class ConfigError(Exception):
    """Base exception for configuration-related errors."""


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


class Environment(Enum):
    """Supported environment types."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"
    DOCKER = "docker"


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
        if (
            self.choices
            and self.default is not None
            and self.default not in self.choices
        ):
            raise ValueError(f"Default value for field '{self.name}' not in choices")
        if self.pattern and not isinstance(self.pattern, str):
            raise ValueError(f"Pattern for field '{self.name}' must be a string")


class BaseConfig(ABC):
    """Abstract base class for configuration sections."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize configuration with provided values."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @classmethod
    @abstractmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        """Return field definitions for this configuration class."""
        return []

    def validate(self) -> None:
        """Validate all fields in this configuration."""
        for field_def in self.get_field_definitions():
            value = getattr(self, field_def.name, None)
            self._validate_field(field_def, value)

    def _validate_field(self, field_def: FieldDefinition, value: Any) -> None:
        """Validate a single field."""
        # Check required fields
        if field_def.required and value is None:
            raise RequiredFieldError(field_def.name)

        # Skip validation for None values (unless required)
        if value is None:
            return

        # Type validation
        if not isinstance(value, field_def.field_type):
            raise ValidationError(
                field_def.name,
                value,
                f"Expected type {field_def.field_type.__name__}, got {type(value).__name__}",
            )

        # Choices validation
        if field_def.choices and value not in field_def.choices:
            raise ValidationError(
                field_def.name,
                value,
                f"Value must be one of {field_def.choices}",
            )

        # Range validation
        if field_def.min_value is not None and value < field_def.min_value:
            raise ValidationError(
                field_def.name,
                value,
                f"Value must be >= {field_def.min_value}",
            )

        if field_def.max_value is not None and value > field_def.max_value:
            raise ValidationError(
                field_def.name,
                value,
                f"Value must be <= {field_def.max_value}",
            )

        # Pattern validation
        if (
            field_def.pattern
            and isinstance(value, str)
            and not re.match(field_def.pattern, value)
        ):
            raise ValidationError(
                field_def.name,
                value,
                f"Value must match pattern: {field_def.pattern}",
            )

        # Custom validator
        if field_def.validator and not field_def.validator(value):
            raise ValidationError(
                field_def.name,
                value,
                "Custom validation failed",
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        result = {}
        for field_def in self.get_field_definitions():
            value = getattr(self, field_def.name, None)
            if value is not None:
                result[field_def.name] = value
        return result

    def __repr__(self) -> str:
        """String representation of configuration."""
        return f"{self.__class__.__name__}({', '.join(f'{k}={v!r}' for k, v in self.to_dict().items())})"


class LoggingConfig(BaseConfig):
    """Logging configuration."""

    def __init__(
        self,
        level: str = "INFO",
        json_logs: bool = True,
        service_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.level = level
        self.json_logs = json_logs
        self.service_name = service_name

    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return [
            FieldDefinition(
                name="level",
                field_type=str,
                default="INFO",
                description="Logging level",
                choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                env_var="LOG_LEVEL",
            ),
            FieldDefinition(
                name="json_logs",
                field_type=bool,
                default=True,
                description="Whether to use JSON logging format",
                env_var="LOG_JSON",
            ),
            FieldDefinition(
                name="service_name",
                field_type=str,
                description="Name of the service for logging context",
                env_var="SERVICE_NAME",
            ),
        ]


class DatabaseConfig(BaseConfig):
    """Database configuration."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        name: str = "discord_voice_lab",
        user: str = "postgres",
        password: str = "",
        ssl_mode: str = "prefer",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.host = host
        self.port = port
        self.name = name
        self.user = user
        self.password = password
        self.ssl_mode = ssl_mode

    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return [
            FieldDefinition(
                name="host",
                field_type=str,
                default="localhost",
                description="Database host",
                env_var="DB_HOST",
            ),
            FieldDefinition(
                name="port",
                field_type=int,
                default=5432,
                description="Database port",
                min_value=1,
                max_value=65535,
                env_var="DB_PORT",
            ),
            FieldDefinition(
                name="name",
                field_type=str,
                default="discord_voice_lab",
                description="Database name",
                env_var="DB_NAME",
            ),
            FieldDefinition(
                name="user",
                field_type=str,
                default="postgres",
                description="Database user",
                env_var="DB_USER",
            ),
            FieldDefinition(
                name="password",
                field_type=str,
                default="",
                description="Database password",
                env_var="DB_PASSWORD",
            ),
            FieldDefinition(
                name="ssl_mode",
                field_type=str,
                default="prefer",
                description="SSL mode for database connection",
                choices=[
                    "disable",
                    "allow",
                    "prefer",
                    "require",
                    "verify-ca",
                    "verify-full",
                ],
                env_var="DB_SSL_MODE",
            ),
        ]


class HttpConfig(BaseConfig):
    """HTTP client configuration."""

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        user_agent: str = "audio-orchestrator/1.0",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.user_agent = user_agent

    @classmethod
    def get_field_definitions(cls) -> list[FieldDefinition]:
        return [
            FieldDefinition(
                name="timeout",
                field_type=float,
                default=30.0,
                description="HTTP request timeout in seconds",
                min_value=0.1,
                max_value=300.0,
                env_var="HTTP_TIMEOUT",
            ),
            FieldDefinition(
                name="max_retries",
                field_type=int,
                default=3,
                description="Maximum number of retries for failed requests",
                min_value=0,
                max_value=10,
                env_var="HTTP_MAX_RETRIES",
            ),
            FieldDefinition(
                name="retry_delay",
                field_type=float,
                default=1.0,
                description="Delay between retries in seconds",
                min_value=0.1,
                max_value=60.0,
                env_var="HTTP_RETRY_DELAY",
            ),
            FieldDefinition(
                name="user_agent",
                field_type=str,
                default="audio-orchestrator/1.0",
                description="User agent string for HTTP requests",
                env_var="HTTP_USER_AGENT",
            ),
        ]


class EnvironmentLoader:
    """Loads configuration from environment variables."""

    def __init__(self, prefix: str = "") -> None:
        """Initialize with optional prefix for environment variables."""
        self.prefix = prefix.upper() + "_" if prefix else ""

    def load_field(self, field_def: FieldDefinition) -> Any:
        """Load a single field from environment variables."""
        env_var = field_def.env_var or f"{self.prefix}{field_def.name.upper()}"
        raw_value = os.getenv(env_var)

        # Return default if no environment variable
        if raw_value is None:
            if field_def.required:
                raise RequiredFieldError(field_def.name)
            return field_def.default

        # Convert and validate the value
        try:
            value = self._convert_value(raw_value, field_def.field_type)
            return value
        except (ValueError, TypeError) as e:
            raise ValidationError(
                field_def.name,
                raw_value,
                f"Failed to convert environment variable {env_var}: {e}",
            ) from e

    def _convert_value(self, raw_value: str, target_type: type[T]) -> T:
        """Convert string value to target type."""
        origin = get_origin(target_type)
        args = get_args(target_type)

        if target_type is bool:
            return raw_value.lower() in ("1", "true", "yes", "on")  # type: ignore
        elif target_type is int:
            return int(raw_value)  # type: ignore
        elif target_type is float:
            return float(raw_value)  # type: ignore
        elif target_type is str:
            return raw_value  # type: ignore
        elif target_type is list or origin is list:
            return [item.strip() for item in raw_value.split(",") if item.strip()]  # type: ignore
        elif origin is Union and type(None) in args and str in args:
            # Handle Optional[str]
            return raw_value if raw_value else None  # type: ignore
        else:
            # Try to use the type as a constructor
            return target_type(raw_value)  # type: ignore

    def load_config(self, config_class: type[T]) -> T:
        """Load configuration for a given class from environment variables."""
        field_definitions = config_class.get_field_definitions()  # type: ignore[attr-defined]
        kwargs = {}

        for field_def in field_definitions:
            try:
                value = self.load_field(field_def)
                kwargs[field_def.name] = value
            except (RequiredFieldError, ValidationError) as e:
                logger.error(
                    "config.load_field_failed",
                    field=field_def.name,
                    error=str(e),
                )
                raise

        return config_class(**kwargs)


class ConfigBuilder:
    """Builder for creating service configurations."""

    def __init__(
        self, service_name: str, environment: Environment = Environment.DEVELOPMENT
    ):
        self.service_name = service_name
        self.environment = environment
        self.loader = EnvironmentLoader(service_name)
        self._configs: dict[str, BaseConfig] = {}

    @classmethod
    def for_service(
        cls, service_name: str, environment: Environment = Environment.DEVELOPMENT
    ) -> ConfigBuilder:
        """Create a configuration builder for a specific service."""
        return cls(service_name, environment)

    def add_config(self, name: str, config_class: type[BaseConfig]) -> ConfigBuilder:
        """Add a configuration section."""
        config = self.loader.load_config(config_class)
        self._configs[name] = config
        return self

    def load(self) -> ServiceConfig:
        """Load and return the complete service configuration."""
        return ServiceConfig(
            service_name=self.service_name,
            environment=self.environment,
            configs=self._configs,
        )


@dataclass
class ServiceConfig:
    """Complete configuration for a service."""

    service_name: str
    environment: Environment
    configs: Mapping[str, BaseConfig]

    def get_config(self, name: str) -> BaseConfig:
        """Get a specific configuration section."""
        if name not in self.configs:
            raise KeyError(f"Configuration section '{name}' not found")
        return self.configs[name]

    def validate(self) -> None:
        """Validate all configuration sections."""
        for name, config in self.configs.items():
            try:
                config.validate()
                logger.debug(
                    "config.section_validated",
                    service=self.service_name,
                    section=name,
                )
            except (ValidationError, RequiredFieldError) as e:
                logger.error(
                    "config.section_validation_failed",
                    service=self.service_name,
                    section=name,
                    error=str(e),
                )
                raise

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "service_name": self.service_name,
            "environment": self.environment.value,
            "configs": {
                name: config.to_dict() for name, config in self.configs.items()
            },
        }

    def __getattr__(self, name: str) -> BaseConfig:
        """Allow direct access to configuration sections."""
        return self.get_config(name)

    def __repr__(self) -> str:
        """String representation of service configuration."""
        return (
            f"ServiceConfig(service={self.service_name}, "
            f"environment={self.environment.value}, "
            f"sections={list(self.configs.keys())})"
        )


# Convenience functions for common configuration patterns
def load_service_config(
    service_name: str, environment: Environment = Environment.DEVELOPMENT
) -> ServiceConfig:
    """Load configuration for a service with common sections."""
    builder = ConfigBuilder.for_service(service_name, environment)

    # Add common configuration sections
    builder.add_config("logging", LoggingConfig)
    builder.add_config("http", HttpConfig)

    return builder.load()


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
    """Convenience function for creating field definitions."""
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


# Common validators
def validate_url(value: str) -> bool:
    """Validate that a string is a valid URL."""
    pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return bool(pattern.match(value))


def validate_port(value: int) -> bool:
    """Validate that a value is a valid port number."""
    return 1 <= value <= 65535


def validate_positive(value: int | float) -> bool:
    """Validate that a value is positive."""
    return value > 0


def validate_non_negative(value: int | float) -> bool:
    """Validate that a value is non-negative."""
    return value >= 0


__all__ = [
    "BaseConfig",
    "ConfigBuilder",
    "ConfigError",
    "DatabaseConfig",
    "Environment",
    "EnvironmentLoader",
    "FieldDefinition",
    "HttpConfig",
    "LoggingConfig",
    "RequiredFieldError",
    "ServiceConfig",
    "ValidationError",
    "create_field_definition",
    "load_service_config",
    "validate_non_negative",
    "validate_port",
    "validate_positive",
    "validate_url",
]
