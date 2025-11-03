"""Shared fixtures for audio pipeline component tests."""

from unittest.mock import AsyncMock, Mock

import pytest

from services.common.surfaces.types import AudioSegment, PCMFrame
from services.common.resilient_http import ResilientHTTPClient


# AudioProcessorClient fixture removed - functionality now in AudioProcessingCore


@pytest.fixture
def mock_resilient_http_client():
    """Mock ResilientHTTPClient with circuit breaker simulation."""
    client = AsyncMock(spec=ResilientHTTPClient)
    client.post_with_retry = AsyncMock()
    client.check_health = AsyncMock(return_value=True)
    client.close = AsyncMock()

    # Add circuit breaker simulation methods
    def get_circuit_stats():
        """Get circuit breaker stats."""
        return {"state": "closed", "available": True}

    client.get_circuit_stats = Mock(side_effect=get_circuit_stats)
    return client


@pytest.fixture
def mock_transcription_response():
    """Mock STT service response."""
    response = Mock()
    response.status_code = 200
    response.json = Mock(
        return_value={
            "text": "test transcript",
            "confidence": 0.95,
            "language": "en",
        }
    )
    response.aclose = AsyncMock()
    return response


@pytest.fixture
def mock_audio_processor_response():
    """Mock audio processor response data structure (legacy fixture, kept for compatibility)."""
    response_data = {
        "success": True,
        "pcm": "",  # Base64 encoded PCM will be set in tests
        "processing_time_ms": 10,
    }
    return response_data


@pytest.fixture
def sample_pcm_frame(sample_pcm_audio):
    """Realistic PCMFrame data (extends sample_pcm_audio fixture)."""
    import time

    return PCMFrame(
        pcm=sample_pcm_audio,
        timestamp=time.time(),
        rms=0.5,
        duration=0.03,
        sequence=1,
        sample_rate=48000,
    )


@pytest.fixture
def sample_processed_frame(sample_pcm_audio):
    """Realistic processed PCMFrame from audio processor."""
    import time

    return PCMFrame(
        pcm=sample_pcm_audio + b"_processed",
        timestamp=time.time(),
        rms=0.6,
        duration=0.03,
        sequence=1,
        sample_rate=48000,
    )


@pytest.fixture
def sample_audio_segment_from_frame(sample_pcm_frame):
    """Create AudioSegment from PCMFrame."""
    return AudioSegment(
        user_id="12345",
        pcm=sample_pcm_frame.pcm,
        sample_rate=sample_pcm_frame.sample_rate,
        start_timestamp=sample_pcm_frame.timestamp,
        end_timestamp=sample_pcm_frame.timestamp + sample_pcm_frame.duration,
        correlation_id=f"frame-{12345}-{int(sample_pcm_frame.timestamp)}",
        frame_count=1,
    )
