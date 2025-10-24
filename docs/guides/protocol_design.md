---
title: Protocol Design Guide
last-updated: 2025-01-27
---

# Protocol Design Guide

## Overview

This guide explains how to design and use protocols in the audio-orchestrator project. Protocols enable structural subtyping and composition over inheritance, creating more flexible and testable code.

## Protocol Design Principles

### 1. Single Responsibility

Each protocol should have a single, well-defined responsibility:

```python
# Good: Focused protocol
class AudioCaptureProtocol(Protocol):
    """Protocol for audio capture operations."""
    async def start_capture(self) -> None: ...
    async def stop_capture(self) -> None: ...
    async def read_audio_frame(self) -> PCMFrame | None: ...

# Bad: Too many responsibilities
class AudioProtocol(Protocol):
    """Protocol for all audio operations."""
    async def start_capture(self) -> None: ...
    async def stop_capture(self) -> None: ...
    async def play_audio(self) -> None: ...
    async def set_volume(self) -> None: ...
    async def get_metadata(self) -> AudioMetadata: ...
```

### 2. Composition over Inheritance

Design protocols to be composable:

```python
# Multiple focused protocols
class AudioCaptureProtocol(Protocol): ...
class AudioPlaybackProtocol(Protocol): ...
class AudioMetadataProtocol(Protocol): ...

# Compose them in implementations
class AudioAdapter:
    def __init__(self):
        self._capture: AudioCaptureProtocol
        self._playback: AudioPlaybackProtocol
        self._metadata: AudioMetadataProtocol
```

### 3. Runtime Checkable When Needed

Use `@runtime_checkable` for protocols that need runtime validation:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class LifecycleProtocol(Protocol):
    """Protocol for lifecycle management."""
    async def initialize(self) -> None: ...
    async def cleanup(self) -> None: ...

# Can use isinstance() checks
def validate_lifecycle(obj: Any) -> bool:
    return isinstance(obj, LifecycleProtocol)
```

## Protocol Patterns

### 1. Service Protocols

For service communication:

```python
class ServiceDiscoveryProtocol(Protocol):
    """Protocol for service discovery."""
    async def discover_services(self) -> list[dict[str, Any]]: ...
    async def register_service(self, info: dict[str, Any]) -> None: ...

class ServiceCommunicationProtocol(Protocol):
    """Protocol for inter-service communication."""
    async def send_request(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]: ...
    async def stream_data(self, endpoint: str) -> AsyncIterator[dict[str, Any]]: ...
```

### 2. Configuration Protocols

For configuration management:

```python
class ConfigurationSourceProtocol(Protocol):
    """Protocol for configuration sources."""
    def load(self) -> dict[str, Any]: ...
    def save(self, config: dict[str, Any]) -> None: ...
    def validate(self) -> bool: ...

class ConfigurationValidatorProtocol(Protocol):
    """Protocol for configuration validation."""
    def validate(self, config: dict[str, Any]) -> list[str]: ...
    def get_schema(self) -> dict[str, Any]: ...
```

### 3. Processing Protocols

For data processing:

```python
class STTProcessingProtocol(Protocol):
    """Protocol for STT processing."""
    async def transcribe(
        self,
        audio_data: bytes,
        audio_format: AudioFormat,
        metadata: AudioMetadata | None = None,
    ) -> STTResult: ...

    def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        audio_format: AudioFormat,
        metadata: AudioMetadata | None = None,
    ) -> AsyncGenerator[STTResult, None]: ...
```

## Implementation Guidelines

### 1. Default Implementations

Provide default implementations for common functionality:

```python
class DefaultAudioCaptureAdapter:
    """Default implementation of audio capture protocols."""
    
    def __init__(self, config: AudioConfig) -> None:
        self.config = config
        self._is_capturing = False
    
    async def start_capture(self) -> None:
        """Start capturing audio."""
        self._is_capturing = True
        # Default implementation - override in subclasses
    
    async def stop_capture(self) -> None:
        """Stop capturing audio."""
        self._is_capturing = False
        # Default implementation - override in subclasses
    
    async def read_audio_frame(self) -> PCMFrame | None:
        """Read audio frame."""
        # Default implementation - override in subclasses
        return None
```

### 2. Backward Compatibility

Maintain backward compatibility with aliases:

```python
# New protocol-based approach
class AudioCaptureProtocol(Protocol): ...

# Backward compatibility alias
AudioSource = AudioCaptureProtocol
```

### 3. Type Hints

Use proper type hints in protocols:

```python
from typing import Protocol, Any
from collections.abc import AsyncIterator

class AudioProcessingProtocol(Protocol):
    """Protocol for audio processing."""
    
    async def process_audio(
        self, 
        audio_data: bytes, 
        format: AudioFormat
    ) -> AudioResult: ...
    
    def get_audio_stream(
        self, 
        source: str
    ) -> AsyncIterator[AudioChunk]: ...
```

## Testing Protocols

### 1. Protocol Compliance Testing

```python
from services.tests.utils.protocol_testing import assert_implements_protocol

def test_audio_adapter_compliance():
    """Test that audio adapter implements required protocols."""
    adapter = AudioAdapter()
    assert_implements_protocol(adapter, AudioCaptureProtocol)
    assert_implements_protocol(adapter, AudioPlaybackProtocol)
```

### 2. Protocol Mocking

```python
from services.tests.utils.protocol_testing import create_protocol_mock

def test_service_with_mock():
    """Test service with protocol mock."""
    mock_capture = create_protocol_mock(AudioCaptureProtocol)
    service = AudioService(capture=mock_capture)
    # Test service behavior
```

### 3. Protocol Validation

```python
from services.tests.utils.protocol_testing import validate_protocol_compliance

def test_protocol_validation():
    """Test protocol validation."""
    adapter = AudioAdapter()
    result = validate_protocol_compliance(adapter, AudioCaptureProtocol)
    assert result["compliant"]
    assert len(result["missing_methods"]) == 0
```

## Hot-Swapping with Protocols

### 1. Dynamic Protocol Implementation

```python
class HotSwappableService:
    """Service that supports hot-swapping of components."""
    
    def __init__(self):
        self._processor: AudioProcessingProtocol | None = None
    
    def set_processor(self, processor: AudioProcessingProtocol) -> None:
        """Set audio processor (hot-swap)."""
        self._processor = processor
    
    async def process_audio(self, data: bytes) -> AudioResult:
        """Process audio using current processor."""
        if self._processor is None:
            raise RuntimeError("No processor set")
        return await self._processor.process_audio(data, AudioFormat.WAV)
```

### 2. Protocol-Based Factory

```python
class ProtocolFactory:
    """Factory for creating protocol implementations."""
    
    _implementations: dict[str, type] = {}
    
    @classmethod
    def register(cls, name: str, implementation: type) -> None:
        """Register protocol implementation."""
        cls._implementations[name] = implementation
    
    @classmethod
    def create(cls, name: str, *args, **kwargs) -> Any:
        """Create protocol implementation."""
        if name not in cls._implementations:
            raise ValueError(f"Unknown implementation: {name}")
        return cls._implementations[name](*args, **kwargs)

# Usage
ProtocolFactory.register("default", DefaultAudioProcessor)
ProtocolFactory.register("advanced", AdvancedAudioProcessor)

processor = ProtocolFactory.create("default", config)
```

## Migration from ABCs

### 1. Before (ABC-based)

```python
from abc import ABC, abstractmethod

class AudioSource(ABC):
    @abstractmethod
    async def start_capture(self) -> None: ...
    
    @abstractmethod
    async def stop_capture(self) -> None: ...
```

### 2. After (Protocol-based)

```python
from typing import Protocol

class AudioCaptureProtocol(Protocol):
    async def start_capture(self) -> None: ...
    async def stop_capture(self) -> None: ...
```

### 3. Implementation Changes

```python
# Before
class DiscordAudioSource(AudioSource):
    async def start_capture(self) -> None:
        # Implementation
        pass

# After
class DiscordAudioSource:
    async def start_capture(self) -> None:
        # Implementation
        pass

# Type checking ensures protocol compliance
def use_audio_source(source: AudioCaptureProtocol) -> None:
    # Works with any object implementing the protocol
    pass
```

## Best Practices

1.  **Keep protocols focused** - One responsibility per protocol
2.  **Use composition** - Combine multiple protocols in implementations
3.  **Provide default implementations** - Make protocols easy to implement
4.  **Use runtime_checkable sparingly** - Only when runtime validation is needed
5.  **Maintain backward compatibility** - Use aliases during migration
6.  **Test protocol compliance** - Ensure implementations follow protocols
7.  **Document protocol contracts** - Clear expectations for implementers

## Common Pitfalls

1.  **Over-engineering** - Don't create protocols for everything
2.  **Too many protocols** - Balance granularity with usability
3.  **Missing type hints** - Always include proper type annotations
4.  **Ignoring runtime_checkable** - Use when runtime validation is needed
5.  **Breaking changes** - Maintain compatibility during migration

This guide provides the foundation for using protocols effectively in the audio-orchestrator project, enabling more flexible and maintainable code through structural subtyping.
