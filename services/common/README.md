# Common Configuration Library

A comprehensive, type-safe configuration management system for audio-orchestrator services.

## Features

-  **Type Safety**: Full type hints and validation for all configuration values
-  **Consistency**: Unified patterns across all services
-  **Validation**: Comprehensive input validation with clear error messages
-  **Flexibility**: Support for different configuration sources (env vars, files, defaults)
-  **Extensibility**: Easy to add new configuration sections
-  **Documentation**: Self-documenting configuration with descriptions
-  **Environment Awareness**: Support for different environments (dev, prod, test, docker)

## Quick Start

```python
from services.common.config import ConfigBuilder, Environment
from services.common.service_configs import DiscordConfig, AudioConfig

# Load configuration for Discord service
config = (
    ConfigBuilder.for_service("discord", Environment.DOCKER)
    .add_config("discord", DiscordConfig)
    .add_config("audio", AudioConfig)
    .load()
)

# Access configuration values
print(f"Discord token: {config.discord.token}")
print(f"Audio sample rate: {config.audio.input_sample_rate_hz}")

# Validate configuration
config.validate()
```

## Service-Specific Configurations

### Discord Service

```python
from services.common.service_configs import (
    DiscordConfig, AudioConfig, STTConfig, WakeConfig, MCPConfig, TelemetryConfig
)

config = (
    ConfigBuilder.for_service("discord", Environment.DOCKER)
    .add_config("discord", DiscordConfig)
    .add_config("audio", AudioConfig)
    .add_config("stt", STTConfig)
    .add_config("wake", WakeConfig)
    .add_config("mcp", MCPConfig)
    .add_config("telemetry", TelemetryConfig)
    .load()
)
```

### STT Service

```python
from services.common.service_configs import FasterWhisperConfig

config = (
    ConfigBuilder.for_service("stt", Environment.DOCKER)
    .add_config("logging", LoggingConfig)
    .add_config("http", HttpConfig)
    .add_config("faster_whisper", FasterWhisperConfig)
    .load()
)
```

### TTS Service

```python
from services.common.service_configs import TTSConfig

config = (
    ConfigBuilder.for_service("tts", Environment.DOCKER)
    .add_config("logging", LoggingConfig)
    .add_config("http", HttpConfig)
    .add_config("tts", TTSConfig)
    .load()
)
```

### Orchestrator Service

```python
from services.common.service_configs import LlamaConfig, OrchestratorConfig

config = (
    ConfigBuilder.for_service("orchestrator", Environment.DOCKER)
    .add_config("logging", LoggingConfig)
    .add_config("http", HttpConfig)
    .add_config("llama", LlamaConfig)
    .add_config("orchestrator", OrchestratorConfig)
    .load()
)
```

## Creating Custom Configurations

```python
from services.common.config import BaseConfig, FieldDefinition, create_field_definition

class MyConfig(BaseConfig):
    def __init__(self, field1: str = "default", field2: int = 42, **kwargs):
        super().__init__(**kwargs)
        self.field1 = field1
        self.field2 = field2
    
    @classmethod
    def get_field_definitions(cls):
        return [
            create_field_definition(
                name="field1",
                field_type=str,
                default="default",
                description="First field",
                env_var="MY_FIELD1",
            ),
            create_field_definition(
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

## Validation

The library provides comprehensive validation:

```python
# Built-in validators
from services.common.config import validate_url, validate_port, validate_positive

# Custom validators
def validate_odd_number(value: int) -> bool:
    return value % 2 == 1

field_def = create_field_definition(
    name="odd_field",
    field_type=int,
    validator=validate_odd_number,
)
```

## Error Handling

```python
try:
    config.validate()
except ValidationError as e:
    print(f"Validation failed for field '{e.field}': {e.message}")
except RequiredFieldError as e:
    print(f"Required field '{e.field}' is missing")
```

## Configuration Persistence

```python
# Save configuration to file
# Configuration is now managed through environment variables and service-specific configs
# No file-based persistence is available
```

## Environment Variables

The library automatically maps configuration fields to environment variables:

-  `field_name` → `FIELD_NAME`
-  `myField` → `MY_FIELD`
-  With service prefix: `DISCORD_FIELD_NAME`

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

## Examples

See `config_examples.py` for comprehensive examples.

## Testing

Run the test suite:

```bash
python -m pytest test_config.py -v
```

## Documentation

-  [Configuration Library Reference](../docs/reference/configuration-library.md)
-  [Migration Guide](../docs/reference/config-migration-guide.md)

## Migration from Current Approach

The new configuration library replaces the current manual environment variable parsing approach used across services. See the migration guide for detailed instructions on how to migrate each service.

### Benefits of Migration

-  **Reduced Code**: Eliminate 100+ lines of manual parsing per service
-  **Type Safety**: Catch configuration errors at startup
-  **Consistency**: Unified configuration patterns across all services
-  **Maintainability**: Easy to add new configuration fields
-  **Documentation**: Self-documenting configuration with descriptions
-  **Validation**: Comprehensive validation with clear error messages
-  **Testing**: Easy to test configuration loading and validation