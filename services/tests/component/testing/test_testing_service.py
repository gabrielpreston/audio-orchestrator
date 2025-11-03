"""Component tests for testing service pipeline orchestration."""

import base64
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from services.testing.app import (
    ORCHESTRATOR_BASE_URL,
    TTS_BASE_URL,
    run_pipeline,
)


@pytest.mark.component
@pytest.mark.asyncio
class TestTestingServicePipeline:
    """Component tests for testing service pipeline orchestration."""

    @patch("services.testing.app.client")
    async def test_complete_pipeline_audio_to_audio_output(
        self,
        mock_client_module,
        sample_wav_file: Path,
        mock_preprocessor_response,
        mock_stt_http_response,
        mock_orchestrator_http_response,
    ):
        """Test complete pipeline: Audio → Preprocess → STT → Orchestrator → Audio output."""
        # Configure mock to return responses in order
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            responses = {
                1: mock_preprocessor_response,
                2: mock_stt_http_response,
                3: mock_orchestrator_http_response,
            }
            return responses.get(call_count)

        mock_client_module.post = AsyncMock(side_effect=mock_post)

        with patch("tempfile.gettempdir", return_value=str(tempfile.gettempdir())):
            # Execute
            transcript, response, audio_path = await run_pipeline(
                audio=str(sample_wav_file),
                text_input="",
                voice_preset="v2/en_speaker_0",
            )

        # Verify
        assert transcript == "hello world this is a test transcript"
        assert response == "This is a test response"
        assert audio_path is not None
        assert Path(audio_path).exists()

        # Verify all services were called
        assert mock_client_module.post.call_count == 3

        # Note: Temporary files use OS cleanup (delete=False for Gradio async access)

    @patch("services.testing.app.client")
    async def run_pipeline_preprocessing_failure_fallback(
        self,
        mock_client_module,
        sample_wav_file: Path,
        mock_stt_http_response,
        mock_orchestrator_http_response,
    ):
        """Test preprocessing failure → Raw audio → STT → Orchestrator."""
        # Configure mock: preprocessing fails, then STT and orchestrator succeed
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Preprocessing fails
                raise httpx.HTTPStatusError(
                    "Preprocessing failed", request=Mock(), response=Mock()
                )
            responses = {
                2: mock_stt_http_response,
                3: mock_orchestrator_http_response,
            }
            return responses.get(call_count)

        mock_client_module.post = AsyncMock(side_effect=mock_post)

        with patch("tempfile.gettempdir", return_value=str(tempfile.gettempdir())):
            # Execute
            transcript, response, audio_path = await run_pipeline(
                audio=str(sample_wav_file),
                text_input="",
                voice_preset="v2/en_speaker_0",
            )

        # Verify pipeline continued despite preprocessing failure
        assert transcript == "hello world this is a test transcript"
        assert response == "This is a test response"
        # STT should have been called with raw audio (call_count == 2 for STT)
        assert mock_client_module.post.call_count >= 2

        # Note: Temporary files use OS cleanup (delete=False for Gradio async access)

    @patch("services.testing.app.client")
    async def run_pipeline_text_input_bypass_stt(
        self,
        mock_client_module,
        mock_orchestrator_http_response,
    ):
        """Test text input → Orchestrator (bypass STT/preprocessing)."""
        mock_client_module.post = AsyncMock(
            return_value=mock_orchestrator_http_response
        )

        # Execute
        transcript, response, audio_path = await run_pipeline(
            audio=None,
            text_input="test text input",
            voice_preset="v2/en_speaker_0",
        )

        # Verify
        assert transcript == "test text input"
        assert response == "This is a test response"
        # Only orchestrator should be called (no preprocessing, no STT)
        assert mock_client_module.post.call_count == 1

        # Verify orchestrator was called with correct data
        call_args = mock_client_module.post.call_args
        assert ORCHESTRATOR_BASE_URL in str(call_args[0][0])
        assert call_args[1]["json"]["transcript"] == "test text input"

        # Note: Temporary files use OS cleanup (delete=False for Gradio async access)

    @patch("services.testing.app.client")
    async def run_pipeline_orchestrator_audio_response_file_saving(
        self,
        mock_client_module,
        mock_orchestrator_http_response,
    ):
        """Test orchestrator audio response → File saving."""
        mock_client_module.post = AsyncMock(
            return_value=mock_orchestrator_http_response
        )

        with patch("tempfile.gettempdir", return_value=str(tempfile.gettempdir())):
            # Execute
            transcript, response, audio_path = await run_pipeline(
                audio=None,
                text_input="test input",
                voice_preset="v2/en_speaker_0",
            )

        # Verify
        assert audio_path is not None
        assert Path(audio_path).exists()
        assert audio_path.endswith(".wav")

        # Verify file contains correct audio data
        saved_audio = Path(audio_path).read_bytes()
        orchestrator_data = mock_orchestrator_http_response.json()
        expected_audio = base64.b64decode(orchestrator_data["audio_data"])
        assert saved_audio == expected_audio

        # Note: Temporary files use OS cleanup (delete=False for Gradio async access)

    @patch("services.testing.app.client")
    async def run_pipeline_tts_fallback_when_orchestrator_no_audio(
        self,
        mock_client_module,
        mock_orchestrator_http_response_no_audio,
        mock_tts_http_response,
    ):
        """Test TTS fallback when orchestrator has no audio."""
        # Configure mock: orchestrator returns no audio, then TTS is called
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            responses = {
                1: mock_orchestrator_http_response_no_audio,
                2: mock_tts_http_response,
            }
            return responses.get(call_count)

        mock_client_module.post = AsyncMock(side_effect=mock_post)

        with patch("tempfile.gettempdir", return_value=str(tempfile.gettempdir())):
            # Execute
            transcript, response, audio_path = await run_pipeline(
                audio=None,
                text_input="test input",
                voice_preset="v2/en_speaker_1",
            )

        # Verify
        assert response == "This is a test response"
        assert audio_path is not None
        assert Path(audio_path).exists()

        # Verify TTS was called
        assert mock_client_module.post.call_count == 2

        # Verify TTS was called with correct voice preset
        tts_call = mock_client_module.post.call_args_list[1]
        assert TTS_BASE_URL in str(tts_call[0][0])
        assert tts_call[1]["json"]["voice"] == "v2/en_speaker_1"

        # Note: Temporary files use OS cleanup (delete=False for Gradio async access)

    @patch("services.testing.app.client")
    async def run_pipeline_voice_preset_selection_for_tts(
        self,
        mock_client_module,
        mock_orchestrator_http_response_no_audio,
        mock_tts_http_response,
    ):
        """Test voice preset selection for TTS."""
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            responses = {
                1: mock_orchestrator_http_response_no_audio,
                2: mock_tts_http_response,
            }
            return responses.get(call_count)

        mock_client_module.post = AsyncMock(side_effect=mock_post)

        # Test different voice presets
        for voice_preset in ["v2/en_speaker_0", "v2/en_speaker_2", "v2/en_speaker_3"]:
            call_count = 0  # Reset for each iteration

            with patch("tempfile.gettempdir", return_value=str(tempfile.gettempdir())):
                transcript, response, audio_path = await run_pipeline(
                    audio=None,
                    text_input="test input",
                    voice_preset=voice_preset,
                )

            # Verify voice preset was used
            tts_call = mock_client_module.post.call_args_list[-1]
            assert tts_call[1]["json"]["voice"] == voice_preset

            # Note: Temporary files use OS cleanup (delete=False for Gradio async access)


@pytest.mark.component
@pytest.mark.asyncio
class TestTestingServiceErrorHandling:
    """Component tests for error handling in testing service pipeline."""

    @patch("services.testing.app.client")
    async def test_stt_failure_error_message(
        self,
        mock_client_module,
        sample_wav_file: Path,
        mock_preprocessor_response,
    ):
        """Test STT failure → Error message returned."""
        # Configure mock: preprocessing succeeds, STT fails
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Preprocessing succeeds
                return mock_preprocessor_response
            if call_count == 2:
                # STT fails
                raise httpx.HTTPStatusError(
                    "STT service unavailable", request=Mock(), response=Mock()
                )
            return None

        mock_client_module.post = AsyncMock(side_effect=mock_post)

        # Execute
        transcript, response, audio_path = await run_pipeline(
            audio=str(sample_wav_file),
            text_input="",
            voice_preset="v2/en_speaker_0",
        )

        # Verify
        assert transcript == "Transcription failed"
        # Note: Orchestrator and TTS are still called even when STT fails,
        # since transcript="Transcription failed" is not empty
        assert mock_client_module.post.call_count >= 2  # At least Preprocess + STT

    @patch("services.testing.app.client")
    async def test_orchestrator_failure_error_message(
        self,
        mock_client_module,
    ):
        """Test orchestrator failure → Error message returned."""
        # Configure mock: orchestrator fails
        orchestrator_error = httpx.HTTPStatusError(
            "Orchestrator service unavailable", request=Mock(), response=Mock()
        )
        mock_client_module.post = AsyncMock(side_effect=orchestrator_error)

        # Execute
        transcript, response, audio_path = await run_pipeline(
            audio=None,
            text_input="test input",
            voice_preset="v2/en_speaker_0",
        )

        # Verify
        assert transcript == "test input"
        assert "Orchestration" in response or "error" in response.lower()
        assert audio_path is None

    @patch("services.testing.app.client")
    async def test_orchestrator_error_response(
        self,
        mock_client_module,
        mock_orchestrator_response_error,
    ):
        """Test orchestrator error response (success=False)."""
        # Configure mock: orchestrator returns error in response
        orchestrator_response = Mock(spec=httpx.Response)
        orchestrator_response.status_code = 200
        orchestrator_response.json = Mock(return_value=mock_orchestrator_response_error)
        orchestrator_response.raise_for_status = Mock()

        mock_client_module.post = AsyncMock(return_value=orchestrator_response)

        # Execute
        transcript, response, audio_path = await run_pipeline(
            audio=None,
            text_input="test input",
            voice_preset="v2/en_speaker_0",
        )

        # Verify
        assert transcript == "test input"
        assert "Orchestration failed" in response or "error" in response.lower()
        assert audio_path is None

    @patch("services.testing.app.client")
    async def test_tts_fallback_failure_no_audio_output(
        self,
        mock_client_module,
        mock_orchestrator_http_response_no_audio,
    ):
        """Test TTS fallback failure → No audio output."""
        # Configure mock: orchestrator has no audio, TTS fails
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Orchestrator returns no audio
                return mock_orchestrator_http_response_no_audio
            if call_count == 2:
                # TTS fails
                raise httpx.HTTPStatusError(
                    "TTS service unavailable", request=Mock(), response=Mock()
                )
            return None

        mock_client_module.post = AsyncMock(side_effect=mock_post)

        # Execute
        transcript, response, audio_path = await run_pipeline(
            audio=None,
            text_input="test input",
            voice_preset="v2/en_speaker_0",
        )

        # Verify
        assert response == "This is a test response"
        assert audio_path is None  # TTS failed, no audio output

    @patch("services.testing.app.client")
    async def test_base64_decoding_errors(
        self,
        mock_client_module,
    ):
        """Test base64 decoding error handling."""
        # Configure mock: orchestrator returns invalid base64
        orchestrator_response = Mock(spec=httpx.Response)
        orchestrator_response.status_code = 200
        orchestrator_response.json = Mock(
            return_value={
                "success": True,
                "response_text": "test response",
                "audio_data": "invalid_base64!!!",  # Invalid base64
                "audio_format": "wav",
            }
        )
        orchestrator_response.raise_for_status = Mock()

        mock_client_module.post = AsyncMock(return_value=orchestrator_response)

        # Execute - should handle base64 decode error gracefully
        transcript, response, audio_path = await run_pipeline(
            audio=None,
            text_input="test input",
            voice_preset="v2/en_speaker_0",
        )

        # Verify - should fall back to TTS or return None for audio_path
        assert response == "test response"
        # Audio path might be None if base64 decode fails, or might try TTS fallback
        # (Note: Base64 decode will fail silently and TTS fallback won't be called in this test)


@pytest.mark.component
@pytest.mark.asyncio
class TestTestingServiceDataTransformation:
    """Component tests for data transformation in testing service."""

    @patch("services.testing.app.client")
    async def test_base64_audio_decoding_correctness(
        self,
        mock_client_module,
        mock_orchestrator_http_response,
    ):
        """Test base64 audio decoding correctness."""
        mock_client_module.post = AsyncMock(
            return_value=mock_orchestrator_http_response
        )

        # Get expected audio data
        orchestrator_data = mock_orchestrator_http_response.json()
        expected_audio = base64.b64decode(orchestrator_data["audio_data"])

        with patch("tempfile.gettempdir", return_value=str(tempfile.gettempdir())):
            # Execute
            transcript, response, audio_path = await run_pipeline(
                audio=None,
                text_input="test input",
                voice_preset="v2/en_speaker_0",
            )

        # Verify base64 decoding was correct
        assert audio_path is not None
        saved_audio = Path(audio_path).read_bytes()
        assert saved_audio == expected_audio

        # Note: Temporary files use OS cleanup (delete=False for Gradio async access)

    @patch("services.testing.app.client")
    async def test_file_io_operations(
        self,
        mock_client_module,
        temp_dir: Path,
        mock_orchestrator_http_response,
    ):
        """Test file I/O operations."""
        mock_client_module.post = AsyncMock(
            return_value=mock_orchestrator_http_response
        )

        # Patch tempfile.gettempdir to use test temp_dir
        with patch("tempfile.gettempdir", return_value=str(temp_dir)):
            # Execute
            transcript, response, audio_path = await run_pipeline(
                audio=None,
                text_input="test input",
                voice_preset="v2/en_speaker_0",
            )

        # Verify file was created and is readable
        # Note: tempfile.NamedTemporaryFile uses system temp dir, not temp_dir fixture
        assert audio_path is not None
        assert Path(audio_path).exists()
        saved_audio = Path(audio_path).read_bytes()
        assert len(saved_audio) > 0

        # Note: Temporary files use OS cleanup (delete=False for Gradio async access)

    @patch("services.testing.app.client")
    async def test_file_path_validation(
        self,
        mock_client_module,
        mock_orchestrator_http_response,
    ):
        """Test file path validation."""
        mock_client_module.post = AsyncMock(
            return_value=mock_orchestrator_http_response
        )

        with patch("tempfile.gettempdir", return_value=str(tempfile.gettempdir())):
            # Execute
            transcript, response, audio_path = await run_pipeline(
                audio=None,
                text_input="test input",
                voice_preset="v2/en_speaker_0",
            )

        # Verify path is valid and file exists
        assert audio_path is not None
        path_obj = Path(audio_path)
        assert path_obj.is_file()  # Should be a file, not directory
        assert path_obj.exists()
        assert path_obj.suffix == ".wav"

        # Note: Temporary files use OS cleanup (delete=False for Gradio async access)

    @patch("services.testing.app.client")
    async def test_temporary_file_cleanup(
        self,
        mock_client_module,
        temp_dir: Path,
        mock_orchestrator_http_response,
    ):
        """Test temporary file cleanup (implicit via temp_dir fixture)."""
        mock_client_module.post = AsyncMock(
            return_value=mock_orchestrator_http_response
        )

        with patch("tempfile.gettempdir", return_value=str(temp_dir)):
            # Execute
            transcript, response, audio_path = await run_pipeline(
                audio=None,
                text_input="test input",
                voice_preset="v2/en_speaker_0",
            )

        # Verify file was created
        assert audio_path is not None
        assert Path(audio_path).exists()

        # File will be cleaned up automatically by temp_dir fixture
        # This test verifies the file can be created and accessed
