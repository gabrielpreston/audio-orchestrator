---
title: Surface Architecture Reference
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-18
---

# Surface Architecture Reference

## Overview

This document describes the current implementation of the Composable Surface Architecture in the Discord Voice Lab project.
The architecture provides a flexible, extensible framework for voice assistant integration across multiple platforms through standardized interfaces.

## Core Interfaces

The architecture is built around four core interfaces that define the contract for surface adapters:

### AudioSource Interface

```python
class AudioSource(ABC):
    """Abstract base class for audio input adapters."""
    
    @abstractmethod
    async def read_audio_frame(self) -> List[PCMFrame]:
        """Read audio frames from the source."""
    
    @abstractmethod
    async def get_telemetry(self) -> Dict[str, Any]:
        """Get telemetry data."""
```

**Responsibilities:**

- Capture audio from the surface
- Provide audio frames in standardized PCM format
- Handle audio quality and format conversion
- Report audio capture metrics

### AudioSink Interface

```python
class AudioSink(ABC):
    """Abstract base class for audio output adapters."""
    
    @abstractmethod
    async def play_audio_chunk(self, frame: PCMFrame) -> None:
        """Play audio frame."""
    
    @abstractmethod
    async def get_telemetry(self) -> Dict[str, Any]:
        """Get telemetry data."""
```

**Responsibilities:**

- Play audio to the surface
- Handle audio format conversion
- Manage audio playback timing and synchronization
- Report playback metrics

### ControlChannel Interface

```python
class ControlChannel(ABC):
    """Abstract base class for control channel adapters."""
    
    @abstractmethod
    async def send_event(self, event: BaseEvent) -> None:
        """Send control event."""
    
    @abstractmethod
    async def receive_event(self) -> Optional[BaseEvent]:
        """Receive control event."""
    
    @abstractmethod
    async def get_telemetry(self) -> Dict[str, Any]:
        """Get telemetry data."""
```

**Responsibilities:**

- Handle surface-specific control events
- Manage user interactions (wake words, button presses, etc.)
- Route events between surface and voice pipeline
- Provide surface state information

### SurfaceLifecycle Interface

```python
class SurfaceLifecycle(ABC):
    """Abstract base class for surface lifecycle management."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the surface."""
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from the surface."""
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check connection status."""
    
    @abstractmethod
    async def get_telemetry(self) -> Dict[str, Any]:
        """Get telemetry data."""
```

**Responsibilities:**

- Manage surface connection lifecycle
- Handle authentication and permissions
- Monitor connection health
- Provide connection metrics

## Data Types

### PCMFrame

```python
@dataclass
class PCMFrame:
    """PCM audio frame."""
    pcm: bytes
    rms: float
    duration: float
    sequence: int
    sample_rate: int
```

**Purpose:** Standardized audio frame format for consistent processing across all surfaces.

### AudioFormat

```python
@dataclass
class AudioFormat:
    """Audio format specification."""
    value: Dict[str, Any]
```

**Purpose:** Describes audio format requirements and capabilities.

## Event System

The architecture uses a comprehensive event system for communication:

- **WakeDetectedEvent**: Wake word detection
- **VADStartSpeechEvent**: Voice activity detection start
- **VADEndSpeechEvent**: Voice activity detection end
- **BargeInRequestEvent**: User interruption request
- **SessionStateEvent**: Session state changes
- **RouteChangeEvent**: Audio routing changes
- **PlaybackControlEvent**: Playback control commands
- **EndpointingEvent**: Speech endpointing
- **TranscriptPartialEvent**: Partial transcript updates
- **TranscriptFinalEvent**: Final transcript results
- **ErrorEvent**: Error reporting

## Discord Implementation

The Discord service implements the Composable Surface Architecture through specialized adapters:

### DiscordAudioSource

Implements the `AudioSource` interface for Discord voice capture, handling:

- Discord voice channel audio capture
- Audio format conversion to PCM
- Voice activity detection integration
- Audio quality metrics

### DiscordAudioSink

Implements the `AudioSink` interface for Discord audio playback, handling:

- Discord voice channel audio playback
- Audio format conversion from PCM
- Playback timing and synchronization
- Playback quality metrics

### DiscordControlChannel

Implements the `ControlChannel` interface for Discord control events, handling:

- Discord message events
- Voice state changes
- User interaction events
- MCP tool integration

### DiscordSurfaceLifecycle

Implements the `SurfaceLifecycle` interface for Discord connection management, handling:

- Discord bot connection lifecycle
- Authentication and permissions
- Connection health monitoring
- Session management

## Registry System

The surface registry manages available surface adapters and their configurations:

```python
# Register a new surface
registry = SurfaceRegistry()
registry.register_surface("discord", DiscordSurfaceAdapter())
```

## Media Gateway

The media gateway handles audio routing and processing between surfaces and the voice pipeline:

- Audio frame routing
- Format conversion
- Quality monitoring
- Performance metrics

## Configuration

The Composable Surface Architecture interfaces are implemented in `services/common/surfaces/interfaces.py` and are used by the Discord service through the `DiscordAudioSource` and `DiscordAudioSink` adapters.

These interfaces are not controlled by environment variables but are implemented as part of the service architecture.

**Note**: This document describes the interface specifications for the Composable Surface Architecture. The actual implementation is integrated into the Discord service without requiring special environment variables.

## Error Handling

### Standardized Error Types

- **ConnectionError**: Surface connection failures
- **AuthenticationError**: Authentication/authorization failures
- **AudioError**: Audio processing errors
- **ControlError**: Control channel errors
- **LifecycleError**: Lifecycle management errors

### Error Recovery Patterns

```python
try:
    await surface_lifecycle.connect()
except ConnectionError as e:
    logger.error("Connection failed: %s", e)
    await surface_lifecycle.reconnect()
```

## Performance Requirements

### Latency Targets

- **Audio Capture**: < 50ms end-to-end latency
- **Audio Playback**: < 50ms end-to-end latency
- **Event Processing**: < 10ms processing time
- **Connection Establishment**: < 1000ms connection time
- **Health Checks**: < 100ms response time

### Throughput Requirements

- **Audio Processing**: Support for 16kHz, 1-channel audio
- **Event Handling**: 100+ events per second
- **Concurrent Sessions**: Multiple simultaneous surface connections

## Testing Requirements

### Contract Testing

All surface adapters must pass contract tests that validate:

- Interface compliance
- Performance requirements
- Error handling behavior
- Lifecycle management

### Parity Testing

Cross-surface parity tests ensure:

- Consistent performance across surface types
- Uniform behavior patterns
- Comparable latency characteristics

### Chaos Testing

Reliability testing includes:

- Network fault injection
- Memory pressure testing
- Rapid connect/disconnect cycles
- Concurrent operation stress tests

## Implementation Files

- **Core Interfaces**: `services/common/surfaces/interfaces.py`
- **Discord Adapters**: `services/discord/adapters/`
- **Registry System**: `services/common/surfaces/registry.py`
- **Media Gateway**: `services/common/surfaces/gateway.py`
- **Event System**: `services/common/surfaces/events.py`

## Related Documentation

- [Shared Utilities](../architecture/shared-utilities.md) - Overview of shared utilities including surface architecture
- [Multi-Surface Architecture Proposal](../proposals/multi-surface-architecture.md) - Future extensions and advanced features
