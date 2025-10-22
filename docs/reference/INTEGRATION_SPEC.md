---
last-updated: 2025-10-16
---

# Composable Surface Architecture - Integration Specification

## Overview

The Composable Surface Architecture provides a flexible, extensible framework for voice assistant integration across multiple platforms. This specification defines the interfaces, protocols, and integration patterns for implementing surface adapters.

## Architecture Principles

### 1. **Composability**

-  Surface adapters are composed of four independent components: AudioSource, AudioSink, ControlChannel, and SurfaceLifecycle
-  Each component can be implemented independently and swapped without affecting others
-  Components communicate through well-defined interfaces

### 2. **Extensibility**

-  New surface types can be added by implementing the four core interfaces
-  Existing surfaces can be enhanced without breaking changes
-  Plugin architecture supports third-party surface implementations

### 3. **Consistency**

-  All surfaces provide consistent behavior through standardized interfaces
-  Common patterns for error handling, configuration, and lifecycle management
-  Unified event system across all surface types

## Core Interfaces

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

-  Capture audio from the surface
-  Provide audio frames in standardized PCM format
-  Handle audio quality and format conversion
-  Report audio capture metrics

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

-  Play audio to the surface
-  Handle audio format conversion
-  Manage audio playback timing and synchronization
-  Report playback metrics

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

-  Handle surface-specific control events
-  Manage user interactions (wake words, button presses, etc.)
-  Route events between surface and voice pipeline
-  Provide surface state information

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

-  Manage surface connection lifecycle
-  Handle authentication and permissions
-  Monitor connection health
-  Provide connection metrics

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

### Event System

The architecture uses a comprehensive event system for communication:

-  **WakeDetectedEvent**: Wake word detection
-  **VADStartSpeechEvent**: Voice activity detection start
-  **VADEndSpeechEvent**: Voice activity detection end
-  **BargeInRequestEvent**: User interruption request
-  **SessionStateEvent**: Session state changes
-  **RouteChangeEvent**: Audio routing changes
-  **PlaybackControlEvent**: Playback control commands
-  **EndpointingEvent**: Speech endpointing
-  **TranscriptPartialEvent**: Partial transcript updates
-  **TranscriptFinalEvent**: Final transcript results
-  **ErrorEvent**: Error reporting

## Integration Patterns

### 1. **Surface Registration**

```python
# Register a new surface
registry = SurfaceRegistry()
registry.register_surface("discord", DiscordSurfaceAdapter())
registry.register_surface("webrtc", WebRTCSurfaceAdapter())
```

### 2. **Adapter Composition**

```python
# Compose surface adapters
surface = SurfaceAdapter(
    audio_source=DiscordAudioSource(),
    audio_sink=DiscordAudioSink(),
    control_channel=DiscordControlChannel(),
    surface_lifecycle=DiscordSurfaceLifecycle()
)
```

### 3. **Event Routing**

```python
# Route events between components
control_channel.register_event_handler("wake_detected", handle_wake_word)
audio_source.register_frame_handler(process_audio_frame)
```

### 4. **Lifecycle Management**

```python
# Manage surface lifecycle
await surface_lifecycle.connect()
await audio_source.initialize()
await audio_sink.initialize()
await control_channel.initialize()
```

## Configuration

### Environment Variables

```bash
# Surface configuration
SURFACE_TYPE=discord
SURFACE_ID=voice_channel_123
SURFACE_CONFIG_PATH=/config/surfaces/

# Audio configuration
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
AUDIO_BIT_DEPTH=16

# Performance configuration
AUDIO_BUFFER_SIZE=1024
AUDIO_LATENCY_TARGET_MS=50
```

### Surface Configuration

```yaml
surfaces:
  discord:
    type: discord
    guild_id: "123456789"
    channel_id: "987654321"
    audio:
      sample_rate: 16000
      channels: 1
      bit_depth: 16
    control:
      wake_words: ["hey assistant", "ok assistant"]
      barge_in_enabled: true
    lifecycle:
      auto_reconnect: true
      health_check_interval: 30
```

## Error Handling

### Standardized Error Types

-  **ConnectionError**: Surface connection failures
-  **AuthenticationError**: Authentication/authorization failures
-  **AudioError**: Audio processing errors
-  **ControlError**: Control channel errors
-  **LifecycleError**: Lifecycle management errors

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

-  **Audio Capture**: < 50ms end-to-end latency
-  **Audio Playback**: < 50ms end-to-end latency
-  **Event Processing**: < 10ms processing time
-  **Connection Establishment**: < 1000ms connection time
-  **Health Checks**: < 100ms response time

### Throughput Requirements

-  **Audio Processing**: Support for 16kHz, 1-channel audio
-  **Event Handling**: 100+ events per second
-  **Concurrent Sessions**: Multiple simultaneous surface connections

## Testing Requirements

### Contract Testing

All surface adapters must pass contract tests that validate:

-  Interface compliance
-  Performance requirements
-  Error handling behavior
-  Lifecycle management

### Parity Testing

Cross-surface parity tests ensure:

-  Consistent performance across surface types
-  Uniform behavior patterns
-  Comparable latency characteristics

### Chaos Testing

Reliability testing includes:

-  Network fault injection
-  Memory pressure testing
-  Rapid connect/disconnect cycles
-  Concurrent operation stress tests

## Migration Guide

### From Monolithic to Composable

-  **Identify Surface Components**: Break down existing surface code into the four core interfaces
-  **Implement Adapters**: Create adapter classes for each interface
-  **Update Integration**: Replace direct surface calls with adapter calls
-  **Test Migration**: Run contract and parity tests to validate migration

### Backward Compatibility

-  Existing surface implementations continue to work
-  Gradual migration path with feature flags
-  Compatibility layer for legacy interfaces

## Security Considerations

### Authentication

-  Surface-specific authentication mechanisms
-  Token-based authentication for API surfaces
-  Certificate-based authentication for secure connections

### Data Privacy

-  Audio data encryption in transit
-  No persistent audio storage
-  Secure event transmission

### Access Control

-  Surface-level permissions
-  User-based access control
-  Session-based authorization

## Monitoring and Observability

### Health Monitoring

-  Connection status monitoring
-  Performance metrics collection
-  Error rate tracking
-  Latency monitoring

### Debugging Support

-  Detailed logging with correlation IDs
-  Event tracing across components
-  Performance profiling
-  Error diagnostics

## Future Extensions

### Planned Surface Types

-  **WebRTC/LiveKit**: Real-time communication surfaces
-  **Mobile SDK**: Native mobile app integration
-  **IoT Devices**: Smart home device integration
-  **Telephony**: Phone system integration

### Advanced Features

-  **Multi-Surface Sessions**: Simultaneous multiple surface connections
-  **Surface Switching**: Dynamic surface switching during sessions
-  **Load Balancing**: Distribution across multiple surface instances
-  **Failover**: Automatic failover between surface instances

## Implementation Checklist

### For New Surface Implementations

-  [ ] Implement all four core interfaces
-  [ ] Add comprehensive error handling
-  [ ] Include performance optimizations
-  [ ] Write contract tests
-  [ ] Add parity test coverage
-  [ ] Document surface-specific configuration
-  [ ] Implement security measures
-  [ ] Add monitoring and logging

### For Integration

-  [ ] Register surface in surface registry
-  [ ] Configure environment variables
-  [ ] Set up event routing
-  [ ] Implement lifecycle management
-  [ ] Add health monitoring
-  [ ] Test end-to-end functionality
-  [ ] Validate performance requirements
-  [ ] Document integration steps
