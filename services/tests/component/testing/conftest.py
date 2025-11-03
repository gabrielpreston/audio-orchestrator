"""Fixtures for testing service component tests."""

import base64
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

# Import shared fixtures
from services.tests.fixtures.testing.testing_fixtures import (  # noqa: F401
    mock_audio_preprocessor_response,
    mock_orchestrator_response,
    mock_orchestrator_response_error,
    mock_orchestrator_response_no_audio,
    mock_stt_response,
    mock_tts_response,
    sample_wav_file,
)


@pytest.fixture
def mock_httpx_client():
    """Create mock httpx.AsyncClient for component tests."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    return mock_client


@pytest.fixture
def mock_preprocessor_response(mock_audio_preprocessor_response: bytes):  # noqa: F811
    """Mock audio preprocessor HTTP response."""
    response = Mock(spec=httpx.Response)
    response.status_code = 200
    response.content = mock_audio_preprocessor_response
    response.raise_for_status = Mock()
    return response


@pytest.fixture
def mock_stt_http_response(mock_stt_response: dict):  # noqa: F811
    """Mock STT HTTP response."""
    response = Mock(spec=httpx.Response)
    response.status_code = 200

    # Create a callable that returns the actual dict
    def json_impl():
        return mock_stt_response

    response.json = json_impl
    response.raise_for_status = Mock(return_value=None)
    return response


@pytest.fixture
def mock_orchestrator_http_response(mock_orchestrator_response: dict):  # noqa: F811
    """Mock orchestrator HTTP response."""
    response = Mock(spec=httpx.Response)
    response.status_code = 200
    response.json = Mock(return_value=mock_orchestrator_response)
    response.raise_for_status = Mock()
    return response


@pytest.fixture
def mock_orchestrator_http_response_no_audio(mock_orchestrator_response_no_audio: dict):  # noqa: F811
    """Mock orchestrator HTTP response without audio."""
    response = Mock(spec=httpx.Response)
    response.status_code = 200
    response.json = Mock(return_value=mock_orchestrator_response_no_audio)
    response.raise_for_status = Mock()
    return response


@pytest.fixture
def mock_tts_http_response(mock_tts_response: dict):  # noqa: F811
    """Mock TTS HTTP response."""
    response = Mock(spec=httpx.Response)
    response.status_code = 200
    response.json = Mock(return_value=mock_tts_response)
    response.content = base64.b64decode(mock_tts_response["audio"])
    response.raise_for_status = Mock()
    return response
