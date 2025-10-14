"""
Pytest configuration for mobile integration tests.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_room():
    """Create a mock LiveKit room for testing."""
    room = Mock()
    room.name = "test-room"
    room.localParticipant = Mock()
    room.remote_participants = {}
    room.connect = AsyncMock()
    room.disconnect = AsyncMock()
    return room


@pytest.fixture
def mock_participant():
    """Create a mock remote participant for testing."""
    participant = Mock()
    participant.identity = "test-user"
    participant.sid = "test-sid"
    return participant


@pytest.fixture
def mock_audio_frame():
    """Create a mock audio frame for testing."""
    from services.common.audio_contracts import AudioFrame
    import time
    
    return AudioFrame(
        pcm_data=b'\x00' * 640,  # 20ms of audio at 16kHz
        timestamp=time.time(),
        sequence_number=1,
        is_speech=True,
        confidence=0.8
    )


@pytest.fixture
def mock_audio_segment():
    """Create a mock audio segment for testing."""
    from services.common.audio_contracts import AudioSegment, WordTiming
    import time
    
    words = [
        WordTiming(word="hello", start_time=0.0, end_time=0.5, confidence=0.9),
        WordTiming(word="world", start_time=0.5, end_time=1.0, confidence=0.8),
    ]
    
    return AudioSegment(
        audio_frames=[],
        transcript="hello world",
        words=words,
        start_time=0.0,
        end_time=1.0,
        confidence=0.85,
        is_final=True
    )


@pytest.fixture
def mock_control_message():
    """Create a mock control message for testing."""
    from services.common.audio_contracts import WakeDetectedMessage
    return WakeDetectedMessage("test-123", 0.8)


@pytest.fixture
def mock_livekit_config():
    """Create a mock LiveKit configuration for testing."""
    return {
        "url": "wss://test.livekit.com",
        "token": "test-token",
        "room_name": "test-room"
    }


@pytest.fixture
def mock_audio_config():
    """Create a mock audio configuration for testing."""
    return {
        "sample_rate": 16000,
        "frame_ms": 20,
        "channels": 1,
        "bit_depth": 16
    }


@pytest.fixture
def mock_vad_config():
    """Create a mock VAD configuration for testing."""
    return {
        "enabled": True,
        "aggressiveness": 2,
        "timeout_ms": 2000,
        "padding_ms": 200,
        "min_speech_duration_ms": 300,
        "max_silence_duration_ms": 1000
    }


@pytest.fixture
def mock_wake_word_config():
    """Create a mock wake word configuration for testing."""
    return {
        "enabled": True,
        "phrases": ["hey atlas", "ok atlas"],
        "threshold": 0.5,
        "cooldown_ms": 1000
    }


@pytest.fixture
def mock_ui_config():
    """Create a mock UI configuration for testing."""
    return {
        "theme": "dark",
        "animations_enabled": True,
        "debug_mode": False
    }


@pytest.fixture
def mock_debug_config():
    """Create a mock debug configuration for testing."""
    return {
        "enabled": False,
        "log_level": "info",
        "save_audio": False
    }


@pytest.fixture
def mock_performance_config():
    """Create a mock performance configuration for testing."""
    return {
        "max_session_duration_minutes": 30,
        "audio_buffer_size_ms": 100,
        "network_timeout_ms": 30000,
        "retry_attempts": 3
    }


@pytest.fixture
def mock_app_config(
    mock_livekit_config,
    mock_audio_config,
    mock_vad_config,
    mock_wake_word_config,
    mock_ui_config,
    mock_debug_config,
    mock_performance_config
):
    """Create a mock app configuration for testing."""
    return {
        "livekit": mock_livekit_config,
        "audio": mock_audio_config,
        "vad": mock_vad_config,
        "wake_word": mock_wake_word_config,
        "ui": mock_ui_config,
        "debug": mock_debug_config,
        "performance": mock_performance_config
    }


@pytest.fixture
def mock_telemetry_data():
    """Create mock telemetry data for testing."""
    return {
        "rtt_ms": 150.5,
        "packet_loss_percent": 2.1,
        "jitter_ms": 25.3,
        "bitrate": 64000,
        "battery_level": 85,
        "thermal_state": "normal",
        "memory_usage": 128,
        "cpu_usage": 45.2
    }


@pytest.fixture
def mock_error():
    """Create a mock error for testing."""
    from services.common.audio_contracts import AppError
    import time
    
    return AppError(
        code="TEST_ERROR",
        message="Test error message",
        recoverable=True,
        timestamp=time.time(),
        context={"test": "data"}
    )


@pytest.fixture
def mock_ui_state():
    """Create a mock UI state for testing."""
    return {
        "is_connected": True,
        "is_recording": False,
        "is_processing": False,
        "is_responding": False,
        "is_muted": False,
        "current_transcript": "",
        "last_response": "",
        "error": None,
        "session_duration": 0,
        "audio_route": "speaker",
        "audio_input": "built_in"
    }


# Async test utilities
@pytest.fixture
def async_mock():
    """Create an async mock for testing."""
    return AsyncMock()


@pytest.fixture
def mock_async_context_manager():
    """Create a mock async context manager for testing."""
    class MockAsyncContextManager:
        def __init__(self, return_value):
            self.return_value = return_value
        
        async def __aenter__(self):
            return self.return_value
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    return MockAsyncContextManager


# Test data fixtures
@pytest.fixture
def sample_audio_data():
    """Create sample audio data for testing."""
    # 1 second of 16kHz mono 16-bit audio
    return b'\x00\x01' * 16000


@pytest.fixture
def sample_transcript():
    """Create sample transcript data for testing."""
    return {
        "text": "Hello, this is a test transcript.",
        "words": [
            {"word": "Hello", "start": 0.0, "end": 0.5, "confidence": 0.9},
            {"word": "this", "start": 0.5, "end": 0.7, "confidence": 0.8},
            {"word": "is", "start": 0.7, "end": 0.8, "confidence": 0.9},
            {"word": "a", "start": 0.8, "end": 0.9, "confidence": 0.7},
            {"word": "test", "start": 0.9, "end": 1.1, "confidence": 0.8},
            {"word": "transcript", "start": 1.1, "end": 1.5, "confidence": 0.9}
        ],
        "confidence": 0.85,
        "is_final": True
    }


@pytest.fixture
def sample_response():
    """Create sample response data for testing."""
    return {
        "text": "I understand you said: Hello, this is a test transcript.",
        "audio_url": "https://example.com/audio/response.wav",
        "duration_ms": 3000,
        "voice": "default"
    }


# Performance test fixtures
@pytest.fixture
def performance_test_config():
    """Create configuration for performance tests."""
    return {
        "max_latency_ms": 400,
        "max_packet_loss_percent": 10,
        "max_jitter_ms": 80,
        "max_memory_mb": 100,
        "max_cpu_percent": 80,
        "test_duration_seconds": 60,
        "concurrent_sessions": 10
    }


# Integration test fixtures
@pytest.fixture
def integration_test_config():
    """Create configuration for integration tests."""
    return {
        "livekit_url": "wss://test.livekit.com",
        "stt_url": "http://localhost:9000",
        "tts_url": "http://localhost:7000",
        "orchestrator_url": "http://localhost:8000",
        "test_timeout_seconds": 30,
        "retry_attempts": 3
    }