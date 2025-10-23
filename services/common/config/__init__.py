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
    RequiredFieldError,
    ServiceConfig,
    TelemetryConfig,
    ValidationError,
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
    get_service_preset,
)
from .validator import (
    create_validator,
    validate_audio_channels,
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
    
    # Service configurations
    "DiscordConfig",
    "STTConfig",
    "TTSConfig",
    "OrchestratorConfig",
    
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
    "validate_audio_channels",
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
]
