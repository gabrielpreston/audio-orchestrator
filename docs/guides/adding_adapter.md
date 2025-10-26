---
title: Adding a New Audio Adapter
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-22
---

# Adding a New Audio Adapter

## Overview

Audio adapters enable the orchestrator to work with different audio sources and
outputs beyond Discord. The adapter framework provides a clean abstraction layer
that allows the system to work with various audio interfaces while maintaining
consistent behavior.

## Architecture

The adapter system consists of two main interfaces:

-  **`AudioInputAdapter`** - Captures audio from sources (Discord, files, WebRTC, etc.)
-  **`AudioOutputAdapter`** - Plays audio to destinations (Discord, speakers, files, etc.)

## Interface Requirements

### Input Adapter

All input adapters must implement the `AudioInputAdapter` interface:

```python
from services.orchestrator.adapters.base import AudioInputAdapter
from services.orchestrator.adapters.types import AudioChunk, AudioMetadata

class MyAudioInputAdapter(AudioInputAdapter):
    """Custom audio input adapter."""
    
    async def start_capture(self) -> None:
        """Start capturing audio from the source."""
        pass
    
    async def stop_capture(self) -> None:
        """Stop capturing audio."""
        pass
    
    async def get_audio_stream(self) -> AsyncIterator[AudioChunk]:
        """Get async generator of audio chunks."""
        pass
    
    @property
    def is_active(self) -> bool:
        """Check if capture is currently active."""
        return False
```

### Output Adapter

All output adapters must implement the `AudioOutputAdapter` interface:

```python
from services.orchestrator.adapters.base import AudioOutputAdapter
from services.orchestrator.adapters.types import AudioChunk

class MyAudioOutputAdapter(AudioOutputAdapter):
    """Custom audio output adapter."""
    
    async def play_audio(self, audio_chunk: AudioChunk) -> None:
        """Play audio chunk to the destination."""
        pass
    
    async def stop_playback(self) -> None:
        """Stop audio playback."""
        pass
    
    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        return False
```

## Step-by-Step Guide

### 1. Create Adapter File

Create your adapter file in the appropriate location:

```bash
# For input adapters
services/orchestrator_enhanced/adapters/my_input_adapter.py

# For output adapters  
services/orchestrator_enhanced/adapters/my_output_adapter.py
```

### 2. Implement Interface Methods

Implement all required methods from the base interface:

```python
"""Custom audio input adapter implementation."""

import asyncio
import logging
from typing import AsyncIterator

from services.orchestrator.adapters.base import AudioInputAdapter
from services.orchestrator.adapters.types import AudioChunk, AudioMetadata

logger = logging.getLogger(__name__)


class MyAudioInputAdapter(AudioInputAdapter):
    """Custom audio input adapter for [your use case]."""
    
    def __init__(self, config: dict):
        """Initialize the adapter with configuration."""
        self.config = config
        self._active = False
        self._logger = logging.getLogger(__name__)
    
    async def start_capture(self) -> None:
        """Start capturing audio from the source."""
        try:
            # Initialize your audio source
            # e.g., open file, connect to WebRTC, etc.
            self._active = True
            self._logger.info("Audio capture started")
        except Exception as e:
            self._logger.error(f"Failed to start capture: {e}")
            raise
    
    async def stop_capture(self) -> None:
        """Stop capturing audio."""
        self._active = False
        # Clean up resources
        self._logger.info("Audio capture stopped")
    
    async def get_audio_stream(self) -> AsyncIterator[AudioChunk]:
        """Get async generator of audio chunks."""
        while self._active:
            try:
                # Read audio data from your source
                audio_data = await self._read_audio_data()
                
                if audio_data:
                    # Create AudioChunk with metadata
                    chunk = AudioChunk(
                        data=audio_data,
                        metadata=AudioMetadata(
                            sample_rate=44100,
                            channels=2,
                            sample_width=2,
                            duration=0.1,  # 100ms chunks
                            frames=len(audio_data) // 4,  # 16-bit stereo
                            format="pcm",
                            bit_depth=16
                        ),
                        correlation_id="my-adapter",
                        sequence_number=0,
                        is_silence=False,
                        volume_level=0.5
                    )
                    yield chunk
                else:
                    # No data available, yield control
                    await asyncio.sleep(0.01)
                    
            except Exception as e:
                self._logger.error(f"Error in audio stream: {e}")
                break
    
    @property
    def is_active(self) -> bool:
        """Check if capture is currently active."""
        return self._active
    
    async def _read_audio_data(self) -> bytes:
        """Read audio data from your source."""
        # Implement your audio reading logic
        # Return raw PCM audio data
        pass
```

### 3. Register Adapter

Register your adapter in the adapter manager:

```python
# In services/orchestrator_enhanced/adapters/manager.py

from .my_input_adapter import MyAudioInputAdapter
from .my_output_adapter import MyAudioOutputAdapter

class AdapterManager:
    def __init__(self):
        # ... existing code ...
        
        # Register your adapters
        self.register_input_adapter("my_input", MyAudioInputAdapter)
        self.register_output_adapter("my_output", MyAudioOutputAdapter)
```

### 4. Add Configuration

Add configuration options for your adapter:

```python
# In services/orchestrator_enhanced/config.py

# My Adapter Configuration
MY_INPUT_ENABLED = env.bool("MY_INPUT_ENABLED", default=False)
MY_INPUT_SOURCE = env.str("MY_INPUT_SOURCE", default="")
MY_OUTPUT_ENABLED = env.bool("MY_OUTPUT_ENABLED", default=False)
MY_OUTPUT_DESTINATION = env.str("MY_OUTPUT_DESTINATION", default="")
```

Add to `.env.sample`:

```bash
# My Adapter Configuration
MY_INPUT_ENABLED=false
MY_INPUT_SOURCE=
MY_OUTPUT_ENABLED=false
MY_OUTPUT_DESTINATION=
```

### 5. Write Tests

Create comprehensive tests for your adapter:

```python
"""Tests for MyAudioInputAdapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.orchestrator.adapters.my_input_adapter import MyAudioInputAdapter
from services.orchestrator.adapters.types import AudioChunk


@pytest.fixture
def adapter_config():
    """Test configuration for adapter."""
    return {
        "source": "test_source",
        "sample_rate": 44100,
        "channels": 2
    }


@pytest.fixture
def my_adapter(adapter_config):
    """Create adapter instance for testing."""
    return MyAudioInputAdapter(adapter_config)


@pytest.mark.asyncio
async def test_start_capture(my_adapter):
    """Test starting audio capture."""
    await my_adapter.start_capture()
    assert my_adapter.is_active is True


@pytest.mark.asyncio
async def test_stop_capture(my_adapter):
    """Test stopping audio capture."""
    await my_adapter.start_capture()
    await my_adapter.stop_capture()
    assert my_adapter.is_active is False


@pytest.mark.asyncio
async def test_audio_stream(my_adapter):
    """Test audio stream generation."""
    # Mock the audio reading
    with patch.object(my_adapter, '_read_audio_data', return_value=b'\x00\x01' * 1000):
        await my_adapter.start_capture()
        
        chunks = []
        async for chunk in my_adapter.get_audio_stream():
            chunks.append(chunk)
            if len(chunks) >= 3:  # Limit for testing
                break
        
        assert len(chunks) == 3
        assert all(isinstance(chunk, AudioChunk) for chunk in chunks)
        
        await my_adapter.stop_capture()


@pytest.mark.asyncio
async def test_error_handling(my_adapter):
    """Test error handling in audio stream."""
    with patch.object(my_adapter, '_read_audio_data', side_effect=Exception("Audio error")):
        await my_adapter.start_capture()
        
        chunks = []
        async for chunk in my_adapter.get_audio_stream():
            chunks.append(chunk)
            break  # Should exit on error
        
        # Should handle error gracefully
        assert len(chunks) == 0
```

## Example: WebRTC Adapter

Here's a complete example of a WebRTC input adapter:

```python
"""WebRTC audio input adapter."""

import asyncio
import logging
from typing import AsyncIterator, Optional

import webrtcvad
from services.orchestrator.adapters.base import AudioInputAdapter
from services.orchestrator.adapters.types import AudioChunk, AudioMetadata

logger = logging.getLogger(__name__)


class WebRTCAudioInputAdapter(AudioInputAdapter):
    """WebRTC-based audio input adapter."""
    
    def __init__(self, config: dict):
        """Initialize WebRTC adapter."""
        self.config = config
        self._active = False
        self._vad = webrtcvad.Vad(2)  # Aggressiveness level 2
        self._sample_rate = config.get("sample_rate", 16000)
        self._chunk_duration_ms = config.get("chunk_duration_ms", 20)
        self._chunk_size = int(self._sample_rate * self._chunk_duration_ms / 1000)
        self._logger = logging.getLogger(__name__)
    
    async def start_capture(self) -> None:
        """Start WebRTC audio capture."""
        try:
            # Initialize WebRTC connection
            # This would typically involve:
            # 1. Creating RTCPeerConnection
            # 2. Setting up media stream
            # 3. Adding audio track handlers
            self._active = True
            self._logger.info("WebRTC audio capture started")
        except Exception as e:
            self._logger.error(f"Failed to start WebRTC capture: {e}")
            raise
    
    async def stop_capture(self) -> None:
        """Stop WebRTC audio capture."""
        self._active = False
        # Close WebRTC connection
        self._logger.info("WebRTC audio capture stopped")
    
    async def get_audio_stream(self) -> AsyncIterator[AudioChunk]:
        """Get WebRTC audio stream."""
        sequence = 0
        
        while self._active:
            try:
                # Get audio data from WebRTC
                audio_data = await self._get_webrtc_audio()
                
                if audio_data and len(audio_data) >= self._chunk_size:
                    # Detect voice activity
                    is_speech = self._detect_speech(audio_data)
                    
                    # Create audio chunk
                    chunk = AudioChunk(
                        data=audio_data,
                        metadata=AudioMetadata(
                            sample_rate=self._sample_rate,
                            channels=1,  # WebRTC typically mono
                            sample_width=2,
                            duration=self._chunk_duration_ms / 1000.0,
                            frames=len(audio_data) // 2,
                            format="pcm",
                            bit_depth=16
                        ),
                        correlation_id="webrtc",
                        sequence_number=sequence,
                        is_silence=not is_speech,
                        volume_level=self._calculate_volume(audio_data)
                    )
                    
                    sequence += 1
                    yield chunk
                else:
                    await asyncio.sleep(0.01)
                    
            except Exception as e:
                self._logger.error(f"Error in WebRTC audio stream: {e}")
                break
    
    @property
    def is_active(self) -> bool:
        """Check if WebRTC capture is active."""
        return self._active
    
    def _detect_speech(self, audio_data: bytes) -> bool:
        """Detect speech using WebRTC VAD."""
        try:
            return self._vad.is_speech(audio_data, self._sample_rate)
        except Exception:
            return False
    
    def _calculate_volume(self, audio_data: bytes) -> float:
        """Calculate audio volume level."""
        # Simple RMS calculation
        import struct
        samples = struct.unpack(f'<{len(audio_data)//2}h', audio_data)
        rms = (sum(sample * sample for sample in samples) / len(samples)) ** 0.5
        return min(rms / 32768.0, 1.0)  # Normalize to 0-1
    
    async def _get_webrtc_audio(self) -> Optional[bytes]:
        """Get audio data from WebRTC connection."""
        # This would typically involve:
        # 1. Waiting for audio track data
        # 2. Converting to PCM format
        # 3. Returning raw audio bytes
        # For this example, return None (no actual WebRTC implementation)
        await asyncio.sleep(0.02)  # Simulate 20ms chunk
        return None  # Would return actual audio data
```

## Testing Strategies

### Unit Tests

-  Test individual methods in isolation
-  Mock external dependencies (WebRTC, file I/O, etc.)
-  Test error conditions and edge cases
-  Verify audio format handling

### Integration Tests

-  Test with real audio sources when possible
-  Verify audio quality and format conversion
-  Test performance under load
-  Validate error handling

### Manual Testing

-  Test with actual audio hardware
-  Verify audio quality and latency
-  Test with different audio formats
-  Validate configuration options

## Common Pitfalls and Solutions

### 1. Audio Format Mismatches

**Problem:** Adapter produces audio in wrong format
**Solution:** Always validate and convert audio formats in your adapter

### 2. Memory Leaks

**Problem:** Audio buffers not properly cleaned up
**Solution:** Implement proper resource cleanup in `stop_capture()`

### 3. Threading Issues

**Problem:** Audio callbacks running in wrong thread
**Solution:** Use asyncio properly and avoid blocking operations

### 4. Configuration Errors

**Problem:** Adapter fails with invalid configuration
**Solution:** Validate configuration in `__init__` and provide clear error messages

### 5. Performance Issues

**Problem:** Adapter causes high CPU usage
**Solution:** Profile your code and optimize hot paths

## Best Practices

1.  **Error Handling:** Always handle exceptions gracefully
2.  **Logging:** Use structured logging with correlation IDs
3.  **Resource Management:** Clean up resources properly
4.  **Configuration:** Validate all configuration parameters
5.  **Testing:** Write comprehensive tests for all code paths
6.  **Documentation:** Document all public methods and configuration options
7.  **Performance:** Consider latency and CPU usage
8.  **Compatibility:** Test with different audio formats and sample rates

## Integration with Orchestrator

Once your adapter is implemented and tested, it can be used by the orchestrator:

```python
# In orchestrator configuration
AUDIO_INPUT_ADAPTER = "my_input"
AUDIO_OUTPUT_ADAPTER = "my_output"

# The orchestrator will automatically use your adapter
# when these environment variables are set
```

## Next Steps

1.  Implement your adapter following this guide
2.  Write comprehensive tests
3.  Test with real audio sources
4.  Submit a pull request with your implementation
5.  Update this documentation if you discover new patterns

## Resources

-  [Audio Adapter Types](../api/audio_adapter_types.md)
-  [Audio Pipeline Architecture](../architecture/audio_pipeline.md)
-  [Testing Audio Adapters](../guides/testing_audio_adapters.md)
-  [Configuration Reference](../api/configuration.md)
