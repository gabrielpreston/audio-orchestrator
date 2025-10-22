---
title: Testing Audio Adapters
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-22
---

# Testing Audio Adapters

## Overview

This guide covers comprehensive testing strategies for audio adapters in the audio orchestrator platform. Proper testing ensures adapters work correctly, handle errors gracefully, and meet performance requirements.

## Testing Strategy

### Test Categories

1.  **Unit Tests** - Test individual methods in isolation
2.  **Component Tests** - Test adapter with mocked dependencies
3.  **Integration Tests** - Test adapter with real audio sources
4.  **Performance Tests** - Test latency and resource usage
5.  **Quality Tests** - Test audio quality and format handling

## Unit Testing

### Basic Adapter Tests

```python
"""Unit tests for audio adapters."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from services.orchestrator.adapters.my_input_adapter import MyAudioInputAdapter
from services.orchestrator.adapters.types import AudioChunk, AudioMetadata


@pytest.fixture
def adapter_config():
    """Test configuration for adapter."""
    return {
        "source": "test_source",
        "sample_rate": 44100,
        "channels": 2,
        "chunk_duration_ms": 20
    }


@pytest.fixture
def my_adapter(adapter_config):
    """Create adapter instance for testing."""
    return MyAudioInputAdapter(adapter_config)


class TestAdapterLifecycle:
    """Test adapter start/stop lifecycle."""
    
    @pytest.mark.asyncio
    async def test_start_capture(self, my_adapter):
        """Test starting audio capture."""
        await my_adapter.start_capture()
        assert my_adapter.is_active is True
    
    @pytest.mark.asyncio
    async def test_stop_capture(self, my_adapter):
        """Test stopping audio capture."""
        await my_adapter.start_capture()
        await my_adapter.stop_capture()
        assert my_adapter.is_active is False
    
    @pytest.mark.asyncio
    async def test_double_start(self, my_adapter):
        """Test starting capture when already active."""
        await my_adapter.start_capture()
        # Should not raise exception
        await my_adapter.start_capture()
        assert my_adapter.is_active is True
    
    @pytest.mark.asyncio
    async def test_stop_when_inactive(self, my_adapter):
        """Test stopping capture when not active."""
        # Should not raise exception
        await my_adapter.stop_capture()
        assert my_adapter.is_active is False


class TestAudioStream:
    """Test audio stream generation."""
    
    @pytest.mark.asyncio
    async def test_audio_stream_basic(self, my_adapter):
        """Test basic audio stream functionality."""
        # Mock the audio reading method
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
    async def test_audio_stream_empty_data(self, my_adapter):
        """Test audio stream with empty data."""
        with patch.object(my_adapter, '_read_audio_data', return_value=b''):
            await my_adapter.start_capture()
            
            chunks = []
            async for chunk in my_adapter.get_audio_stream():
                chunks.append(chunk)
                if len(chunks) >= 1:  # Should not yield empty chunks
                    break
            
            # Should handle empty data gracefully
            assert len(chunks) == 0
            
            await my_adapter.stop_capture()
    
    @pytest.mark.asyncio
    async def test_audio_stream_error_handling(self, my_adapter):
        """Test error handling in audio stream."""
        with patch.object(my_adapter, '_read_audio_data', side_effect=Exception("Audio error")):
            await my_adapter.start_capture()
            
            chunks = []
            async for chunk in my_adapter.get_audio_stream():
                chunks.append(chunk)
                break  # Should exit on error
            
            # Should handle error gracefully
            assert len(chunks) == 0
            
            await my_adapter.stop_capture()


class TestAudioChunkCreation:
    """Test audio chunk creation and metadata."""
    
    @pytest.mark.asyncio
    async def test_audio_chunk_metadata(self, my_adapter):
        """Test that audio chunks have correct metadata."""
        test_audio_data = b'\x00\x01' * 1000  # 2000 bytes
        
        with patch.object(my_adapter, '_read_audio_data', return_value=test_audio_data):
            await my_adapter.start_capture()
            
            chunk = None
            async for chunk in my_adapter.get_audio_stream():
                break
            
            assert chunk is not None
            assert chunk.data == test_audio_data
            assert isinstance(chunk.metadata, AudioMetadata)
            assert chunk.metadata.sample_rate == 44100
            assert chunk.metadata.channels == 2
            assert chunk.correlation_id == "my-adapter"
            assert chunk.sequence_number == 0
            
            await my_adapter.stop_capture()
    
    @pytest.mark.asyncio
    async def test_sequence_numbering(self, my_adapter):
        """Test that sequence numbers increment correctly."""
        with patch.object(my_adapter, '_read_audio_data', return_value=b'\x00\x01' * 1000):
            await my_adapter.start_capture()
            
            chunks = []
            async for chunk in my_adapter.get_audio_stream():
                chunks.append(chunk)
                if len(chunks) >= 3:
                    break
            
            # Check sequence numbers
            for i, chunk in enumerate(chunks):
                assert chunk.sequence_number == i
            
            await my_adapter.stop_capture()
```

### Error Handling Tests

```python
class TestErrorHandling:
    """Test error handling in adapters."""
    
    @pytest.mark.asyncio
    async def test_start_capture_error(self, my_adapter):
        """Test error handling in start_capture."""
        with patch.object(my_adapter, '_initialize_audio_source', side_effect=Exception("Init error")):
            with pytest.raises(Exception, match="Init error"):
                await my_adapter.start_capture()
    
    @pytest.mark.asyncio
    async def test_audio_stream_connection_error(self, my_adapter):
        """Test handling of connection errors."""
        with patch.object(my_adapter, '_read_audio_data', side_effect=ConnectionError("Connection lost")):
            await my_adapter.start_capture()
            
            chunks = []
            async for chunk in my_adapter.get_audio_stream():
                chunks.append(chunk)
                break  # Should exit on connection error
            
            # Should handle connection error gracefully
            assert len(chunks) == 0
    
    @pytest.mark.asyncio
    async def test_invalid_audio_format(self, my_adapter):
        """Test handling of invalid audio formats."""
        # Mock invalid audio data
        invalid_data = b'invalid_audio_data'
        
        with patch.object(my_adapter, '_read_audio_data', return_value=invalid_data):
            await my_adapter.start_capture()
            
            chunks = []
            async for chunk in my_adapter.get_audio_stream():
                chunks.append(chunk)
                break
            
            # Should handle invalid format gracefully
            # (exact behavior depends on adapter implementation)
            assert len(chunks) == 0 or chunks[0].data == invalid_data
```

## Component Testing

### Testing with Mocked Dependencies

```python
"""Component tests for audio adapters."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.orchestrator.adapters.discord_input_adapter import DiscordAudioInputAdapter


class TestDiscordAdapter:
    """Test Discord adapter with mocked Discord client."""
    
    @pytest.fixture
    def mock_discord_client(self):
        """Mock Discord client."""
        client = MagicMock()
        client.voice = MagicMock()
        return client
    
    @pytest.fixture
    def mock_voice_client(self):
        """Mock voice client."""
        voice_client = MagicMock()
        voice_client.is_connected.return_value = True
        return voice_client
    
    @pytest.fixture
    def discord_adapter(self, mock_discord_client):
        """Create Discord adapter with mocked client."""
        config = {
            "guild_id": 123456789,
            "voice_channel_id": 987654321,
            "sample_rate": 48000
        }
        return DiscordAudioInputAdapter(config)
    
    @pytest.mark.asyncio
    async def test_discord_connection(self, discord_adapter, mock_discord_client, mock_voice_client):
        """Test Discord voice connection."""
        with patch.object(discord_adapter, '_get_voice_client', return_value=mock_voice_client):
            await discord_adapter.start_capture()
            assert discord_adapter.is_active is True
    
    @pytest.mark.asyncio
    async def test_discord_audio_reception(self, discord_adapter, mock_voice_client):
        """Test receiving audio from Discord."""
        # Mock Discord audio reception
        mock_audio_data = b'\x00\x01' * 2000
        
        with patch.object(discord_adapter, '_get_voice_client', return_value=mock_voice_client):
            with patch.object(discord_adapter, '_receive_discord_audio', return_value=mock_audio_data):
                await discord_adapter.start_capture()
                
                chunks = []
                async for chunk in discord_adapter.get_audio_stream():
                    chunks.append(chunk)
                    if len(chunks) >= 1:
                        break
                
                assert len(chunks) == 1
                assert chunks[0].data == mock_audio_data
```

## Integration Testing

### Testing with Real Audio Sources

```python
"""Integration tests for audio adapters."""

import pytest
import asyncio
import tempfile
import wave
from pathlib import Path
from services.orchestrator.adapters.file_input_adapter import FileAudioInputAdapter


class TestFileAdapterIntegration:
    """Test file adapter with real audio files."""
    
    @pytest.fixture
    def test_audio_file(self):
        """Create a test audio file."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            # Create a simple WAV file
            with wave.open(f.name, 'w') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(44100)  # 44.1kHz
                
                # Write some test audio data
                frames = b'\x00\x01' * 4410  # 0.1 seconds of audio
                wav_file.writeframes(frames)
            
            yield f.name
            Path(f.name).unlink()  # Clean up
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_file_adapter_with_real_audio(self, test_audio_file):
        """Test file adapter with real audio file."""
        config = {
            "file_path": test_audio_file,
            "sample_rate": 44100,
            "channels": 1
        }
        
        adapter = FileAudioInputAdapter(config)
        
        try:
            await adapter.start_capture()
            assert adapter.is_active is True
            
            chunks = []
            async for chunk in adapter.get_audio_stream():
                chunks.append(chunk)
                if len(chunks) >= 5:  # Read first 5 chunks
                    break
            
            assert len(chunks) > 0
            assert all(isinstance(chunk, AudioChunk) for chunk in chunks)
            assert all(chunk.metadata.sample_rate == 44100 for chunk in chunks)
            assert all(chunk.metadata.channels == 1 for chunk in chunks)
            
        finally:
            await adapter.stop_capture()
```

## Performance Testing

### Latency Testing

```python
"""Performance tests for audio adapters."""

import pytest
import time
import asyncio
from services.orchestrator.adapters.my_input_adapter import MyAudioInputAdapter


class TestAdapterPerformance:
    """Test adapter performance requirements."""
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_start_capture_latency(self, my_adapter):
        """Test that start_capture completes within latency requirements."""
        start_time = time.time()
        await my_adapter.start_capture()
        end_time = time.time()
        
        latency_ms = (end_time - start_time) * 1000
        assert latency_ms < 100, f"Start capture took {latency_ms}ms, should be < 100ms"
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_audio_stream_latency(self, my_adapter):
        """Test that audio stream has acceptable latency."""
        with patch.object(my_adapter, '_read_audio_data', return_value=b'\x00\x01' * 1000):
            await my_adapter.start_capture()
            
            start_time = time.time()
            chunk = None
            async for chunk in my_adapter.get_audio_stream():
                break
            end_time = time.time()
            
            latency_ms = (end_time - start_time) * 1000
            assert latency_ms < 50, f"Audio stream latency {latency_ms}ms, should be < 50ms"
            assert chunk is not None
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_memory_usage(self, my_adapter):
        """Test that adapter doesn't leak memory."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Run adapter for multiple cycles
        for _ in range(10):
            with patch.object(my_adapter, '_read_audio_data', return_value=b'\x00\x01' * 1000):
                await my_adapter.start_capture()
                
                chunks = []
                async for chunk in my_adapter.get_audio_stream():
                    chunks.append(chunk)
                    if len(chunks) >= 5:
                        break
                
                await my_adapter.stop_capture()
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 10MB)
        assert memory_increase < 10 * 1024 * 1024, f"Memory increased by {memory_increase} bytes"
```

## Quality Testing

### Audio Quality Tests

```python
"""Audio quality tests for adapters."""

import pytest
import numpy as np
from services.orchestrator.adapters.types import AudioChunk, AudioMetadata


class TestAudioQuality:
    """Test audio quality and format handling."""
    
    def test_audio_format_validation(self):
        """Test that audio formats are validated correctly."""
        # Test valid format
        valid_metadata = AudioMetadata(
            sample_rate=44100,
            channels=2,
            sample_width=2,
            duration=0.1,
            frames=4410,
            format="pcm",
            bit_depth=16
        )
        
        chunk = AudioChunk(
            data=b'\x00\x01' * 4410,
            metadata=valid_metadata,
            correlation_id="test",
            sequence_number=0,
            is_silence=False,
            volume_level=0.5
        )
        
        assert chunk.metadata.sample_rate == 44100
        assert chunk.metadata.channels == 2
        assert chunk.metadata.bit_depth == 16
    
    def test_audio_chunk_consistency(self):
        """Test that audio chunks are internally consistent."""
        # Create test audio data
        sample_rate = 44100
        duration = 0.1  # 100ms
        channels = 2
        sample_width = 2  # 16-bit
        
        frames = int(sample_rate * duration)
        data_size = frames * channels * sample_width
        test_data = b'\x00\x01' * (data_size // 2)
        
        metadata = AudioMetadata(
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
            duration=duration,
            frames=frames,
            format="pcm",
            bit_depth=16
        )
        
        chunk = AudioChunk(
            data=test_data,
            metadata=metadata,
            correlation_id="test",
            sequence_number=0,
            is_silence=False,
            volume_level=0.5
        )
        
        # Verify consistency
        assert len(chunk.data) == data_size
        assert chunk.metadata.frames == frames
        assert chunk.metadata.duration == duration
    
    @pytest.mark.asyncio
    async def test_audio_stream_quality(self, my_adapter):
        """Test audio stream maintains quality over time."""
        with patch.object(my_adapter, '_read_audio_data', return_value=b'\x00\x01' * 1000):
            await my_adapter.start_capture()
            
            chunks = []
            async for chunk in my_adapter.get_audio_stream():
                chunks.append(chunk)
                if len(chunks) >= 10:  # Test multiple chunks
                    break
            
            # All chunks should have consistent format
            for chunk in chunks:
                assert chunk.metadata.sample_rate == 44100
                assert chunk.metadata.channels == 2
                assert chunk.metadata.bit_depth == 16
                assert len(chunk.data) > 0
            
            await my_adapter.stop_capture()
```

## Test Configuration

### Pytest Configuration

```python
# conftest.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_audio_data():
    """Mock audio data for testing."""
    return b'\x00\x01' * 1000

@pytest.fixture
def adapter_config():
    """Default adapter configuration for testing."""
    return {
        "sample_rate": 44100,
        "channels": 2,
        "chunk_duration_ms": 20,
        "timeout_ms": 5000
    }
```

### Test Markers

```python
# pytest.ini
[tool:pytest]
markers =
    unit: Unit tests
    component: Component tests
    integration: Integration tests
    performance: Performance tests
    quality: Audio quality tests
    slow: Slow running tests
```

## Running Tests

### Test Commands

```bash
# Run all tests
pytest services/orchestrator/tests/unit/adapters/

# Run specific test categories
pytest -m unit services/orchestrator/tests/unit/adapters/
pytest -m component services/orchestrator/tests/component/adapters/
pytest -m integration services/orchestrator/tests/integration/adapters/
pytest -m performance services/orchestrator/tests/performance/adapters/

# Run with coverage
pytest --cov=services.orchestrator.adapters services/orchestrator/tests/unit/adapters/

# Run specific test file
pytest services/orchestrator/tests/unit/adapters/test_my_adapter.py

# Run with verbose output
pytest -v services/orchestrator/tests/unit/adapters/
```

### Continuous Integration

```yaml
# .github/workflows/test-adapters.yml
name: Test Audio Adapters

on: [push, pull_request]

jobs:
  test-adapters:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.11
    
    - name: Install dependencies
      run: |
        pip install -r services/requirements-dev.txt
        pip install pytest-cov
    
    - name: Run unit tests
      run: pytest -m unit services/orchestrator/tests/unit/adapters/
    
    - name: Run component tests
      run: pytest -m component services/orchestrator/tests/component/adapters/
    
    - name: Run integration tests
      run: pytest -m integration services/orchestrator/tests/integration/adapters/
    
    - name: Run performance tests
      run: pytest -m performance services/orchestrator/tests/performance/adapters/
```

## Best Practices

### Test Organization

1.  **Separate test files** for each adapter
2.  **Group related tests** in classes
3.  **Use descriptive test names** that explain what is being tested
4.  **Mock external dependencies** in unit tests
5.  **Use real audio sources** in integration tests

### Test Data Management

1.  **Use fixtures** for common test data
2.  **Create test audio files** programmatically
3.  **Clean up test files** after tests
4.  **Use appropriate audio formats** for testing

### Performance Considerations

1.  **Set reasonable timeouts** for async operations
2.  **Limit test duration** to avoid slow test suites
3.  **Use appropriate buffer sizes** for testing
4.  **Monitor memory usage** in long-running tests

### Error Testing

1.  **Test all error conditions** your adapter can encounter
2.  **Verify error messages** are helpful
3.  **Test resource cleanup** on errors
4.  **Test retry logic** if implemented

## Debugging Tests

### Common Issues

1.  **Async test failures** - Ensure proper async/await usage
2.  **Mock not working** - Check mock setup and scope
3.  **Audio format issues** - Verify test audio data format
4.  **Timing issues** - Add appropriate delays in tests
5.  **Resource leaks** - Ensure proper cleanup in tests

### Debugging Tools

```python
# Add debugging to tests
import logging
logging.basicConfig(level=logging.DEBUG)

# Use pytest debugging
pytest --pdb services/orchestrator/tests/unit/adapters/test_my_adapter.py

# Add print statements for debugging
print(f"Debug: chunk data length = {len(chunk.data)}")
print(f"Debug: metadata = {chunk.metadata}")
```

This comprehensive testing guide ensures that audio adapters are thoroughly tested and meet all quality and performance requirements.
