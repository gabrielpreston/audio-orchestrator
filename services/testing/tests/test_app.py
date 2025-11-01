"""Unit tests for testing service app."""

import base64
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

# Import fixtures
from services.tests.fixtures.integration_fixtures import (  # noqa: F401
    sample_audio_bytes,
)

from services.testing.app import (
    _check_audio_preprocessor_health,
    _check_orchestrator_health,
    _check_service_health,
    _check_stt_health,
    _check_tts_health,
    create_gradio_interface,
    run_pipeline,
)


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestPipeline:
    """Unit tests for run_pipeline function."""

    @pytest.fixture
    def sample_audio_file(self, tmp_path: Path):
        """Create sample audio file for testing."""
        # Create minimal WAV file bytes for testing
        # WAV header + minimal data
        wav_bytes = (
            b"RIFF"
            b"\x24\x00\x00\x00"  # File size - 36
            b"WAVE"
            b"fmt \x10\x00\x00\x00"  # fmt chunk
            b"\x01\x00\x01\x00"  # Audio format (PCM), channels (1)
            b"\x40\x1f\x00\x00"  # Sample rate (8000)
            b"\x80\x3e\x00\x00"  # Byte rate
            b"\x02\x00\x10\x00"  # Block align, bits per sample
            b"data"
            b"\x00\x00\x00\x00"  # Data size (0 - minimal)
        )
        audio_file = tmp_path / "test_audio.wav"
        audio_file.write_bytes(wav_bytes)
        return str(audio_file)

    @patch("services.testing.app.client")
    async def test_pipeline_audio_with_preprocessing_success(
        self, mock_client_module, sample_audio_file
    ):
        """Test pipeline with audio input and successful preprocessing."""

        # Mock preprocessing response
        preprocess_response = Mock(spec=httpx.Response)
        preprocess_response.status_code = 200
        preprocess_response.content = b"enhanced_audio_bytes"
        preprocess_response.raise_for_status = Mock()

        # Mock STT response
        stt_response = Mock(spec=httpx.Response)
        stt_response.status_code = 200
        stt_response.json = Mock(return_value={"text": "test transcript"})
        stt_response.raise_for_status = Mock()

        # Mock orchestrator response with audio
        orchestrator_response = Mock(spec=httpx.Response)
        orchestrator_response.status_code = 200
        audio_bytes = b"test_audio_bytes"
        audio_b64 = base64.b64encode(audio_bytes).decode()
        orchestrator_response.json = Mock(
            return_value={
                "success": True,
                "response_text": "test response",
                "audio_data": audio_b64,
                "audio_format": "wav",
            }
        )
        orchestrator_response.raise_for_status = Mock()

        # Configure mock client responses
        mock_client_module.post = AsyncMock(
            side_effect=[preprocess_response, stt_response, orchestrator_response]
        )

        # Execute
        transcript, response, audio_path = await run_pipeline(
            audio=sample_audio_file, text_input="", voice_preset="v2/en_speaker_0"
        )

        # Verify
        assert transcript == "test transcript"
        assert response == "test response"
        assert audio_path is not None
        assert Path(audio_path).exists()

        # Cleanup
        if audio_path and Path(audio_path).exists():
            Path(audio_path).unlink()

    @patch("services.testing.app.client")
    async def test_pipeline_audio_with_preprocessing_failure(
        self, mock_client_module, sample_audio_file
    ):
        """Test pipeline with audio input when preprocessing fails (fallback to raw)."""

        # Mock STT response (with raw audio)
        stt_response = Mock(spec=httpx.Response)
        stt_response.status_code = 200
        stt_response.json = Mock(return_value={"text": "test transcript"})
        stt_response.raise_for_status = Mock()

        # Mock orchestrator response
        orchestrator_response = Mock(spec=httpx.Response)
        orchestrator_response.status_code = 200
        orchestrator_response.json = Mock(
            return_value={
                "success": True,
                "response_text": "test response",
            }
        )
        orchestrator_response.raise_for_status = Mock()

        # Mock TTS fallback response
        tts_response = Mock(spec=httpx.Response)
        tts_response.status_code = 200
        audio_bytes = b"test_tts_audio"
        audio_b64 = base64.b64encode(audio_bytes).decode()
        tts_response.json = Mock(return_value={"audio": audio_b64})
        tts_response.raise_for_status = Mock()

        # Configure mock to handle multiple post calls
        call_count = 0

        async def mock_post_sequence(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Use dictionary lookup for call count mapping
            responses: dict[int, Mock] = {
                2: stt_response,  # STT succeeds
                3: orchestrator_response,  # Orchestrator succeeds
                4: tts_response,  # TTS fallback (no audio from orchestrator)
            }
            if call_count == 1:
                raise httpx.HTTPStatusError("Error", request=Mock(), response=Mock())
            return responses.get(call_count)

        mock_client_module.post = AsyncMock(side_effect=mock_post_sequence)

        # Execute
        transcript, response, audio_path = await run_pipeline(
            audio=sample_audio_file, text_input="", voice_preset="v2/en_speaker_0"
        )

        # Verify
        assert transcript == "test transcript"
        assert response == "test response"
        assert audio_path is not None  # TTS fallback should create audio

        # Cleanup
        if audio_path and Path(audio_path).exists():
            Path(audio_path).unlink()

    @patch("services.testing.app.client")
    async def test_pipeline_text_input_bypass_stt(self, mock_client_module):
        """Test pipeline with text input bypassing STT."""
        # Mock orchestrator response
        orchestrator_response = Mock(spec=httpx.Response)
        orchestrator_response.status_code = 200
        orchestrator_response.json = Mock(
            return_value={
                "success": True,
                "response_text": "test response",
                "audio_data": base64.b64encode(b"test_audio").decode(),
                "audio_format": "wav",
            }
        )
        orchestrator_response.raise_for_status = Mock()

        mock_client_module.post = AsyncMock(return_value=orchestrator_response)

        # Execute
        transcript, response, audio_path = await run_pipeline(
            audio=None, text_input="test text input", voice_preset="v2/en_speaker_0"
        )

        # Verify
        assert transcript == "test text input"
        assert response == "test response"
        # Verify STT was not called (only orchestrator called)
        assert mock_client_module.post.call_count == 1

    @patch("services.testing.app.client")
    async def test_pipeline_empty_input(self, mock_client_module):
        """Test pipeline with empty input."""
        # Execute
        transcript, response, audio_path = await run_pipeline(
            audio=None, text_input="", voice_preset="v2/en_speaker_0"
        )

        # Verify
        assert transcript == "No input provided"
        assert response == "No response generated"
        assert audio_path is None
        # Verify no HTTP calls were made
        mock_client_module.post.assert_not_called()

    @patch("services.testing.app.client")
    async def test_pipeline_stt_failure(self, mock_client_module, sample_audio_file):
        """Test pipeline when STT fails."""
        # Mock preprocessing success
        preprocess_response = Mock(spec=httpx.Response)
        preprocess_response.status_code = 200
        preprocess_response.content = b"enhanced_audio"
        preprocess_response.raise_for_status = Mock()

        # Mock STT failure - raises exception when raise_for_status is called
        stt_response = Mock(spec=httpx.Response)
        stt_response.status_code = 500
        stt_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "STT Error", request=Mock(), response=Mock()
            )
        )

        # Mock orchestrator and TTS (will be called even though STT failed, since transcript="Transcription failed" is not empty)
        orchestrator_response = Mock(spec=httpx.Response)
        orchestrator_response.status_code = 200
        orchestrator_response.json = Mock(
            return_value={"success": True, "response_text": "Error response"}
        )
        orchestrator_response.raise_for_status = Mock()

        tts_response = Mock(spec=httpx.Response)
        tts_response.status_code = 200
        tts_response.json = Mock(
            return_value={"audio": base64.b64encode(b"audio").decode()}
        )
        tts_response.raise_for_status = Mock()

        call_count = 0

        async def mock_post_sequence(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Use dictionary lookup for call count mapping
            responses: dict[int, Mock] = {
                1: preprocess_response,
                2: stt_response,  # This will raise when raise_for_status is called
                3: orchestrator_response,
                4: tts_response,
            }
            return responses.get(call_count)

        mock_client_module.post = AsyncMock(side_effect=mock_post_sequence)

        # Execute
        transcript, response, audio_path = await run_pipeline(
            audio=sample_audio_file, text_input="", voice_preset="v2/en_speaker_0"
        )

        # Verify
        assert transcript == "Transcription failed"
        # Note: Orchestrator and TTS are still called even when STT fails, since transcript="Transcription failed" is not empty
        assert mock_client_module.post.call_count >= 2  # At least Preprocess + STT

    @patch("services.testing.app.client")
    async def test_pipeline_orchestrator_failure(self, mock_client_module):
        """Test pipeline when orchestrator fails."""
        # Mock orchestrator failure
        orchestrator_response = Mock(spec=httpx.Response)
        orchestrator_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "Orchestrator Error", request=Mock(), response=Mock()
            )
        )

        mock_client_module.post = AsyncMock(return_value=orchestrator_response)

        # Execute
        transcript, response, audio_path = await run_pipeline(
            audio=None, text_input="test input", voice_preset="v2/en_speaker_0"
        )

        # Verify
        assert transcript == "test input"
        assert "Orchestration HTTP error" in response or "Orchestration" in response
        assert audio_path is None

    @patch("services.testing.app.client")
    async def test_pipeline_orchestrator_error_response(self, mock_client_module):
        """Test pipeline when orchestrator returns error in response."""
        # Mock orchestrator response with success=False
        orchestrator_response = Mock(spec=httpx.Response)
        orchestrator_response.status_code = 200
        orchestrator_response.json = Mock(
            return_value={
                "success": False,
                "error": "Orchestration failed",
            }
        )
        orchestrator_response.raise_for_status = Mock()

        mock_client_module.post = AsyncMock(return_value=orchestrator_response)

        # Execute
        transcript, response, audio_path = await run_pipeline(
            audio=None, text_input="test input", voice_preset="v2/en_speaker_0"
        )

        # Verify
        assert transcript == "test input"
        assert "Orchestration failed" in response
        assert audio_path is None

    @patch("services.testing.app.client")
    @patch("tempfile.gettempdir")
    async def test_pipeline_base64_audio_decoding(
        self, mock_tempdir, mock_client_module, tmp_path
    ):
        """Test base64 audio decoding and file saving."""
        mock_tempdir.return_value = str(tmp_path)

        # Mock orchestrator response with base64 audio
        audio_bytes = b"test_audio_data"
        audio_b64 = base64.b64encode(audio_bytes).decode()

        orchestrator_response = Mock(spec=httpx.Response)
        orchestrator_response.status_code = 200
        orchestrator_response.json = Mock(
            return_value={
                "success": True,
                "response_text": "test response",
                "audio_data": audio_b64,
                "audio_format": "wav",
            }
        )
        orchestrator_response.raise_for_status = Mock()

        mock_client_module.post = AsyncMock(return_value=orchestrator_response)

        # Execute
        transcript, response, audio_path = await run_pipeline(
            audio=None, text_input="test input", voice_preset="v2/en_speaker_0"
        )

        # Verify
        assert audio_path is not None
        assert Path(audio_path).exists()
        # Verify file contains decoded audio
        saved_audio = Path(audio_path).read_bytes()
        assert saved_audio == audio_bytes

        # Cleanup
        Path(audio_path).unlink()


@pytest.mark.unit
class TestCreateGradioInterface:
    """Unit tests for create_gradio_interface function."""

    @patch("services.testing.app.GRADIO_AVAILABLE", True)
    @patch("services.testing.app.gr")
    def test_create_gradio_interface_success(self, mock_gr):
        """Test successful Gradio interface creation."""
        mock_interface = Mock()
        mock_gr.Interface.return_value = mock_interface

        result = create_gradio_interface()

        assert result == mock_interface
        mock_gr.Interface.assert_called_once()

    @patch("services.testing.app.GRADIO_AVAILABLE", False)
    def test_create_gradio_interface_unavailable(self):
        """Test Gradio interface creation when Gradio is unavailable."""
        with pytest.raises(ImportError, match="Gradio is not available"):
            create_gradio_interface()


@pytest.mark.unit
@pytest.mark.asyncio
class TestHealthChecks:
    """Unit tests for health check functions."""

    @patch("services.testing.app.client")
    async def test_check_service_health_success(self, mock_client_module):
        """Test successful health check."""
        response = Mock(spec=httpx.Response)
        response.status_code = 200

        mock_client_module.get = AsyncMock(return_value=response)

        result = await _check_service_health("http://test:9000")

        assert result is True
        mock_client_module.get.assert_called_once_with(
            "http://test:9000/health/ready", timeout=5.0
        )

    @patch("services.testing.app.client")
    async def test_check_service_health_failure(self, mock_client_module):
        """Test failed health check (HTTP error)."""
        response = Mock(spec=httpx.Response)
        response.status_code = 503

        mock_client_module.get = AsyncMock(return_value=response)

        result = await _check_service_health("http://test:9000")

        assert result is False

    @patch("services.testing.app.client")
    async def test_check_service_health_exception(self, mock_client_module):
        """Test health check with exception."""
        mock_client_module.get = AsyncMock(side_effect=Exception("Connection error"))

        result = await _check_service_health("http://test:9000")

        assert result is False

    @patch("services.testing.app.client")
    async def test_check_audio_preprocessor_health(self, mock_client_module):
        """Test audio preprocessor health check wrapper."""
        response = Mock(spec=httpx.Response)
        response.status_code = 200
        mock_client_module.get = AsyncMock(return_value=response)

        result = await _check_audio_preprocessor_health()

        assert result is True
        mock_client_module.get.assert_called_once()

    @patch("services.testing.app.client")
    async def test_check_stt_health(self, mock_client_module):
        """Test STT health check wrapper."""
        response = Mock(spec=httpx.Response)
        response.status_code = 200
        mock_client_module.get = AsyncMock(return_value=response)

        result = await _check_stt_health()

        assert result is True
        mock_client_module.get.assert_called_once()

    @patch("services.testing.app.client")
    async def test_check_orchestrator_health(self, mock_client_module):
        """Test orchestrator health check wrapper."""
        response = Mock(spec=httpx.Response)
        response.status_code = 200
        mock_client_module.get = AsyncMock(return_value=response)

        result = await _check_orchestrator_health()

        assert result is True
        mock_client_module.get.assert_called_once()

    @patch("services.testing.app.client")
    async def test_check_tts_health(self, mock_client_module):
        """Test TTS health check wrapper."""
        response = Mock(spec=httpx.Response)
        response.status_code = 200
        mock_client_module.get = AsyncMock(return_value=response)

        result = await _check_tts_health()

        assert result is True
        mock_client_module.get.assert_called_once()
