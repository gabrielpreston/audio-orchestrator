"""Component tests for AudioProcessorClient."""

import base64
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from services.discord.audio import PCMFrame
from services.discord.audio_processor_client import AudioProcessorClient
from services.common.resilient_http import ServiceUnavailableError


@pytest.mark.component
@pytest.mark.asyncio
class TestAudioProcessorClient:
    """Component tests for AudioProcessorClient."""

    @pytest.fixture
    def mock_resilient_client(self):
        """Create mock ResilientHTTPClient."""
        mock_client = AsyncMock()
        mock_client.post_with_retry = AsyncMock()
        mock_client.check_health = AsyncMock(return_value=True)
        mock_client.close = AsyncMock()
        return mock_client

    @pytest.fixture
    def sample_pcm_frame(self, sample_pcm_audio):
        """Create sample PCMFrame for testing."""
        return PCMFrame(
            pcm=sample_pcm_audio,
            timestamp=1000.0,
            rms=0.5,
            duration=0.03,
            sequence=1,
            sample_rate=48000,
        )

    @patch("services.discord.audio_processor_client.create_resilient_client")
    async def test_process_frame_success(
        self, mock_factory, mock_resilient_client, sample_pcm_frame
    ):
        """Test frame processing with successful response."""
        mock_factory.return_value = mock_resilient_client

        # Create processed PCM data (base64 encoded)
        processed_pcm = sample_pcm_frame.pcm + b"_processed"
        processed_pcm_b64 = base64.b64encode(processed_pcm).decode()

        # Configure mock response
        response = Mock(spec=httpx.Response)
        response.status_code = 200
        response.json = Mock(
            return_value={
                "success": True,
                "pcm": processed_pcm_b64,
                "processing_time_ms": 10,
            }
        )
        mock_resilient_client.post_with_retry.return_value = response

        # Create client and test
        client = AudioProcessorClient(base_url="http://test-audio:9100")
        result = await client.process_frame(sample_pcm_frame)

        # Verify results
        assert result is not None
        assert result.pcm == processed_pcm
        assert result.timestamp == sample_pcm_frame.timestamp
        assert result.rms == sample_pcm_frame.rms
        assert result.duration == sample_pcm_frame.duration
        assert result.sequence == sample_pcm_frame.sequence
        assert result.sample_rate == sample_pcm_frame.sample_rate

        # Verify request was made correctly
        mock_resilient_client.post_with_retry.assert_called_once()
        call_args = mock_resilient_client.post_with_retry.call_args
        assert call_args[0][0] == "/process/frame"
        assert "json" in call_args[1]
        assert (
            call_args[1]["json"]["pcm"]
            == base64.b64encode(sample_pcm_frame.pcm).decode()
        )

        await client.close()

    @patch("services.discord.audio_processor_client.create_resilient_client")
    async def test_process_frame_service_unavailable(
        self, mock_factory, mock_resilient_client, sample_pcm_frame
    ):
        """Test circuit breaker behavior when service is unavailable."""
        mock_factory.return_value = mock_resilient_client

        # Configure mock to raise ServiceUnavailableError
        mock_resilient_client.post_with_retry.side_effect = ServiceUnavailableError(
            "Circuit breaker open"
        )

        # Create client and test
        client = AudioProcessorClient(base_url="http://test-audio:9100")
        result = await client.process_frame(sample_pcm_frame)

        # Verify None is returned
        assert result is None

        await client.close()

    @patch("services.discord.audio_processor_client.create_resilient_client")
    async def test_process_frame_error_response(
        self, mock_factory, mock_resilient_client, sample_pcm_frame
    ):
        """Test error response handling."""
        mock_factory.return_value = mock_resilient_client

        # Configure mock response with success=False
        response = Mock(spec=httpx.Response)
        response.status_code = 200
        response.json = Mock(
            return_value={"success": False, "error": "Processing failed"}
        )
        mock_resilient_client.post_with_retry.return_value = response

        # Create client and test
        client = AudioProcessorClient(base_url="http://test-audio:9100")
        result = await client.process_frame(sample_pcm_frame)

        # Verify None is returned
        assert result is None

        await client.close()

    @patch("services.discord.audio_processor_client.create_resilient_client")
    async def test_process_frame_non_200_status(
        self, mock_factory, mock_resilient_client, sample_pcm_frame
    ):
        """Test non-200 status code handling."""
        mock_factory.return_value = mock_resilient_client

        # Configure mock response with non-200 status
        response = Mock(spec=httpx.Response)
        response.status_code = 500
        mock_resilient_client.post_with_retry.return_value = response

        # Create client and test
        client = AudioProcessorClient(base_url="http://test-audio:9100")
        result = await client.process_frame(sample_pcm_frame)

        # Verify None is returned
        assert result is None

        await client.close()

    @patch("services.discord.audio_processor_client.create_resilient_client")
    async def test_process_segment_success(
        self, mock_factory, mock_resilient_client, sample_audio_segment_fixture
    ):
        """Test segment processing with successful response."""
        mock_factory.return_value = mock_resilient_client

        # Create processed PCM data (base64 encoded)
        processed_pcm = sample_audio_segment_fixture.pcm + b"_processed"
        processed_pcm_b64 = base64.b64encode(processed_pcm).decode()

        # Configure mock response
        response = Mock(spec=httpx.Response)
        response.status_code = 200
        response.json = Mock(
            return_value={
                "success": True,
                "pcm": processed_pcm_b64,
                "processing_time_ms": 20,
            }
        )
        mock_resilient_client.post_with_retry.return_value = response

        # Create client and test
        client = AudioProcessorClient(base_url="http://test-audio:9100")
        result = await client.process_segment(sample_audio_segment_fixture)

        # Verify results
        assert result is not None
        assert result.pcm == processed_pcm
        assert result.user_id == sample_audio_segment_fixture.user_id
        assert result.start_timestamp == sample_audio_segment_fixture.start_timestamp
        assert result.end_timestamp == sample_audio_segment_fixture.end_timestamp
        assert result.correlation_id == sample_audio_segment_fixture.correlation_id
        assert result.frame_count == sample_audio_segment_fixture.frame_count
        assert result.sample_rate == sample_audio_segment_fixture.sample_rate

        # Verify request was made correctly
        mock_resilient_client.post_with_retry.assert_called_once()
        call_args = mock_resilient_client.post_with_retry.call_args
        assert call_args[0][0] == "/process/segment"
        assert "json" in call_args[1]
        assert call_args[1]["json"]["user_id"] == sample_audio_segment_fixture.user_id
        assert (
            call_args[1]["json"]["correlation_id"]
            == sample_audio_segment_fixture.correlation_id
        )

        await client.close()

    @patch("services.discord.audio_processor_client.create_resilient_client")
    async def test_process_segment_service_unavailable(
        self, mock_factory, mock_resilient_client, sample_audio_segment_fixture
    ):
        """Test service unavailable for segment processing."""
        mock_factory.return_value = mock_resilient_client

        # Configure mock to raise ServiceUnavailableError
        mock_resilient_client.post_with_retry.side_effect = ServiceUnavailableError(
            "Circuit breaker open"
        )

        # Create client and test
        client = AudioProcessorClient(base_url="http://test-audio:9100")
        result = await client.process_segment(sample_audio_segment_fixture)

        # Verify None is returned
        assert result is None

        await client.close()

    @patch("services.discord.audio_processor_client.create_resilient_client")
    async def test_enhance_audio_success(
        self, mock_factory, mock_resilient_client, sample_pcm_audio
    ):
        """Test audio enhancement endpoint with binary content."""
        mock_factory.return_value = mock_resilient_client

        # Create enhanced audio data
        enhanced_audio = sample_pcm_audio + b"_enhanced"

        # Configure mock response
        response = Mock(spec=httpx.Response)
        response.status_code = 200
        response.content = enhanced_audio
        mock_resilient_client.post_with_retry.return_value = response

        # Create client and test
        client = AudioProcessorClient(base_url="http://test-audio:9100")
        correlation_id = "test-correlation-456"
        result = await client.enhance_audio(
            sample_pcm_audio, correlation_id=correlation_id
        )

        # Verify results
        assert result == enhanced_audio

        # Verify request was made correctly
        mock_resilient_client.post_with_retry.assert_called_once()
        call_args = mock_resilient_client.post_with_retry.call_args
        assert call_args[0][0] == "/enhance/audio"
        assert call_args[1]["content"] == sample_pcm_audio
        assert call_args[1]["headers"]["X-Correlation-ID"] == correlation_id

        await client.close()

    @patch("services.discord.audio_processor_client.create_resilient_client")
    async def test_enhance_audio_fallback(
        self, mock_factory, mock_resilient_client, sample_pcm_audio
    ):
        """Test fallback to original audio on failure."""
        mock_factory.return_value = mock_resilient_client

        # Configure mock to raise ServiceUnavailableError
        mock_resilient_client.post_with_retry.side_effect = ServiceUnavailableError(
            "Circuit breaker open"
        )

        # Create client and test
        client = AudioProcessorClient(base_url="http://test-audio:9100")
        result = await client.enhance_audio(sample_pcm_audio)

        # Verify original audio is returned
        assert result == sample_pcm_audio

        await client.close()

    @patch("services.discord.audio_processor_client.create_resilient_client")
    async def test_health_check(self, mock_factory, mock_resilient_client):
        """Test health check endpoint delegation."""
        mock_factory.return_value = mock_resilient_client
        mock_resilient_client.check_health.return_value = True

        # Create client and test
        client = AudioProcessorClient(base_url="http://test-audio:9100")
        result = await client.health_check()

        # Verify results
        assert result is True
        mock_resilient_client.check_health.assert_called_once()

        await client.close()

    @patch("services.discord.audio_processor_client.create_resilient_client")
    async def test_base64_encoding(
        self, mock_factory, mock_resilient_client, sample_pcm_frame
    ):
        """Test PCM data encoding/decoding correctness (round-trip validation)."""
        mock_factory.return_value = mock_resilient_client

        # Create processed PCM data (base64 encoded)
        processed_pcm = sample_pcm_frame.pcm
        processed_pcm_b64 = base64.b64encode(processed_pcm).decode()

        # Configure mock response
        response = Mock(spec=httpx.Response)
        response.status_code = 200
        response.json = Mock(return_value={"success": True, "pcm": processed_pcm_b64})
        mock_resilient_client.post_with_retry.return_value = response

        # Create client and test
        client = AudioProcessorClient(base_url="http://test-audio:9100")
        result = await client.process_frame(sample_pcm_frame)

        # Verify base64 round-trip
        assert result is not None
        assert result.pcm == processed_pcm

        # Verify encoding in request
        call_args = mock_resilient_client.post_with_retry.call_args
        request_pcm_b64 = call_args[1]["json"]["pcm"]
        assert request_pcm_b64 == base64.b64encode(sample_pcm_frame.pcm).decode()
        # Verify decoding in response
        decoded = base64.b64decode(request_pcm_b64)
        assert decoded == sample_pcm_frame.pcm

        await client.close()

    @patch("services.discord.audio_processor_client.create_resilient_client")
    async def test_correlation_id_propagation(
        self, mock_factory, mock_resilient_client, sample_pcm_audio
    ):
        """Test correlation ID in headers for enhance_audio."""
        mock_factory.return_value = mock_resilient_client

        # Configure mock response
        response = Mock(spec=httpx.Response)
        response.status_code = 200
        response.content = sample_pcm_audio
        mock_resilient_client.post_with_retry.return_value = response

        # Create client and test
        client = AudioProcessorClient(base_url="http://test-audio:9100")
        correlation_id = "test-correlation-789"
        await client.enhance_audio(sample_pcm_audio, correlation_id=correlation_id)

        # Verify correlation ID in headers
        call_args = mock_resilient_client.post_with_retry.call_args
        assert call_args[1]["headers"]["X-Correlation-ID"] == correlation_id

        await client.close()
