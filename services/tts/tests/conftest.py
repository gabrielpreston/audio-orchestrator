"""Test configuration for services.tts module."""

from collections.abc import Generator
from typing import Any
from unittest import mock

import numpy as np
import pytest


@pytest.fixture
def mock_piper_model() -> Generator[mock.Mock, None, None]:
    """Mock Piper TTS model for testing."""
    with mock.patch("piper.PiperVoice") as mock_voice:
        # Configure mock voice
        mock_voice.return_value.synthesize.return_value = np.random.randn(22050).astype(np.float32)
        mock_voice.return_value.sample_rate = 22050
        yield mock_voice.return_value


@pytest.fixture
def mock_audio_processor() -> Generator[mock.Mock, None, None]:
    """Mock audio processor for testing."""
    with mock.patch("librosa.load") as mock_load:
        mock_audio = np.random.randn(22050)  # 1 second of audio at 22.05kHz
        mock_sr = 22050
        mock_load.return_value = (mock_audio, mock_sr)
        yield mock_load


@pytest.fixture
def mock_soundfile() -> Generator[mock.Mock, None, None]:
    """Mock soundfile for testing."""
    with mock.patch("soundfile.write") as mock_write:
        mock_write.return_value = None
        yield mock_write


@pytest.fixture
def test_synthesis_request() -> dict[str, Any]:
    """Provide test synthesis request data."""
    return {
        "text": "Hello, this is a test of the text-to-speech system.",
        "voice": "en_US-amy-medium",
        "format": "wav",
        "sample_rate": 22050,
        "length_scale": 1.0,
        "noise_scale": 0.667,
        "noise_w": 0.8,
    }


@pytest.fixture
def test_synthesis_response() -> dict[str, Any]:
    """Provide test synthesis response data."""
    return {
        "audio_data": b"mock audio data",
        "sample_rate": 22050,
        "format": "wav",
        "duration": 2.5,
        "voice": "en_US-amy-medium",
    }


@pytest.fixture
def test_audio_data() -> np.ndarray:
    """Provide test audio data for TTS testing."""
    # Generate 2.5 seconds of 22.05kHz mono audio
    return np.random.randn(55125).astype(np.float32)


@pytest.fixture
def mock_http_client() -> Generator[mock.Mock, None, None]:
    """Mock HTTP client for testing."""
    with mock.patch("httpx.AsyncClient") as mock_client:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.content = b"mock audio data"
        mock_response.headers = {"Content-Type": "audio/wav"}
        mock_client.return_value.post.return_value = mock_response
        yield mock_client.return_value


@pytest.fixture
def test_voice_config() -> dict[str, Any]:
    """Provide test voice configuration."""
    return {
        "name": "en_US-amy-medium",
        "language": "en_US",
        "gender": "female",
        "sample_rate": 22050,
        "format": "wav",
    }


@pytest.fixture
def mock_file_upload() -> Generator[mock.Mock, None, None]:
    """Mock file upload for testing."""
    with mock.patch("fastapi.UploadFile") as mock_file:
        mock_file.return_value.filename = "test_text.txt"
        mock_file.return_value.content_type = "text/plain"
        mock_file.return_value.read.return_value = b"Hello, this is a test."
        yield mock_file.return_value


@pytest.fixture
def test_rate_limit_config() -> dict[str, Any]:
    """Provide test rate limit configuration."""
    return {"max_requests_per_minute": 60, "max_concurrent_requests": 4, "max_text_length": 1000}
