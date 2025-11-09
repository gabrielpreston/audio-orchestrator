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

## PyTorch Optimization Utilities

### torch.compile() Integration (`torch_compile.py`)

Centralized PyTorch model compilation with consistent error handling:

```python
from services.common.torch_compile import compile_model_if_enabled

# Compile model if enabled via {SERVICE}_ENABLE_TORCH_COMPILE env var
model = AutoModelForSeq2SeqLM.from_pretrained(...)
model = compile_model_if_enabled(model, "flan", "flan_t5", logger)
```

**Features**:
- Automatic Docker compatibility (configures `torch._dynamo.config.suppress_errors`)
- Configurable compile modes (default, reduce-overhead, max-autotune, max-autotune-no-cudagraphs)
- Graceful degradation (returns original model on failure)
- Duration logging and error handling

**Configuration**: `{SERVICE}_ENABLE_TORCH_COMPILE`, `{SERVICE}_COMPILE_MODE`

### Pre-warming (`prewarm.py`)

Generic pre-warming pattern for triggering torch.compile() warmup during startup:

```python
from services.common.prewarm import prewarm_if_enabled

async def _prewarm():
    # Perform a dummy inference to trigger compilation
    model.generate(...)

await prewarm_if_enabled(
    _prewarm,
    "flan",
    logger,
    model_loader=_model_loader,
    health_manager=_health_manager,
)
```

**Features**:
- Waits for model loading before pre-warming
- Registers health dependency automatically
- Non-blocking (marks complete on failure)
- Configurable via `{SERVICE}_ENABLE_PREWARM` env var

### Result Caching (`result_cache.py`)

Generic LRU cache for service results:

```python
from services.common.result_cache import ResultCache, generate_cache_key

# Initialize cache
cache = ResultCache(max_entries=200, max_size_mb=1000, service_name="stt")

# Check cache before inference
cache_key = generate_cache_key(audio_bytes)
cached = cache.get(cache_key)
if cached:
    return cached

# Perform inference...
result = perform_inference(...)

# Cache result
cache.put(cache_key, result)
```

**Features**:
- LRU eviction by entry count and memory size
- Generic type support (bytes, dict, str, etc.)
- Statistics tracking (hits, misses, hit_rate)
- Configurable via `{SERVICE}_ENABLE_CACHE`, `{SERVICE}_CACHE_MAX_ENTRIES`, `{SERVICE}_CACHE_MAX_SIZE_MB`

## Metric Registration (`audio_metrics.py`)

Standardized metric registration helper to reduce boilerplate and ensure consistency across services.

### Quick Start

```python
from services.common.audio_metrics import MetricKind, register_service_metrics
from services.common.tracing import get_observability_manager

async def _startup() -> None:
    # Get observability manager (factory already setup observability)
    _observability_manager = get_observability_manager("my_service")

    # Register all required metrics in one call
    metrics = register_service_metrics(
        _observability_manager,
        kinds=[MetricKind.AUDIO, MetricKind.SYSTEM]
    )

    # Access metrics by group
    _audio_metrics = metrics["audio"]
    _system_metrics = metrics["system"]

    # HTTP metrics already available from app_factory via app.state.http_metrics
```

### Metric Kinds

The `MetricKind` enum provides type-safe specification of metric types:

- `MetricKind.AUDIO` - Audio processing metrics (chunks, duration, quality)
- `MetricKind.STT` - Speech-to-text metrics (transcriptions, latency)
- `MetricKind.TTS` - Text-to-speech metrics (synthesis, duration)
- `MetricKind.LLM` - Language model metrics (requests, tokens, latency)
- `MetricKind.HTTP` - HTTP request metrics (requests, duration, status codes)
- `MetricKind.SYSTEM` - System resource metrics (CPU, memory, GPU)
- `MetricKind.GUARDRAILS` - Safety/guardrails metrics (validations, blocks)

### Service Patterns

#### Audio Processing Service
```python
metrics = register_service_metrics(
    _observability_manager,
    kinds=[MetricKind.AUDIO, MetricKind.SYSTEM]
)
_audio_metrics = metrics["audio"]
_system_metrics = metrics["system"]
```

#### STT Service
```python
metrics = register_service_metrics(
    _observability_manager,
    kinds=[MetricKind.STT, MetricKind.SYSTEM]
)
_stt_metrics = metrics["stt"]
_system_metrics = metrics["system"]
```

#### Orchestrator Service
```python
metrics = register_service_metrics(
    _observability_manager,
    kinds=[MetricKind.LLM, MetricKind.SYSTEM]
)
_llm_metrics = metrics["llm"]
_system_metrics = metrics["system"]
```

#### Multi-Metric Services
```python
# Discord service uses multiple metric types
metrics = register_service_metrics(
    _observability_manager,
    kinds=[MetricKind.STT, MetricKind.AUDIO, MetricKind.SYSTEM]
)
_stt_metrics = metrics["stt"]
_audio_metrics = metrics["audio"]
_system_metrics = metrics["system"]
```

#### Services with Only HTTP Metrics
```python
# Monitoring/testing services - HTTP metrics already in app.state.http_metrics
# No service-specific metrics needed
async def _startup() -> None:
    _observability_manager = get_observability_manager("monitoring")
    # HTTP metrics available via app.state.http_metrics (auto-created by app_factory)
```

### HTTP Metrics Handling

HTTP metrics are automatically created by `app_factory.py` and stored in `app.state.http_metrics`. Services should:

1. **Reuse existing HTTP metrics** - Access via `app.state.http_metrics` in route handlers
2. **Don't create duplicate HTTP metrics** - The factory already creates them
3. **Use ObservabilityMiddleware** - HTTP metrics are automatically recorded by middleware

```python
# In route handlers - HTTP metrics already recorded by middleware
@app.post("/endpoint")
async def endpoint(request: Request):
    # No manual HTTP metric recording needed - middleware handles it
    # Access metrics via app.state.http_metrics if needed
    http_metrics = request.app.state.http_metrics
    # ...
```

### Features

- **Type Safety**: `MetricKind` enum prevents typos and enables IDE autocomplete
- **Error Handling**: Continues with other metrics if one fails to register
- **Validation**: Validates metric kinds and provides clear error messages
- **Consistency**: Standardized pattern across all services
- **Backward Compatible**: Existing `create_*_metrics()` functions remain public

### Error Handling

The helper gracefully handles registration failures:

```python
# If one metric type fails, others still register
metrics = register_service_metrics(
    _observability_manager,
    kinds=[MetricKind.AUDIO, MetricKind.SYSTEM]
)
# If SYSTEM metrics fail, audio metrics will still be available
_audio_metrics = metrics["audio"]  # May be empty dict if registration failed
_system_metrics = metrics["system"]  # May be empty dict if registration failed
```

### Integration with App Factory

The metric registration pattern integrates seamlessly with `create_service_app()`:

```python
from services.common.app_factory import create_service_app
from services.common.audio_metrics import MetricKind, register_service_metrics
from services.common.tracing import get_observability_manager

async def _startup() -> None:
    # Observability already setup by factory
    _observability_manager = get_observability_manager("my_service")

    # Register service-specific metrics
    metrics = register_service_metrics(
        _observability_manager,
        kinds=[MetricKind.AUDIO, MetricKind.SYSTEM]
    )
    _audio_metrics = metrics["audio"]
    _system_metrics = metrics["system"]

    # HTTP metrics already in app.state.http_metrics (created by factory)

app = create_service_app(
    "my_service",
    "1.0.0",
    startup_callback=_startup,
)
```

## Wake Detection (`wake_detection.py`)

The `WakeDetector` class provides service-agnostic wake phrase detection for any audio I/O surface. It supports both audio-based detection (primary) and transcript-based detection (fallback).

### Features

- **Audio-Based Detection**: Uses openwakeword models for real-time wake phrase detection from PCM audio
- **Transcript Fallback**: Falls back to transcript-based pattern matching if audio models unavailable
- **Three-Tier Model Loading**: User-provided paths → Auto-discovery → Built-in defaults
- **Resampling Support**: Automatically resamples audio to target sample rate (default 16kHz)
- **Format Conversion**: Automatically converts normalized float32 audio to int16 PCM format required by OpenWakeWord
- **Graceful Degradation**: Continues operation even if models fail to load

### Audio Format Requirements

**Important**: OpenWakeWord requires 16-bit PCM audio (`np.int16`). The `WakeDetector` automatically:
- Normalizes audio to float32 for processing (padding/truncation)
- Converts back to int16 before passing to the model
- Clamps values to prevent overflow during conversion

The conversion is logged at DEBUG level with event `wake.format_conversion` for troubleshooting.

### Basic Usage

```python
from services.common.wake_detection import WakeDetector, WakeDetectionResult
from services.common.config.presets import WakeConfig

# Create wake config
wake_config = WakeConfig(
    model_paths=[],  # Empty = auto-discover in ./services/models/wake/
    activation_threshold=0.5,
    target_sample_rate_hz=16000,
    enabled=True,
)

# Initialize detector
wake_detector = WakeDetector(wake_config, service_name="discord")

# Detect from audio PCM bytes
pcm_bytes = b"..."
sample_rate = 48000
result = wake_detector.detect_audio(pcm_bytes, sample_rate)
if result:
    print(f"Wake phrase '{result.phrase}' detected with confidence {result.confidence}")

# Note: Transcript-based detection is disabled as wake phrases are determined by the model itself
```

### Model Loading Strategy

The detector uses a three-tier fallback strategy:

1. **Tier 1**: User-provided paths via `WAKE_MODEL_PATHS` environment variable
2. **Tier 2**: Auto-discovery in `./services/models/wake/` directory (`.tflite` or `.onnx` files)
3. **Tier 3**: Built-in default models (if available from openwakeword)

**Model Filtering**:

All model paths (user-provided and auto-discovered) are automatically filtered to ensure only wake word models are loaded:

-  **Infrastructure models excluded**: Models with names containing `embedding_model`, `melspectrogram`, or `silero_vad` are automatically filtered out (these are infrastructure models, not wake word models)
-  **ONNX format preferred**: ONNX format is preferred over TFLite. On Linux x86_64, ONNX is required (TFLite runtime unavailable)
-  **Format deduplication**: When both `.onnx` and `.tflite` versions of the same model exist, only the ONNX version is used
-  **Filtering applies universally**: Both user-provided paths and auto-discovered models are filtered using the same logic

**Why filtering is needed**:

The `openwakeword.utils.download_models()` function downloads all model files including infrastructure models. Passing these infrastructure models to `WakeWordModel()` causes TensorFlow Lite errors. The automatic filtering ensures only compatible wake word models are loaded, preventing initialization failures.

### Early Detection Integration

For early wake detection in audio frame processing loops:

```python
# In AudioProcessorWrapper.register_frame_async()
if self._wake_detector and self._wake_detector._model:
    # Check every 5 frames after minimum threshold
    if frame_count >= 10 and frame_count % 5 == 0:
        accumulated_pcm = b"".join(f.pcm for f in accumulator.frames)
        wake_result = self._wake_detector.detect_audio(
            accumulated_pcm, accumulator.sample_rate
        )
        if wake_result and total_duration >= min_segment_duration:
            # Early flush on wake detection
            return segment
```

### Configuration

Wake detection is configured via environment variables:

- `WAKE_MODEL_PATHS`: Comma-separated list of model file paths (default: empty = auto-discover)
- `WAKE_THRESHOLD`: Activation threshold 0.0-1.0 (default: 0.5)
- `WAKE_SAMPLE_RATE`: Target sample rate in Hz (default: 16000)
- `WAKE_DETECTION_ENABLED`: Enable/disable wake detection (default: true)
- `WAKE_INFERENCE_FRAMEWORK`: Inference framework to use - 'onnx' (default, required on Linux) or 'tflite' (default: "onnx")

## Migration from Current Approach

The new configuration library replaces the current manual environment variable parsing approach used across services. See the [Configuration Library Reference](../docs/reference/configuration-library.md) for detailed migration instructions.

### Benefits of Migration

-  **Reduced Code**: Eliminate 100+ lines of manual parsing per service
-  **Type Safety**: Catch configuration errors at startup
-  **Consistency**: Unified configuration patterns across all services
-  **Maintainability**: Easy to add new configuration fields
-  **Documentation**: Self-documenting configuration with descriptions
-  **Validation**: Comprehensive validation with clear error messages
-  **Testing**: Easy to test configuration loading and validation
