"""Shared fixtures for testing service tests."""

import base64
from pathlib import Path
from typing import Any

import pytest

# Import existing fixtures to reuse
from services.tests.fixtures.integration_fixtures import (  # noqa: F401
    sample_audio_bytes,
)
from services.tests.fixtures.voice_pipeline_fixtures import (  # noqa: F401
    realistic_voice_audio,
)


@pytest.fixture
def sample_wav_file(temp_dir: Path) -> Path:
    """Create temporary WAV file for testing."""
    # Create minimal WAV file bytes for testing
    # WAV header + minimal data
    wav_bytes = (
        b"RIFF"
        b"\x24\x00\x00\x00"  # File size - 36
        b"WAVE"
        b"fmt \x10\x00\x00\x00"  # fmt chunk
        b"\x01\x00\x01\x00"  # Audio format (PCM), channels (1)
        b"\x40\x1f\x00\x00"  # Sample rate (8000)
        b"\x80\x3e\x00\x00"  # Byte rate
        b"\x02\x00\x10\x00"  # Block align, bits per sample
        b"data"
        b"\x00\x00\x00\x00"  # Data size (0 - minimal)
    )
    audio_file = temp_dir / "test_audio.wav"
    audio_file.write_bytes(wav_bytes)
    return audio_file


@pytest.fixture
def mock_orchestrator_response() -> dict[str, Any]:
    """Standard orchestrator JSON response with audio_data/base64."""
    # Create sample audio bytes for base64 encoding
    audio_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    audio_b64 = base64.b64encode(audio_bytes).decode()

    return {
        "success": True,
        "response_text": "This is a test response",
        "audio_data": audio_b64,
        "audio_format": "wav",
        "correlation_id": "test-correlation-123",
    }


@pytest.fixture
def mock_orchestrator_response_no_audio() -> dict[str, Any]:
    """Orchestrator response without audio (triggers TTS fallback)."""
    return {
        "success": True,
        "response_text": "This is a test response",
        "correlation_id": "test-correlation-123",
    }


@pytest.fixture
def mock_orchestrator_response_error() -> dict[str, Any]:
    """Orchestrator response with error."""
    return {
        "success": False,
        "error": "Orchestration failed",
        "correlation_id": "test-correlation-123",
    }


@pytest.fixture
def mock_tts_response() -> dict[str, Any]:
    """Standard TTS (Bark) JSON response with base64 audio."""
    # Create sample audio bytes for base64 encoding
    audio_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    audio_b64 = base64.b64encode(audio_bytes).decode()

    return {
        "audio": audio_b64,
    }


@pytest.fixture
def mock_audio_preprocessor_response() -> bytes:
    """Audio preprocessing service response (bytes)."""
    # Return processed audio bytes (simulated enhanced audio)
    return b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00_enhanced"


@pytest.fixture
def mock_stt_response() -> dict[str, Any]:
    """Standard STT JSON response."""
    return {
        "text": "hello world this is a test transcript",
        "confidence": 0.95,
        "language": "en",
    }
