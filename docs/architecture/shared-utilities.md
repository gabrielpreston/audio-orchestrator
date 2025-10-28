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

### HTTP Utilities (`http.py`)

HTTP client management and utilities:

-  **Consistent Timeouts**: Standardized timeout configurations
-  **Retry Logic**: Configurable retry behavior for resilience
-  **Authentication**: Bearer token and API key management
-  **Error Handling**: Comprehensive error response processing
-  **Connection Pooling**: Efficient connection reuse

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

## Documentation

For detailed usage examples and API reference, see the [services/common/README.md](../../services/common/README.md).

## Maintenance

The shared utilities are maintained as part of the core project and follow the same development lifecycle as the services that use them. Changes to shared utilities should be coordinated across all affected services to ensure compatibility.
