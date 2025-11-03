---
title: Shared Utilities
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-18
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Architecture ▸ Shared Utilities

# Shared Utilities

The `services/common/` package provides shared utilities and libraries used across all Python services in the audio-orchestrator project.

## Overview

The shared utilities package addresses common needs across services while maintaining consistency and reducing code duplication. All utilities are designed to work seamlessly with the new configuration management system.

## Core Modules

### Audio Processing (`audio.py`)

Standardized audio processing library providing:

-  **Format Conversion**: PCM ↔ WAV conversion with proper headers
-  **Resampling**: High-quality sample rate conversion (48kHz → 16kHz)
-  **Normalization**: RMS-based audio level adjustment
-  **Metadata Extraction**: Consistent audio property detection
-  **Service Defaults**: Optimized parameters for each service

**Service-Specific Audio Parameters**:

-  **Discord**: 48kHz, mono, 16-bit PCM
-  **STT**: 16kHz, mono, 16-bit WAV
-  **TTS**: 22.05kHz, mono, 16-bit WAV
-  **Orchestrator**: 22.05kHz, mono, 16-bit WAV

### Correlation IDs (`correlation.py`)

Unified correlation ID generation system providing:

-  **End-to-End Tracing**: Complete visibility through the voice pipeline
-  **Service Identification**: Easy identification of originating service
-  **Hierarchical Organization**: Natural grouping in debug directories
-  **Timestamp Tracking**: Chronological ordering of operations

**Correlation ID Formats**:

-  **Discord**: `discord-{user_id}-{guild_id}-{timestamp_ms}`
-  **STT**: `stt-{source_id}` or `stt-{timestamp_ms}`
-  **TTS**: `tts-{source_id}` or `tts-{timestamp_ms}`
-  **Orchestrator**: `orchestrator-{source_id}` or `orchestrator-{user_id}-{timestamp_ms}`
-  **Manual**: `manual-{service}-{context}-{timestamp_ms}`

### Debug Management

Debug management utilities are available through individual service implementations. The shared utilities focus on core functionality rather than debug-specific features.

### Configuration Library (`config.py`, `service_configs.py`)

Type-safe configuration management system:

-  **Type Safety**: Full type hints and validation for all configuration values
-  **Consistency**: Unified patterns across all services
-  **Validation**: Comprehensive input validation with clear error messages
-  **Flexibility**: Support for different configuration sources (env vars, files, defaults)
-  **Extensibility**: Easy to add new configuration sections
-  **Documentation**: Self-documenting configuration with descriptions
-  **Environment Awareness**: Support for different environments (dev, prod, test, docker)

### Logging (`logging.py`)

Structured logging utilities:

-  **JSON Output**: Consistent structured logging across all services
-  **Service Identification**: Automatic service name tagging
-  **Correlation Tracking**: Built-in correlation ID propagation
-  **Configurable Verbosity**: Environment-controlled log levels
-  **Context Preservation**: Rich metadata in all log entries

### HTTP Utilities (`http_client.py`, `resilient_http.py`, `http_client_factory.py`, `optimized_http.py`)

HTTP client management and utilities:

-  **Unified Resilience Pattern**: All service-to-service HTTP calls use `ResilientHTTPClient` with circuit breaker protection
-  **Circuit Breaker**: Automatic protection against cascading failures with configurable thresholds
-  **Health Checks**: Proactive health monitoring with startup grace period
-  **Connection Pooling**: Efficient connection reuse with configurable limits
-  **Consistent Timeouts**: Standardized timeout configurations
-  **Retry Logic**: Configurable retry behavior for resilience
-  **Authentication**: Bearer token and API key management
-  **Error Handling**: Comprehensive error response processing with service-specific degradation strategies
-  **Automatic Correlation ID Propagation**: All HTTP clients automatically inject correlation IDs from context
-  **Environment-Based Configuration**: Factory function loads configuration from environment variables with sensible defaults

**ResilientHTTPClient Features**:

-  **Circuit Breaker Protection**: Opens circuit after failure threshold, recovers with success threshold
-  **Health Check Integration**: Checks service health before requests, with configurable intervals
-  **Startup Grace Period**: Allows services time to start before health checks fail requests
-  **Connection Pooling**: Reuses connections with configurable max_connections and max_keepalive_connections
-  **HTTP Methods**: Supports GET, POST, PUT, DELETE with circuit breaker protection
-  **ServiceUnavailableError**: Raises specific exception when circuit is open or service is unhealthy

**Factory Pattern**:

```python
from services.common.http_client_factory import create_resilient_client

# Create resilient client with environment-based configuration
client = create_resilient_client(
    service_name="orchestrator",
    base_url="http://orchestrator:8200",
    env_prefix="ORCHESTRATOR",  # Optional: defaults to service_name.upper()
)
```

**Configuration Variables** (per-service prefix pattern):

-  `{PREFIX}_BASE_URL`: Service base URL
-  `{PREFIX}_CIRCUIT_FAILURE_THRESHOLD`: Failures before opening circuit (default: 5)
-  `{PREFIX}_CIRCUIT_SUCCESS_THRESHOLD`: Successes to close from half-open (default: 2)
-  `{PREFIX}_CIRCUIT_TIMEOUT_SECONDS`: Base timeout for circuit recovery (default: 30.0)
-  `{PREFIX}_TIMEOUT_SECONDS`: Request timeout in seconds (default: 30.0)
-  `{PREFIX}_HEALTH_CHECK_INTERVAL`: Seconds between health checks (default: 10.0)
-  `{PREFIX}_HEALTH_CHECK_STARTUP_GRACE_SECONDS`: Grace period during startup (default: 30.0)
-  `{PREFIX}_MAX_CONNECTIONS`: Max concurrent connections (default: 10)
-  `{PREFIX}_MAX_KEEPALIVE_CONNECTIONS`: Max persistent connections (default: 5)

**Service-Specific Error Handling**:

-  **Audio Processor Clients**: Return original data/None on failure (graceful degradation)
-  **Orchestrator Client**: Return error dict with graceful message
-  **Guardrails**: Fallback to unsanitized input when unavailable
-  **Testing Service**: Return error messages in response model

### HTTP Headers (`http_headers.py`)

Shared utilities for HTTP header propagation:

-  **Correlation ID Injection**: `inject_correlation_id()` automatically adds correlation IDs to HTTP requests
-  **Context-Aware**: Reads correlation IDs from async context (set by `ObservabilityMiddleware`)
-  **Non-Breaking**: Only injects if correlation ID not already present in headers
-  **Single Source of Truth**: Ensures consistent correlation ID propagation across all HTTP clients

### Observability Middleware (`middleware.py`)

Unified FastAPI middleware for observability:

-  **Correlation ID Management**: Extracts from headers, generates if missing, stores in context
-  **Request/Response Logging**: Automatic logging of all HTTP requests with timing
-  **Health Check Filtering**: Excludes verbose logging for health endpoints
-  **Error Logging**: Automatic error logging with timing and correlation IDs

### Service Factory (`app_factory.py`)

Standardized FastAPI app creation factory:

-  **Automatic Observability Setup**: Configures OpenTelemetry instrumentation before app starts
-  **Automatic Middleware Registration**: Adds `ObservabilityMiddleware` automatically
-  **Standardized Lifespan**: Provides consistent startup/shutdown pattern
-  **Service Callbacks**: Supports service-specific startup/shutdown logic
-  **Code Reduction**: Eliminates ~80% of boilerplate code per service

### Surface Architecture (`surfaces/`)

Composable surface architecture for voice assistant integration:

-  **Core Interfaces**: AudioSource, AudioSink, ControlChannel, SurfaceLifecycle
-  **Discord Adapters**: Specialized implementations for Discord voice integration
-  **Registry System**: Surface registration and management
-  **Media Gateway**: Audio routing and processing
-  **Event System**: Comprehensive event handling for surface interactions

**Key Components**:

-  **AudioSource**: Captures audio from surfaces in standardized PCM format
-  **AudioSink**: Plays audio to surfaces with format conversion
-  **ControlChannel**: Handles surface-specific control events and user interactions
-  **SurfaceLifecycle**: Manages surface connection lifecycle and health monitoring

**Current Implementation**: Discord service uses specialized adapters (DiscordAudioSource, DiscordAudioSink, DiscordControlChannel, DiscordSurfaceLifecycle) that implement the core interfaces.

**Future Extensions**: Multi-surface sessions, surface switching, load balancing, and failover capabilities are planned for future releases.

**Related Documentation**:

-  [Surface Architecture Reference](../reference/surface-architecture.md) - Current implementation details
-  [Multi-Surface Architecture Proposal](../proposals/multi-surface-architecture.md) - Future extensions and advanced features

## Usage Patterns

### Configuration Loading

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
```

### Audio Processing

```python
from services.common.audio import AudioProcessor

# Process audio with service-specific defaults
processor = AudioProcessor.for_service("stt")
processed_audio = processor.convert_to_wav(raw_pcm_data)
```

### Correlation IDs

```python
from services.common.correlation import generate_correlation_id

# Generate correlation ID for Discord service
correlation_id = generate_correlation_id("discord", user_id="123", guild_id="456")
```

### Debug Management

Debug management is handled by individual services using their own debug utilities and logging systems.

## Integration with Services

All services use these shared utilities through the common configuration system:

-  **Discord Service**: Audio processing, correlation IDs, debug management
-  **STT Service**: Audio processing, correlation IDs, debug management
-  **LLM Service**: Configuration management, logging, HTTP utilities
-  **Orchestrator Service**: Configuration management, correlation IDs, debug management
-  **TTS Service**: Audio processing, correlation IDs, debug management

### PyTorch Optimization Utilities (`torch_compile.py`, `prewarm.py`, `result_cache.py`)

Shared utilities for optimizing PyTorch model performance across all services:

-  **torch.compile() Integration**: Centralized PyTorch model compilation with consistent error handling and Docker compatibility
-  **Pre-warming**: Generic pattern for triggering torch.compile() warmup during startup to prevent first-request timeouts
-  **Result Caching**: Generic LRU cache for service results (transcripts, generations, classifications)

**Usage Pattern**:

```python
from services.common.torch_compile import compile_model_if_enabled
from services.common.prewarm import prewarm_if_enabled
from services.common.result_cache import ResultCache, generate_cache_key

# Compile model if enabled
model = AutoModelForSeq2SeqLM.from_pretrained(...)
model = compile_model_if_enabled(model, "flan", "flan_t5", logger)

# Pre-warm during startup
async def _prewarm():
    model.generate(...)

await prewarm_if_enabled(_prewarm, "flan", logger, model_loader=_model_loader)

# Cache results
cache = ResultCache(max_entries=200, max_size_mb=1000, service_name="stt")
cache_key = generate_cache_key(audio_bytes)
cached = cache.get(cache_key)
if not cached:
    result = perform_inference(...)
    cache.put(cache_key, result)
```

**Configuration**: All optimizations controlled via `{SERVICE}_ENABLE_{FEATURE}` environment variables.

## Documentation

For detailed usage examples and API reference, see the [services/common/README.md](../../services/common/README.md).

## Maintenance

The shared utilities are maintained as part of the core project and follow the same development lifecycle as the services that use them. Changes to shared utilities should be coordinated across all affected services to ensure compatibility.
