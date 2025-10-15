"""Test configuration for services.discord module."""

from collections.abc import Generator
from typing import Any
from unittest import mock

import discord
import pytest

from services.common.service_configs import DiscordConfig


@pytest.fixture
def mock_discord_client() -> Generator[mock.Mock, None, None]:
    """Mock Discord client for testing."""
    with mock.patch("discord.Client") as mock_client:
        # Configure mock client
        mock_client.return_value.user = mock.Mock(id=123456789)
        mock_client.return_value.guilds = []
        mock_client.return_value.voice_clients = []
        yield mock_client.return_value


@pytest.fixture
def mock_voice_client() -> Generator[mock.Mock, None, None]:
    """Mock Discord voice client for testing."""
    mock_voice = mock.Mock(spec=discord.VoiceClient)
    mock_voice.channel = mock.Mock(id=987654321)
    mock_voice.is_connected.return_value = True
    mock_voice.is_playing.return_value = False
    mock_voice.play = mock.Mock()
    mock_voice.stop = mock.Mock()
    mock_voice.disconnect = mock.Mock()
    yield mock_voice


@pytest.fixture
def mock_voice_receiver() -> Generator[mock.Mock, None, None]:
    """Mock voice receiver for testing."""
    with mock.patch("discord.ext.voice_recv.VoiceRecvClient") as mock_receiver:
        mock_receiver.return_value.listen.return_value = mock.AsyncMock()
        yield mock_receiver.return_value


@pytest.fixture
def mock_audio_source() -> Generator[mock.Mock, None, None]:
    """Mock audio source for testing."""
    mock_source = mock.Mock()
    mock_source.read.return_value = b"mock audio data"
    mock_source.cleanup = mock.Mock()
    yield mock_source


@pytest.fixture
def mock_wake_word_detector() -> Generator[mock.Mock, None, None]:
    """Mock wake word detector for testing."""
    with mock.patch("openwakeword.Model") as mock_detector:
        mock_detector.return_value.predict.return_value = {"hey atlas": 0.8, "ok atlas": 0.6}
        yield mock_detector.return_value


@pytest.fixture
def mock_stt_client() -> Generator[mock.Mock, None, None]:
    """Mock STT client for testing."""
    with mock.patch("httpx.AsyncClient") as mock_client:
        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "transcript": "hey atlas, what's the weather",
            "confidence": 0.95,
            "language": "en",
        }
        mock_response.status_code = 200
        mock_client.return_value.post.return_value = mock_response
        yield mock_client.return_value


@pytest.fixture
def mock_orchestrator_client() -> Generator[mock.Mock, None, None]:
    """Mock orchestrator client for testing."""
    with mock.patch("httpx.AsyncClient") as mock_client:
        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "response": "The weather is sunny today",
            "tts_url": "http://tts:7000/synthesize",
            "correlation_id": "test-123",
        }
        mock_response.status_code = 200
        mock_client.return_value.post.return_value = mock_response
        yield mock_client.return_value


@pytest.fixture
def mock_mcp_client() -> Generator[mock.Mock, None, None]:
    """Mock MCP client for testing."""
    with mock.patch("mcp.Client") as mock_client:
        mock_client.return_value.call_tool.return_value = {
            "success": True,
            "result": "Tool executed successfully",
        }
        yield mock_client.return_value


@pytest.fixture
def test_discord_config() -> DiscordConfig:
    """Provide test Discord configuration."""
    return DiscordConfig(
        token="test-token",
        guild_id=123456789,
        voice_channel_id=987654321,
        intents=["guilds", "voice_states"],
        auto_join=False,
    )


@pytest.fixture
def mock_voice_data() -> bytes:
    """Provide mock voice data for testing."""
    # Simulate 1 second of 48kHz mono 16-bit PCM audio
    return b"\x00" * 96000  # 48kHz * 2 bytes per sample * 1 second


@pytest.fixture
def mock_audio_segment() -> dict[str, Any]:
    """Provide mock audio segment data for testing."""
    return {
        "data": b"mock audio data",
        "sample_rate": 48000,
        "channels": 1,
        "duration": 1.0,
        "timestamp": 1234567890.0,
    }
