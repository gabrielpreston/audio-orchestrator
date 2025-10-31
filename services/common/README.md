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
    DiscordConfig, AudioConfig, STTConfig, WakeConfig, TelemetryConfig
)

config = (
    ConfigBuilder.for_service("discord", Environment.DOCKER)
    .add_config("discord", DiscordConfig)
    .add_config("audio", AudioConfig)
    .add_config("stt", STTConfig)
    .add_config("wake", WakeConfig)
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
from services.common.service_configs import OrchestratorConfig

config = (
    ConfigBuilder.for_service("orchestrator", Environment.DOCKER)
    .add_config("logging", LoggingConfig)
    .add_config("http", HttpConfig)
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

## BackgroundModelLoader

The `BackgroundModelLoader` provides a unified pattern for model loading across all services with:
- **Cache-first + download fallback**: Try local cache first, download if needed
- **Background loading**: Non-blocking startup (models load in background)
- **Lazy loading fallback**: If background fails, models load on first request
- **Graceful API handling**: Services can check status and return 503 when models aren't ready
- **Race condition protection**: Multiple concurrent requests handled safely

### Basic Usage

```python
from services.common.model_loader import BackgroundModelLoader
from services.common.structured_logging import get_logger

logger = get_logger(__name__)

# Define loader functions
def load_from_cache() -> Any | None:
    """Try loading from local cache."""
    # Return model if cache hit, None if cache miss
    pass

def load_with_download() -> Any:
    """Download and load model."""
    # Return loaded model
    pass

# Create loader
model_loader = BackgroundModelLoader(
    cache_loader_func=load_from_cache,
    download_loader_func=load_with_download,
    logger=logger,
    loader_name="my_model",
)

# Start background loading (non-blocking)
await model_loader.initialize()

# Check status in API endpoints
if model_loader.is_loading():
    raise HTTPException(status_code=503, detail="Model loading...")

if not model_loader.is_loaded():
    raise HTTPException(status_code=503, detail="Model not available")

# Get model
model = model_loader.get_model()
```

### Patterns

#### Side-Effect Functions (Bark)

Some loaders don't return a model object, they load into memory:

```python
model_loader = BackgroundModelLoader(
    cache_loader_func=None,
    download_loader_func=preload_models,  # Doesn't return model
    logger=logger,
    loader_name="bark_models",
    is_side_effect=True,  # Indicates side-effect function
)
```

#### Tuple Returns (FLAN)

Some loaders return multiple objects (model + tokenizer):

```python
def load_from_cache() -> tuple[Any, Any] | None:
    return (model, tokenizer) if cached else None

def load_with_download() -> tuple[Any, Any]:
    return (model, tokenizer)

model_loader = BackgroundModelLoader(
    cache_loader_func=load_from_cache,
    download_loader_func=load_with_download,
    logger=logger,
    loader_name="flan_t5",
)

# Get tuple
model, tokenizer = model_loader.get_model()
```

#### Lazy Loading Only (Audio Enhancer)

For services that load models only when used:

```python
model_loader = BackgroundModelLoader(
    cache_loader_func=load_from_cache,
    download_loader_func=load_with_download,
    logger=logger,
    loader_name="metricgan",
    enable_background_load=False,  # Don't load at startup
)

# Load on first use
if not model_loader.is_loaded():
    await model_loader.ensure_loaded()
```

#### Force Download

Force download allows bypassing the cache to re-download models. This is useful when you need to ensure you have the latest model versions or want to refresh cached models.

```python
# Force download via environment variable
# Set FORCE_MODEL_DOWNLOAD=true (global) or
# FORCE_MODEL_DOWNLOAD_{LOADER_NAME_UPPERCASE}=true (service-specific)
model_loader = BackgroundModelLoader(
    cache_loader_func=load_from_cache,
    download_loader_func=load_with_download,
    logger=logger,
    loader_name="whisper_model",  # Maps to FORCE_MODEL_DOWNLOAD_WHISPER_MODEL
)

# Or force download programmatically
model_loader = BackgroundModelLoader(
    cache_loader_func=load_from_cache,
    download_loader_func=load_with_download,
    logger=logger,
    loader_name="whisper_model",
    force_download=True,  # Overrides environment variables
)

# Check if force download is enabled
if model_loader.is_force_download():
    print("Force download is enabled - cache will be bypassed")
```

**Environment Variable Mapping:**
- Global: `FORCE_MODEL_DOWNLOAD=true` applies to all services
- Service-specific: `FORCE_MODEL_DOWNLOAD_{LOADER_NAME_UPPERCASE}=true` (e.g., `FORCE_MODEL_DOWNLOAD_WHISPER_MODEL=true`)
- Service-specific overrides global setting

### API Request Handling Pattern

Standard pattern for all service endpoints:

```python
@app.post("/endpoint")
async def endpoint(request: Request):
    # Check if model is loading (non-blocking)
    if _model_loader.is_loading():
        raise HTTPException(
            status_code=503,
            detail="Model is currently loading. Please try again shortly."
        )

    # Check if model is loaded (non-blocking)
    if not _model_loader.is_loaded():
        status = _model_loader.get_status()
        error_msg = status.get("error", "Model not available")
        raise HTTPException(
            status_code=503,
            detail=f"Model not available: {error_msg}"
        )

    # Model is loaded, proceed
    model = _model_loader.get_model()
    # ... use model ...
```

### Integration with Health Checks

```python
# In health check registration
_health_manager.register_dependency(
    "model_loaded", lambda: _model_loader.is_loaded()
)
```

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
