"""Configuration system for audio-orchestrator services.

This module provides a unified configuration system with:
- Hybrid approach (environment variables + config files)
- Type-safe configuration classes
- Validation framework
- Migration utilities
"""

from .base import (
    AudioConfig,
    BaseConfig,
    ConfigError,
    Environment,
    FieldDefinition,
    HttpConfig,
    LoggingConfig,
    NestedConfig,
    RequiredFieldError,
    ServiceConfig,
    TelemetryConfig,
    ValidationError,
    create_field_definition,
)
from .loader import (
    get_env_with_default,
    load_config_from_env,
    load_environment_variables,
    validate_required_env_vars,
)
from .migration import ConfigMigrationValidator, migrate_config_file
from .presets import (
    DiscordConfig,
    OrchestratorConfig,
    STTConfig,
    TTSConfig,
    WakeConfig,
    get_service_preset,
)
from .validator import (
    create_validator,
    validate_audio_channels_validator,
    validate_audio_sample_rate,
    validate_choice,
    validate_http_url,
    validate_pattern,
    validate_port,
    validate_positive_float_value,
    validate_positive_integer,
    validate_range,
    validate_timeout_value,
    validate_url,
)

__all__ = [
    # Base classes
    "BaseConfig",
    "ConfigError",
    "ValidationError",
    "RequiredFieldError",
    "FieldDefinition",
    "Environment",
    # Core configurations
    "LoggingConfig",
    "HttpConfig",
    "AudioConfig",
    "ServiceConfig",
    "TelemetryConfig",
    "NestedConfig",
    # Service configurations
    "DiscordConfig",
    "STTConfig",
    "TTSConfig",
    "OrchestratorConfig",
    "WakeConfig",
    # Utilities
    "load_environment_variables",
    "load_config_from_env",
    "validate_required_env_vars",
    "get_env_with_default",
    "get_service_preset",
    # Migration
    "ConfigMigrationValidator",
    "migrate_config_file",
    # Validators
    "validate_url",
    "validate_port",
    "validate_audio_sample_rate",
    "validate_audio_channels_validator",
    "validate_timeout",
    "validate_positive_int",
    "validate_positive_float",
    "validate_range",
    "validate_choice",
    "validate_pattern",
    "create_validator",
    "validate_http_url",
    "validate_timeout_value",
    "validate_positive_integer",
    "validate_positive_float_value",
    # Field definition utilities
    "create_field_definition",
]
