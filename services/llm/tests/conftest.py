"""Test configuration for services.llm module."""

from collections.abc import Generator
from typing import Any
from unittest import mock

import pytest


@pytest.fixture
def mock_llama_model() -> Generator[mock.Mock, None, None]:
    """Mock Llama model for testing."""
    with mock.patch("llama_cpp.Llama") as mock_model:
        # Configure mock model
        mock_model.return_value.create_completion.return_value = {
            "choices": [
                {
                    "text": "The weather is sunny today with a temperature of 75°F.",
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
        }
        yield mock_model.return_value


@pytest.fixture
def mock_http_client() -> Generator[mock.Mock, None, None]:
    """Mock HTTP client for testing."""
    with mock.patch("httpx.AsyncClient") as mock_client:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "The weather is sunny today with a temperature of 75°F.",
                        "role": "assistant",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
        }
        mock_client.return_value.post.return_value = mock_response
        yield mock_client.return_value


@pytest.fixture
def test_chat_request() -> dict[str, Any]:
    """Provide test chat request data."""
    return {
        "messages": [{"role": "user", "content": "What's the weather like today?"}],
        "model": "llama-2-7b",
        "temperature": 0.7,
        "max_tokens": 100,
    }


@pytest.fixture
def test_chat_response() -> dict[str, Any]:
    """Provide test chat response data."""
    return {
        "choices": [
            {
                "message": {
                    "content": "The weather is sunny today with a temperature of 75°F.",
                    "role": "assistant",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
        "model": "llama-2-7b",
    }


@pytest.fixture
def test_completion_request() -> dict[str, Any]:
    """Provide test completion request data."""
    return {
        "prompt": "The weather today is",
        "model": "llama-2-7b",
        "temperature": 0.7,
        "max_tokens": 50,
    }


@pytest.fixture
def test_completion_response() -> dict[str, Any]:
    """Provide test completion response data."""
    return {
        "choices": [{"text": "sunny with a temperature of 75°F.", "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
        "model": "llama-2-7b",
    }


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
def test_tts_request() -> dict[str, Any]:
    """Provide test TTS request data."""
    return {
        "text": "The weather is sunny today",
        "voice": "en_US-amy-medium",
        "format": "wav",
        "sample_rate": 22050,
    }


@pytest.fixture
def test_tts_response() -> bytes:
    """Provide test TTS response data."""
    return b"mock audio data for TTS"
