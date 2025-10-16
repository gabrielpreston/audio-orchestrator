"""Test configuration for services.orchestrator module."""

from collections.abc import Generator
from typing import Any
from unittest import mock

import pytest


@pytest.fixture
def mock_llm_client() -> Generator[mock.Mock, None, None]:
    """Mock LLM client for testing."""
    with mock.patch("httpx.AsyncClient") as mock_client:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "I'll check the weather for you.",
                        "role": "assistant",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
        }
        mock_client.return_value.post.return_value = mock_response
        yield mock_client.return_value


@pytest.fixture
def mock_tts_client() -> Generator[mock.Mock, None, None]:
    """Mock TTS client for testing."""
    with mock.patch("httpx.AsyncClient") as mock_client:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.content = b"mock audio data"
        mock_response.headers = {"Content-Type": "audio/wav"}
        mock_client.return_value.post.return_value = mock_response
        yield mock_client.return_value


@pytest.fixture
def mock_mcp_client() -> Generator[mock.Mock, None, None]:
    """Mock MCP client for testing."""
    with mock.patch("mcp.Client") as mock_client:
        mock_client.return_value.call_tool.return_value = {
            "success": True,
            "result": {
                "weather": "sunny",
                "temperature": "75°F",
                "location": "San Francisco",
            },
        }
        yield mock_client.return_value


@pytest.fixture
def test_orchestration_request() -> dict[str, Any]:
    """Provide test orchestration request data."""
    return {
        "transcript": "hey atlas, what's the weather like today?",
        "user_id": "123456789",
        "guild_id": "987654321",
        "correlation_id": "test-123",
    }


@pytest.fixture
def test_orchestration_response() -> dict[str, Any]:
    """Provide test orchestration response data."""
    return {
        "response": "The weather today is sunny with a temperature of 75°F in San Francisco.",
        "tts_url": "http://tts:7000/synthesize",
        "correlation_id": "test-123",
        "tools_used": ["weather_check"],
        "confidence": 0.95,
    }


@pytest.fixture
def test_mcp_tool_call() -> dict[str, Any]:
    """Provide test MCP tool call data."""
    return {
        "tool": "weather_check",
        "parameters": {"location": "San Francisco", "date": "today"},
        "correlation_id": "test-123",
    }


@pytest.fixture
def test_mcp_tool_response() -> dict[str, Any]:
    """Provide test MCP tool response data."""
    return {
        "success": True,
        "result": {
            "weather": "sunny",
            "temperature": "75°F",
            "location": "San Francisco",
            "humidity": "60%",
        },
        "correlation_id": "test-123",
    }


@pytest.fixture
def mock_audio_processor() -> Generator[mock.Mock, None, None]:
    """Mock audio processor for testing."""
    with mock.patch("librosa.load") as mock_load:
        import numpy as np

        mock_audio = np.random.randn(22050)  # 1 second of audio at 22.05kHz
        mock_sr = 22050
        mock_load.return_value = (mock_audio, mock_sr)
        yield mock_load


@pytest.fixture
def test_audio_data() -> bytes:
    """Provide test audio data for orchestration testing."""
    return b"mock audio data for orchestration"


@pytest.fixture
def mock_file_system() -> Generator[dict[str, mock.Mock], None, None]:
    """Mock file system operations for testing."""
    with (
        mock.patch("pathlib.Path.write_bytes") as mock_write,
        mock.patch("pathlib.Path.exists") as mock_exists,
        mock.patch("pathlib.Path.mkdir") as mock_mkdir,
    ):
        mock_exists.return_value = False
        yield {"write_bytes": mock_write, "exists": mock_exists, "mkdir": mock_mkdir}
