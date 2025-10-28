"""Fixtures for voice pipeline integration tests."""

import base64
from pathlib import Path
from typing import Any

import pytest

from services.tests.utils.audio_quality_helpers import (
    create_wav_file,
    generate_test_audio,
)


@pytest.fixture
def voice_pipeline_services() -> list[str]:
    """Services for complete voice pipeline."""
    return ["stt", "orchestrator", "llm", "tts"]


@pytest.fixture
def realistic_voice_audio() -> bytes:
    """Generate realistic voice-like audio for testing."""
    # Generate 2 seconds of voice-like audio at 16kHz mono
    pcm_data = generate_test_audio(
        duration=2.0,
        frequency=440.0,  # A4 note
        amplitude=0.5,
        noise_level=0.1,  # Slight noise for realism
    )
    return create_wav_file(pcm_data, sample_rate=16000, channels=1)


@pytest.fixture
def realistic_voice_audio_base64(realistic_voice_audio: bytes) -> str:
    """Base64-encoded realistic voice audio for JSON requests."""
    return base64.b64encode(realistic_voice_audio).decode()


@pytest.fixture
def realistic_voice_audio_multipart(realistic_voice_audio: bytes) -> dict[str, Any]:
    """Multipart form data for STT /transcribe endpoint."""
    from io import BytesIO

    return {"file": ("test_voice.wav", BytesIO(realistic_voice_audio), "audio/wav")}


@pytest.fixture
def test_voice_transcript() -> str:
    """Sample voice transcript for testing."""
    return "Hello, this is a test of the voice pipeline integration."


@pytest.fixture
def test_voice_context() -> dict[str, str]:
    """Test context for voice pipeline."""
    return {
        "guild_id": "123456789",
        "channel_id": "987654321",
        "user_id": "12345",
    }


@pytest.fixture
def test_voice_correlation_id() -> str:
    """Test correlation ID for voice pipeline."""
    return "voice-test-correlation-1234567890abcdef"


@pytest.fixture
def voice_pipeline_artifacts_dir(test_artifacts_dir: Path) -> Path:
    """Directory for voice pipeline test artifacts."""
    voice_dir = test_artifacts_dir / "voice_pipeline"
    voice_dir.mkdir(parents=True, exist_ok=True)
    return voice_dir


@pytest.fixture
def test_voice_quality_thresholds() -> dict[str, float]:
    """Voice quality thresholds for testing."""
    return {
        "min_snr_db": 20.0,
        "max_thd_percent": 1.0,
        "min_voice_range_ratio": 0.8,
        "max_aliasing_ratio": 0.1,
    }


@pytest.fixture
def test_voice_performance_thresholds() -> dict[str, float]:
    """Voice performance thresholds for testing."""
    return {
        "max_end_to_end_latency_s": 2.0,
        "max_stt_latency_s": 0.3,
        "max_tts_latency_s": 1.0,
        "max_wake_detection_latency_s": 0.2,
    }


# REST API fixtures removed - using REST API now


@pytest.fixture
def test_voice_pipeline_config() -> dict[str, Any]:
    """Test configuration for voice pipeline."""
    return {
        "stt_url": "http://stt:9000",
        "tts_url": "http://tts-bark:7100",
        "llm_url": "http://llm-flan:8100",
        "orchestrator_url": "http://orchestrator-enhanced:8200",
        "discord_url": "http://discord:8001",
        "auth_token": "test-token",
        "timeout": 30.0,
    }
