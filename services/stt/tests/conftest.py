"""Test configuration for services.stt module."""

from collections.abc import Generator
from typing import Any
from unittest import mock

import numpy as np
import pytest


@pytest.fixture
def mock_whisper_model() -> Generator[mock.Mock, None, None]:
    """Mock Whisper model for testing."""
    with mock.patch("faster_whisper.WhisperModel") as mock_model:
        # Configure mock model
        mock_model.return_value.transcribe.return_value = [
            {
                "text": "hey atlas, what's the weather",
                "language": "en",
                "language_probability": 0.99,
                "start": 0.0,
                "end": 2.5,
                "no_speech_prob": 0.1,
            }
        ]
        yield mock_model.return_value


@pytest.fixture
def mock_audio_processor() -> Generator[mock.Mock, None, None]:
    """Mock audio processor for testing."""
    with mock.patch("librosa.load") as mock_load:
        # Return mock audio data
        mock_audio = np.random.randn(48000)  # 1 second of audio at 48kHz
        mock_sr = 48000
        mock_load.return_value = (mock_audio, mock_sr)
        yield mock_load


@pytest.fixture
def mock_soundfile() -> Generator[mock.Mock, None, None]:
    """Mock soundfile for testing."""
    with mock.patch("soundfile.read") as mock_read:
        mock_audio = np.random.randn(16000)  # 1 second of audio at 16kHz
        mock_sr = 16000
        mock_read.return_value = (mock_audio, mock_sr)
        yield mock_read


@pytest.fixture
def test_audio_data() -> np.ndarray:
    """Provide test audio data for STT testing."""
    # Generate 2 seconds of 16kHz mono audio
    return np.random.randn(32000).astype(np.float32)


@pytest.fixture
def test_transcription_request() -> dict[str, Any]:
    """Provide test transcription request data."""
    return {
        "audio_data": b"mock audio data",
        "sample_rate": 16000,
        "language": "en",
        "format": "wav",
    }


@pytest.fixture
def test_transcription_response() -> dict[str, Any]:
    """Provide test transcription response data."""
    return {
        "transcript": "hey atlas, what's the weather",
        "confidence": 0.95,
        "language": "en",
        "language_probability": 0.99,
        "start_time": 0.0,
        "end_time": 2.5,
        "no_speech_probability": 0.1,
        "segments": [
            {
                "text": "hey atlas, what's the weather",
                "start": 0.0,
                "end": 2.5,
                "no_speech_prob": 0.1,
            }
        ],
    }


@pytest.fixture
def mock_http_client() -> Generator[mock.Mock, None, None]:
    """Mock HTTP client for testing."""
    with mock.patch("httpx.AsyncClient") as mock_client:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transcript": "hey atlas, what's the weather",
            "confidence": 0.95,
            "language": "en",
        }
        mock_client.return_value.post.return_value = mock_response
        yield mock_client.return_value


@pytest.fixture
def mock_file_upload() -> Generator[mock.Mock, None, None]:
    """Mock file upload for testing."""
    with mock.patch("fastapi.UploadFile") as mock_file:
        mock_file.return_value.filename = "test_audio.wav"
        mock_file.return_value.content_type = "audio/wav"
        mock_file.return_value.read.return_value = b"mock audio data"
        yield mock_file.return_value
