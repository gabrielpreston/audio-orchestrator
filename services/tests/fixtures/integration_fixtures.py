"""Fixtures for integration tests."""

import base64

import pytest

from services.tests.utils.audio_quality_helpers import (
    create_wav_file,
    generate_test_audio,
)


@pytest.fixture
def sample_audio_bytes() -> bytes:
    """Generate sample audio as bytes for HTTP requests."""
    pcm_data = generate_test_audio(duration=2.0, frequency=440.0, amplitude=0.5)
    return create_wav_file(pcm_data, sample_rate=16000, channels=1)


@pytest.fixture
def base64_audio(sample_audio_bytes: bytes) -> str:
    """Base64-encoded audio for JSON requests."""
    return base64.b64encode(sample_audio_bytes).decode()


@pytest.fixture
def test_transcript() -> str:
    """Sample transcript for testing."""
    return "hello world, this is a test"


@pytest.fixture
def test_auth_token() -> str:
    """Test authentication token."""
    return "test-token"


@pytest.fixture
def test_guild_id() -> str:
    """Test Discord guild ID."""
    return "123456789"


@pytest.fixture
def test_channel_id() -> str:
    """Test Discord channel ID."""
    return "987654321"


@pytest.fixture
def test_user_id() -> str:
    """Test Discord user ID."""
    return "12345"


@pytest.fixture
def test_correlation_id() -> str:
    """Test correlation ID for request tracking."""
    return "test-correlation-1234567890abcdef"
