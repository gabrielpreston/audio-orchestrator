"""TTS test fixtures and configuration."""

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.tests.fixtures.tts.tts_test_helpers import (
    load_tts_baseline_metadata,
    validate_tts_audio_format,
    validate_tts_audio_quality,
)
from services.tests.utils.audio_quality_helpers import (
    create_wav_file,
    generate_test_audio,
)


@pytest.fixture
def tts_baseline_samples() -> dict[str, Path]:
    """Load baseline TTS samples from fixtures."""
    samples_dir = Path(__file__).parent / "samples"
    return {
        "short_phrase": samples_dir / "short_phrase.wav",
        "medium_phrase": samples_dir / "medium_phrase.wav",
        "ssml_sample": samples_dir / "ssml_sample.wav",
        "silence": samples_dir / "silence.wav",
        "low_amplitude": samples_dir / "low_amplitude.wav",
        "high_amplitude": samples_dir / "high_amplitude.wav",
    }


@pytest.fixture
def tts_baseline_metadata(sample_name: str) -> dict[str, Any]:
    """Load baseline sample metadata."""
    samples_dir = Path(__file__).parent / "samples"
    return load_tts_baseline_metadata(samples_dir, sample_name)


@pytest.fixture
def tts_artifacts_dir(test_artifacts_dir: Path) -> Path:
    """Get TTS test artifacts directory."""
    tts_dir = test_artifacts_dir / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)
    return tts_dir


@pytest.fixture
def mock_tts_audio(temp_dir: Path) -> Path:
    """Generate mock TTS audio in temp directory."""
    # Generate synthetic audio
    pcm_data = generate_test_audio(
        duration=1.0,
        sample_rate=22050,
        frequency=440.0,
        amplitude=0.5,
        noise_level=0.0,
    )
    wav_data = create_wav_file(pcm_data, sample_rate=22050, channels=1)

    # Save to temp directory
    audio_file = temp_dir / "mock_tts_audio.wav"
    audio_file.write_bytes(wav_data)
    return audio_file


@pytest.fixture
def tts_test_client() -> Generator[TestClient, None, None]:
    """HTTP client for TTS service testing."""
    # This would be imported from the actual TTS service
    # For now, we'll create a mock client
    from unittest.mock import Mock

    mock_client = Mock()
    mock_client.post.return_value.status_code = 200
    mock_client.post.return_value.content = b"mock audio data"
    mock_client.post.return_value.headers = {"content-type": "audio/wav"}

    yield mock_client


# Helper fixtures for TTS validation
@pytest.fixture
def validate_tts_format():
    """Fixture for TTS format validation."""
    return validate_tts_audio_format


@pytest.fixture
def validate_tts_quality():
    """Fixture for TTS quality validation."""
    return validate_tts_audio_quality
