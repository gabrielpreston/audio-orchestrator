---
title: Audio Adapter Types Reference
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-22
---

# Audio Adapter Types Reference

## Overview

This document provides a complete reference for all audio adapter types and interfaces used in the audio orchestrator platform.

## Base Interfaces

### AudioInputAdapter

Abstract base class for audio input adapters.

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator
from services.orchestrator.adapters.types import AudioChunk

class AudioInputAdapter(ABC):
    """Abstract base class for audio input adapters."""
    
    @abstractmethod
    async def start_capture(self) -> None:
        """Start capturing audio from the source."""
        pass
    
    @abstractmethod
    async def stop_capture(self) -> None:
        """Stop capturing audio."""
        pass
    
    @abstractmethod
    async def get_audio_stream(self) -> AsyncIterator[AudioChunk]:
        """Get async generator of audio chunks."""
        pass
    
    @abstractmethod
    @property
    def is_active(self) -> bool:
        """Check if capture is currently active."""
        pass
```

### AudioOutputAdapter

Abstract base class for audio output adapters.

```python
from abc import ABC, abstractmethod
from services.orchestrator.adapters.types import AudioChunk

class AudioOutputAdapter(ABC):
    """Abstract base class for audio output adapters."""
    
    @abstractmethod
    async def play_audio(self, audio_chunk: AudioChunk) -> None:
        """Play audio chunk to the destination."""
        pass
    
    @abstractmethod
    async def stop_playback(self) -> None:
        """Stop audio playback."""
        pass
    
    @abstractmethod
    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        pass
```

## Data Types

### AudioChunk

Represents a chunk of audio data with metadata.

```python
from dataclasses import dataclass
from services.orchestrator.adapters.types import AudioMetadata

@dataclass
class AudioChunk:
    """Audio chunk with metadata and correlation information."""
    
    data: bytes                    # Raw audio data (PCM)
    metadata: AudioMetadata        # Audio format information
    correlation_id: str           # Correlation ID for tracing
    sequence_number: int          # Sequence number in stream
    is_silence: bool             # Whether this chunk contains silence
    volume_level: float          # Volume level (0.0 to 1.0)
```

### AudioMetadata

Contains audio format and quality information.

```python
from dataclasses import dataclass

@dataclass
class AudioMetadata:
    """Audio format and quality metadata."""
    
    sample_rate: int             # Sample rate in Hz (e.g., 44100)
    channels: int                # Number of channels (1=mono, 2=stereo)
    sample_width: int            # Sample width in bytes (1, 2, 4)
    duration: float              # Duration in seconds
    frames: int                  # Number of audio frames
    format: str                  # Audio format (e.g., "pcm", "wav")
    bit_depth: int              # Bit depth (8, 16, 24, 32)
```

### AdapterConfig

Configuration for audio adapters.

```python
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class AdapterConfig:
    """Configuration for audio adapters."""
    
    name: str                    # Adapter name
    enabled: bool               # Whether adapter is enabled
    parameters: Dict[str, Any]  # Adapter-specific parameters
    timeout_ms: Optional[int]   # Operation timeout in milliseconds
```

## Built-in Adapters

### DiscordAudioInputAdapter

Discord voice input adapter.

```python
class DiscordAudioInputAdapter(AudioInputAdapter):
    """Discord voice input adapter."""
    
    def __init__(self, config: dict):
        self.discord_client = None
        self.voice_client = None
        # ... initialization
    
    async def start_capture(self) -> None:
        """Start Discord voice capture."""
        # Connect to Discord voice channel
        pass
    
    async def stop_capture(self) -> None:
        """Stop Discord voice capture."""
        # Disconnect from voice channel
        pass
    
    async def get_audio_stream(self) -> AsyncIterator[AudioChunk]:
        """Get Discord audio stream."""
        # Yield audio chunks from Discord
        pass
```

### DiscordAudioOutputAdapter

Discord voice output adapter.

```python
class DiscordAudioOutputAdapter(AudioOutputAdapter):
    """Discord voice output adapter."""
    
    def __init__(self, config: dict):
        self.discord_client = None
        self.voice_client = None
        # ... initialization
    
    async def play_audio(self, audio_chunk: AudioChunk) -> None:
        """Play audio to Discord voice channel."""
        # Send audio to Discord
        pass
    
    async def stop_playback(self) -> None:
        """Stop Discord audio playback."""
        # Stop audio playback
        pass
```

### FileAudioInputAdapter

File-based audio input adapter for testing.

```python
class FileAudioInputAdapter(AudioInputAdapter):
    """File-based audio input adapter."""
    
    def __init__(self, config: dict):
        self.file_path = config.get("file_path")
        self.file_handle = None
        # ... initialization
    
    async def start_capture(self) -> None:
        """Start reading from audio file."""
        # Open audio file
        pass
    
    async def stop_capture(self) -> None:
        """Stop reading from audio file."""
        # Close audio file
        pass
    
    async def get_audio_stream(self) -> AsyncIterator[AudioChunk]:
        """Get audio stream from file."""
        # Read and yield audio chunks
        pass
```

### FileAudioOutputAdapter

File-based audio output adapter for testing.

```python
class FileAudioOutputAdapter(AudioOutputAdapter):
    """File-based audio output adapter."""
    
    def __init__(self, config: dict):
        self.file_path = config.get("file_path")
        self.file_handle = None
        # ... initialization
    
    async def play_audio(self, audio_chunk: AudioChunk) -> None:
        """Write audio to file."""
        # Write audio data to file
        pass
    
    async def stop_playback(self) -> None:
        """Stop writing to file."""
        # Close output file
        pass
```

## Adapter Manager

### AdapterManager

Manages registration and retrieval of audio adapters.

```python
class AdapterManager:
    """Manages audio input and output adapters."""
    
    def __init__(self):
        self._input_adapters: Dict[str, Type[AudioInputAdapter]] = {}
        self._output_adapters: Dict[str, Type[AudioOutputAdapter]] = {}
    
    def register_input_adapter(self, name: str, adapter_class: Type[AudioInputAdapter]) -> None:
        """Register an input adapter."""
        self._input_adapters[name] = adapter_class
    
    def register_output_adapter(self, name: str, adapter_class: Type[AudioOutputAdapter]) -> None:
        """Register an output adapter."""
        self._output_adapters[name] = adapter_class
    
    def get_input_adapter(self, name: str, config: dict) -> AudioInputAdapter:
        """Get an input adapter instance."""
        if name not in self._input_adapters:
            raise ValueError(f"Unknown input adapter: {name}")
        return self._input_adapters[name](config)
    
    def get_output_adapter(self, name: str, config: dict) -> AudioOutputAdapter:
        """Get an output adapter instance."""
        if name not in self._output_adapters:
            raise ValueError(f"Unknown output adapter: {name}")
        return self._output_adapters[name](config)
    
    def list_input_adapters(self) -> List[str]:
        """List available input adapters."""
        return list(self._input_adapters.keys())
    
    def list_output_adapters(self) -> List[str]:
        """List available output adapters."""
        return list(self._output_adapters.keys())
```

## Configuration

### Environment Variables

```bash
# Audio Adapter Configuration
AUDIO_INPUT_ADAPTER=discord          # Input adapter to use
AUDIO_OUTPUT_ADAPTER=discord        # Output adapter to use

# Discord Adapter Configuration
DISCORD_BOT_TOKEN=your_token_here
DISCORD_GUILD_ID=your_guild_id
DISCORD_VOICE_CHANNEL_ID=your_channel_id

# File Adapter Configuration (for testing)
FILE_INPUT_PATH=/path/to/input.wav
FILE_OUTPUT_PATH=/path/to/output.wav
```

### Configuration Examples

#### Discord Configuration

```python
discord_config = {
    "bot_token": "your_token_here",
    "guild_id": 123456789,
    "voice_channel_id": 987654321,
    "sample_rate": 48000,
    "channels": 2
}
```

#### File Configuration

```python
file_config = {
    "file_path": "/path/to/audio.wav",
    "sample_rate": 44100,
    "channels": 1,
    "format": "wav"
}
```

#### WebRTC Configuration

```python
webrtc_config = {
    "ice_servers": [
        {"urls": "stun:stun.l.google.com:19302"}
    ],
    "sample_rate": 16000,
    "channels": 1,
    "chunk_duration_ms": 20
}
```

## Error Handling

### Common Exceptions

```python
class AdapterError(Exception):
    """Base exception for adapter errors."""
    pass

class AdapterNotAvailableError(AdapterError):
    """Raised when adapter is not available."""
    pass

class AdapterConfigurationError(AdapterError):
    """Raised when adapter configuration is invalid."""
    pass

class AudioFormatError(AdapterError):
    """Raised when audio format is not supported."""
    pass
```

### Error Handling Best Practices

1.  **Graceful Degradation:** Handle errors without crashing
2.  **Logging:** Log errors with context information
3.  **Retry Logic:** Implement retry for transient failures
4.  **Resource Cleanup:** Always clean up resources on error
5.  **User Feedback:** Provide meaningful error messages

## Performance Considerations

### Latency Requirements

-  **Input Latency:** < 50ms from audio source to processing
-  **Output Latency:** < 100ms from processing to audio output
-  **End-to-End:** < 2s total response time

### Memory Management

-  **Buffer Sizes:** Use appropriate buffer sizes for your use case
-  **Memory Cleanup:** Always clean up audio buffers
-  **Streaming:** Use async generators for memory efficiency

### CPU Usage

-  **Audio Processing:** Minimize CPU usage in hot paths
-  **Format Conversion:** Cache format conversion results
-  **Threading:** Use asyncio instead of threads when possible

## Testing

### Unit Testing

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_adapter_lifecycle():
    """Test adapter start/stop lifecycle."""
    adapter = MyAudioInputAdapter(config)
    
    # Test start
    await adapter.start_capture()
    assert adapter.is_active is True
    
    # Test stop
    await adapter.stop_capture()
    assert adapter.is_active is False
```

### Integration Testing

```python
@pytest.mark.integration
async def test_adapter_with_real_audio():
    """Test adapter with real audio source."""
    # Use test audio files or hardware
    pass
```

### Performance Testing

```python
@pytest.mark.performance
async def test_adapter_latency():
    """Test adapter latency."""
    # Measure and assert latency requirements
    pass
```
