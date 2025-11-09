"""Test fixtures for Discord service tests."""

from collections.abc import Callable, Generator
from unittest.mock import Mock

import numpy as np
import pytest

from services.common.audio import AudioProcessor
from services.discord.audio import AudioSegment
from services.discord.config import (
    AudioConfig,
    BotConfig,
    STTConfig,
    TelemetryConfig,
    WakeConfig,
)


@pytest.fixture
def sample_pcm_audio() -> bytes:
    """Generate sample PCM audio data."""
    # Generate 1 second of 16kHz mono audio with sine wave
    sample_rate = 16000
    duration = 1.0
    frequency = 440  # A4 note

    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio_float = np.sin(2 * np.pi * frequency * t) * 0.5  # 50% amplitude
    audio_int16 = (audio_float * 32767).astype(np.int16)
    return audio_int16.tobytes()


@pytest.fixture
def mock_audio_processor():
    """Create mock audio processor."""
    processor = Mock(spec=AudioProcessor)
    processor.normalize_audio = Mock(return_value=(b"normalized_audio", 2000.0))
    processor.calculate_rms = Mock(return_value=1000.0)
    processor.resample_audio = Mock(return_value=b"resampled_audio")
    return processor


@pytest.fixture
def mock_vad():
    """Create mock VAD."""
    vad = Mock()
    vad.is_speech = Mock(return_value=True)
    return vad


@pytest.fixture
def mock_wake_detector():
    """Create mock wake detector."""
    detector = Mock()
    detector.detect = Mock()
    return detector


@pytest.fixture
def mock_transcription_client():
    """Create mock transcription client."""
    client = Mock()
    client.transcribe = Mock()
    client.get_circuit_stats = Mock(return_value={"state": "closed", "available": True})
    return client


@pytest.fixture
def mock_orchestrator_client():
    """Create mock orchestrator client."""
    client = Mock()
    client.process_transcript = Mock()
    return client


@pytest.fixture
def generate_test_audio() -> Callable[[int, float, float], bytes]:
    """Generate test audio data."""

    def _generate_audio(
        sample_rate: int = 16000, duration: float = 1.0, frequency: float = 440.0
    ) -> bytes:
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_float = np.sin(2 * np.pi * frequency * t) * 0.5
        audio_int16 = (audio_float * 32767).astype(np.int16)
        return audio_int16.tobytes()

    return _generate_audio


@pytest.fixture
def assert_audio_properties() -> Callable[[bytes, int, float], None]:
    """Assert audio properties."""

    def _assert_audio(pcm_data: bytes, sample_rate: int, duration: float):
        assert len(pcm_data) > 0
        assert len(pcm_data) == sample_rate * duration * 2  # 2 bytes per int16 sample
        assert isinstance(pcm_data, bytes)

    return _assert_audio


@pytest.fixture
def capture_structured_logs() -> Generator[Mock, None, None]:
    """Capture structured logs for testing."""
    # This would be implemented with a log capture mechanism
    # For now, return a mock
    yield Mock()


@pytest.fixture
def mock_config(tmp_path):
    """Create mock configuration."""
    audio_config = AudioConfig(
        allowlist_user_ids=[],
        silence_timeout_seconds=0.75,
        max_segment_duration_seconds=15.0,
        min_segment_duration_seconds=0.3,
        aggregation_window_seconds=1.5,
        input_sample_rate_hz=48000,
        vad_sample_rate_hz=16000,
        vad_frame_duration_ms=30,
        vad_aggressiveness=2,
    )

    stt_config = STTConfig(
        base_url="http://test-stt:9000",
        request_timeout_seconds=45,
        max_retries=3,
        forced_language="en",
    )

    wake_config = WakeConfig(
        model_paths=[],
        activation_threshold=0.5,
        target_sample_rate_hz=16000,
        enabled=True,
    )

    telemetry_config = TelemetryConfig()

    config = Mock(spec=BotConfig)
    config.audio = audio_config
    config.stt = stt_config
    config.wake = wake_config
    config.telemetry = telemetry_config

    return config


@pytest.fixture
def sample_audio_segment(sample_pcm_audio):
    """Create sample audio segment."""
    return AudioSegment(
        user_id=12345,
        pcm=sample_pcm_audio,
        sample_rate=16000,
        start_timestamp=0.0,
        end_timestamp=1.0,
        correlation_id="test-correlation-123",
        frame_count=16000,
    )
