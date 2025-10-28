---
title: Configuration Library Reference
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-18
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Reference ▸ Configuration Library Reference

# Configuration Management Library

The `services.common.config` module provides a comprehensive, type-safe, and validated configuration management system for all Python services in the audio-orchestrator project.

> **Status**: This configuration library is actively implemented and used by all services (discord, stt, llm, orchestrator, tts). All services use the ConfigBuilder pattern for type-safe configuration management.

## Overview

The configuration library addresses the inconsistencies and limitations found in the current configuration management across services:

-  **Type Safety**: Full type hints and validation for all configuration values
-  **Consistency**: Unified patterns across all services
-  **Validation**: Comprehensive input validation with clear error messages
-  **Flexibility**: Support for different configuration sources (env vars, files, defaults)
-  **Extensibility**: Easy to add new configuration sections
-  **Documentation**: Self-documenting configuration with descriptions
-  **Environment Awareness**: Support for different environments (dev, prod, test, docker)

## Core Components

### BaseConfig

Abstract base class for all configuration sections. Provides validation, serialization, and common functionality.

```python
from services.common.config import BaseConfig, FieldDefinition

class MyConfig(BaseConfig):
    def __init__(self, field1: str = "default", field2: int = 42, **kwargs):
        super().__init__(**kwargs)
        self.field1 = field1
        self.field2 = field2

    @classmethod
    def get_field_definitions(cls) -> List[FieldDefinition]:
        return [
            FieldDefinition(
                name="field1",
                field_type=str,
                default="default",
                description="First field",
                env_var="MY_FIELD1",
            ),
            FieldDefinition(
                name="field2",
                field_type=int,
                default=42,
                description="Second field",
                min_value=0,
                max_value=100,
                env_var="MY_FIELD2",
            ),
        ]
```

### FieldDefinition

Defines validation rules and metadata for configuration fields.

```python
FieldDefinition(
    name="field_name",           # Field name
    field_type=str,              # Python type
    default="default_value",     # Default value
    required=False,              # Whether field is required
    description="Field description",  # Human-readable description
    validator=validate_url,      # Custom validation function
    env_var="ENV_VAR_NAME",      # Environment variable name
    choices=["a", "b", "c"],     # Allowed values
    min_value=0,                 # Minimum value (for numbers)
    max_value=100,               # Maximum value (for numbers)
    pattern=r"^[a-z]+$",         # Regex pattern (for strings)
)
```

### EnvironmentLoader

Loads configuration from environment variables with automatic type conversion.

```python
from services.common.config import EnvironmentLoader

loader = EnvironmentLoader("MY_SERVICE")
config = loader.load_config(MyConfig)
```

### ConfigBuilder

Fluent API for building service configurations.

```python
from services.common.config import ConfigBuilder, Environment

config = (
    ConfigBuilder.for_service("discord", Environment.DOCKER)
    .add_config("discord", DiscordConfig)
    .add_config("audio", AudioConfig)
    .add_config("stt", STTConfig)
    .load()
)
```

### ServiceConfig

Complete configuration container for a service.

```python
# Access configuration sections
discord_config = config.discord
audio_config = config.audio

# Validate all configurations
config.validate()

# Convert to dictionary
config_dict = config.to_dict()

# Note: The configuration library is environment-driven. File persistence APIs are not provided.
```

## Service-Specific Configurations

The library includes pre-built configuration classes for all services:

### Discord Service

```python
from services.common.service_configs import (
    DiscordConfig, AudioConfig, STTConfig, WakeConfig,
    TelemetryConfig, OrchestratorClientConfig, DiscordRuntimeConfig,
)

config = (
    ConfigBuilder.for_service("discord", Environment.DOCKER)
    .add_config("discord", DiscordConfig)
    .add_config("audio", AudioConfig)
    .add_config("stt", STTConfig)
    .add_config("wake", WakeConfig)
    .add_config("telemetry", TelemetryConfig)
    .add_config("orchestrator", OrchestratorClientConfig)
    .add_config("runtime", DiscordRuntimeConfig)
    .load()
)
```

### STT Service

```python
from services.common.service_configs import FasterWhisperConfig, TelemetryConfig

config = (
    ConfigBuilder.for_service("stt", Environment.DOCKER)
    .add_config("logging", LoggingConfig)
    .add_config("http", HttpConfig)
    .add_config("faster_whisper", FasterWhisperConfig)
    .add_config("telemetry", TelemetryConfig)
    .load()
)
```

### TTS Service

```python
from services.common.service_configs import TTSConfig, TelemetryConfig

config = (
    ConfigBuilder.for_service("tts", Environment.DOCKER)
    .add_config("logging", LoggingConfig)
    .add_config("http", HttpConfig)
    .add_config("tts", TTSConfig)
    .add_config("telemetry", TelemetryConfig)
    .load()
)
```

### LLM Service

```python
from services.common.service_configs import (
    LlamaConfig, LLMServiceConfig, TTSClientConfig, LoggingConfig, HttpConfig, TelemetryConfig
)

config = (
    ConfigBuilder.for_service("llm", Environment.DOCKER)
    .add_config("logging", LoggingConfig)
    .add_config("http", HttpConfig)
    .add_config("llama", LlamaConfig)
    .add_config("service", LLMServiceConfig)
    .add_config("tts", TTSClientConfig)
    .add_config("telemetry", TelemetryConfig)
    .load()
)
```

## Validation

The library provides comprehensive validation with clear error messages:

### Built-in Validators

```python
from services.common.config import validate_url, validate_port, validate_positive, validate_non_negative

# URL validation
validate_url("http://example.com")  # True
validate_url("not-a-url")          # False

# Port validation
validate_port(8080)  # True
validate_port(99999) # False

# Number validation
validate_positive(1)    # True
validate_positive(-1)   # False
validate_non_negative(0) # True
validate_non_negative(-1) # False
```

### Custom Validators

```python
def validate_odd_number(value: int) -> bool:
    return value % 2 == 1

field_def = FieldDefinition(
    name="odd_field",
    field_type=int,
    validator=validate_odd_number,
)
```

### Validation Errors

```python
try:
    config.validate()
except ValidationError as e:
    print(f"Validation failed for field '{e.field}': {e.message}")
except RequiredFieldError as e:
    print(f"Required field '{e.field}' is missing")
```

## Environment Variables

The library automatically maps configuration fields to environment variables:

### Default Mapping

Field names are automatically converted to environment variables:

-  `field_name` → `FIELD_NAME`
-  `myField` → `MY_FIELD`

### Custom Mapping

```python
FieldDefinition(
    name="database_url",
    field_type=str,
    env_var="DATABASE_CONNECTION_STRING",  # Custom environment variable
)
```

### Service Prefixes

```python
loader = EnvironmentLoader("DISCORD")  # Prefixes all env vars with "DISCORD_"
# field_name → DISCORD_FIELD_NAME
```

## Type Conversion

Automatic type conversion from environment variables:

| Environment Variable | Target Type | Result |
|---------------------|-------------|---------|
| `"true"` | `bool` | `True` |
| `"false"` | `bool` | `False` |
| `"42"` | `int` | `42` |
| `"3.14"` | `float` | `3.14` |
| `"a,b,c"` | `list` | `["a", "b", "c"]` |
| `"text"` | `str` | `"text"` |

## Configuration Persistence

Configuration is managed via environment variables. File-based persistence is not supported.

## Error Handling

The library provides comprehensive error handling:

### ConfigurationError

Base exception for all configuration-related errors.

### ValidationError

Raised when field validation fails:

```python
try:
    config.validate()
except ValidationError as e:
    print(f"Field '{e.field}' with value '{e.value}' failed validation: {e.message}")
```

### RequiredFieldError

Raised when a required field is missing:

```python
try:
    config.validate()
except RequiredFieldError as e:
    print(f"Required field '{e.field}' is missing")
```

## Best Practices

### 1. Use Type Hints

Always use type hints for configuration fields:

```python
def __init__(self, timeout: float = 30.0, max_retries: int = 3, **kwargs):
    super().__init__(**kwargs)
    self.timeout = timeout
    self.max_retries = max_retries
```

### 2. Provide Descriptions

Include helpful descriptions for all fields:

```python
FieldDefinition(
    name="timeout",
    field_type=float,
    default=30.0,
    description="Request timeout in seconds",
)
```

### 3. Use Validation

Add appropriate validation for all fields:

```python
FieldDefinition(
    name="port",
    field_type=int,
    default=8080,
    validator=validate_port,
    min_value=1,
    max_value=65535,
)
```

### 4. Set Sensible Defaults

Provide reasonable default values:

```python
FieldDefinition(
    name="max_retries",
    field_type=int,
    default=3,
    min_value=0,
    max_value=10,
)
```

### 5. Handle Required Fields

Mark truly required fields as required:

```python
FieldDefinition(
    name="api_key",
    field_type=str,
    required=True,
    description="API key for external service",
)
```

## Migration Guide

### From Current Discord Config

**Before:**

```python
# services/discord/config.py
@dataclass(slots=True)
class DiscordConfig:
    token: str
    guild_id: int
    voice_channel_id: int
    # ... more fields

def load_config() -> BotConfig:
    # Manual environment variable parsing
    # ... 100+ lines of parsing code
```

**After:**

```python
# services/discord/config.py
from services.common.service_configs import DiscordConfig, AudioConfig, STTConfig, WakeConfig, TelemetryConfig
from services.common.config import ConfigBuilder, Environment

def load_config():
    return (
        ConfigBuilder.for_service("discord", Environment.DOCKER)
        .add_config("discord", DiscordConfig)
        .add_config("audio", AudioConfig)
        .add_config("stt", STTConfig)
        .add_config("wake", WakeConfig)
        .add_config("telemetry", TelemetryConfig)
        .load()
    )
```

### From Current STT Config

**Before:**

```python
# services/stt/app.py
MODEL_NAME = os.environ.get("FW_MODEL", "small")
device = os.environ.get("FW_DEVICE", "cpu")
compute_type = os.environ.get("FW_COMPUTE_TYPE")
```

**After:**

```python
# services/stt/app.py
from services.common.config import load_service_config
from services.common.service_configs import FasterWhisperConfig

config = load_service_config("stt", Environment.DOCKER)
config.configs["faster_whisper"] = FasterWhisperConfig()

model_name = config.faster_whisper.model
device = config.faster_whisper.device
compute_type = config.faster_whisper.compute_type
```

## Examples

See `services/common/config_examples.py` for comprehensive examples of how to use the configuration library.

## Testing

Run the test suite to verify the configuration library works correctly:

```bash
cd services/common
python -m pytest test_config.py -v
```

## Future Enhancements

The configuration library is designed to be extensible. Future enhancements could include:

-  **Configuration hot-reloading**: Reload configuration without restarting services
-  **Configuration validation schemas**: JSON Schema or similar for external validation
-  **Configuration encryption**: Encrypt sensitive configuration values
-  **Configuration versioning**: Handle configuration schema changes over time
-  **Configuration inheritance**: Inherit configuration from parent services
-  **Configuration templates**: Pre-built configuration templates for common scenarios
