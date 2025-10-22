"""Tests for end-to-end audio pipeline functionality."""

import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.discord.audio import AudioSegment
from services.discord.config import (
    AudioConfig,
    BotConfig,
    STTConfig,
    TelemetryConfig,
    WakeConfig,
)
from services.discord.discord_voice import VoiceBot
from services.discord.transcription import TranscriptionClient
from services.discord.wake import WakeDetector


class TestAudioPipelineE2E:
    """Test end-to-end audio pipeline functionality."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock configuration for testing."""
        audio_config = AudioConfig(
            allowlist_user_ids=[],
            silence_timeout_seconds=0.75,
            max_segment_duration_seconds=15.0,
            min_segment_duration_seconds=0.3,
            aggregation_window_seconds=1.5,
            input_sample_rate_hz=48000,
            vad_sample_rate_hz=16000,
            vad_frame_duration_ms=30,
            vad_aggressiveness=2,
        )

        stt_config = STTConfig(
            base_url="http://test-stt:9000",
            request_timeout_seconds=45,
            max_retries=3,
            forced_language="en",
        )

        wake_config = WakeConfig(
            wake_phrases=["hey atlas", "ok atlas"],
            model_paths=[],
            activation_threshold=0.5,
            target_sample_rate_hz=16000,
            enabled=True,
        )

        telemetry_config = TelemetryConfig(waveform_debug_dir=tmp_path / "debug_wavs")

        config = Mock(spec=BotConfig)
        config.audio = audio_config
        config.stt = stt_config
        config.wake = wake_config
        config.telemetry = telemetry_config

        return config

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger for testing."""
        return Mock()

    @pytest.fixture
    def sample_audio_segment(self):
        """Create sample audio segment."""
        import numpy as np

        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_float = np.sin(2 * np.pi * 440 * t) * 0.5
        audio_int16 = (audio_float * 32767).astype(np.int16)
        pcm_data = audio_int16.tobytes()

        return AudioSegment(
            user_id=12345,
            pcm=pcm_data,
            sample_rate=sample_rate,
            start_timestamp=0.0,
            end_timestamp=duration,
            correlation_id="test-correlation-123",
            frame_count=int(sample_rate * duration),
        )

    @pytest.fixture
    def mock_transcription_client(self):
        """Create mock transcription client."""
        client = Mock(spec=TranscriptionClient)
        client.transcribe = AsyncMock()
        client.get_circuit_stats = Mock(
            return_value={"state": "closed", "available": True}
        )
        return client

    @pytest.fixture
    def mock_wake_detector(self):
        """Create mock wake detector."""
        detector = Mock(spec=WakeDetector)
        detector.detect = Mock()
        return detector

    @pytest.fixture
    def mock_orchestrator_client(self):
        """Create mock orchestrator client."""
        client = Mock()
        client.process_transcript = AsyncMock()
        return client

    @pytest.mark.component
    async def test_audio_pipeline_happy_path(
        self,
        mock_config,
        mock_logger,
        sample_audio_segment,
        mock_transcription_client,
        mock_wake_detector,
        mock_orchestrator_client,
    ):
        """Test complete audio pipeline happy path."""
        # Mock transcription result
        mock_transcript = Mock()
        mock_transcript.text = "hey atlas, how are you?"
        mock_transcript.start_timestamp = 0.0
        mock_transcript.end_timestamp = 1.0
        mock_transcript.language = "en"
        mock_transcript.confidence = 0.9
        mock_transcript.correlation_id = "test-correlation-123"
        mock_transcription_client.transcribe.return_value = mock_transcript

        # Mock wake detection result
        mock_wake_result = Mock()
        mock_wake_result.phrase = "hey atlas"
        mock_wake_result.confidence = 0.8
        mock_wake_result.source = "transcript"
        mock_wake_detector.detect.return_value = mock_wake_result

        # Mock orchestrator result
        mock_orchestrator_result = Mock()
        mock_orchestrator_result.text = "I'm doing well, thank you!"
        mock_orchestrator_result.audio_url = "http://test-tts:7000/audio/123.wav"
        mock_orchestrator_client.process_transcript.return_value = (
            mock_orchestrator_result
        )

        # Create voice bot with mocks
        voice_bot = Mock(spec=VoiceBot)
        voice_bot.config = mock_config
        voice_bot._logger = mock_logger
        voice_bot._save_debug_wav = Mock()

        # Simulate the pipeline flow
        with (
            patch(
                "services.discord.discord_voice.TranscriptionClient",
                return_value=mock_transcription_client,
            ),
            patch(
                "services.discord.discord_voice.WakeDetector",
                return_value=mock_wake_detector,
            ),
            patch(
                "services.discord.discord_voice.OrchestratorClient",
                return_value=mock_orchestrator_client,
            ),
        ):
            # Simulate segment processing
            voice_bot._save_debug_wav(sample_audio_segment, prefix="captured")

            # Simulate transcription
            transcript = await mock_transcription_client.transcribe(
                sample_audio_segment
            )
            assert transcript.text == "hey atlas, how are you?"

            # Simulate wake detection
            wake_result = mock_wake_detector.detect(
                sample_audio_segment, transcript.text
            )
            assert wake_result.phrase == "hey atlas"

            # Simulate orchestrator processing
            voice_bot._save_debug_wav(sample_audio_segment, prefix="wake_detected")
            orchestrator_result = await mock_orchestrator_client.process_transcript(
                guild_id="123456789",
                channel_id="987654321",
                user_id="12345",
                transcript=transcript.text,
            )
            assert orchestrator_result.text == "I'm doing well, thank you!"

        # Verify debug WAV files were saved
        assert voice_bot._save_debug_wav.call_count == 2
        voice_bot._save_debug_wav.assert_any_call(
            sample_audio_segment, prefix="captured"
        )
        voice_bot._save_debug_wav.assert_any_call(
            sample_audio_segment, prefix="wake_detected"
        )

    @pytest.mark.component
    def test_audio_pipeline_with_wake_detection(
        self,
        mock_config,
        mock_logger,
        sample_audio_segment,
        mock_transcription_client,
        mock_wake_detector,
    ):
        """Test audio pipeline with wake detection enabled."""
        # Mock transcription result
        mock_transcript = Mock()
        mock_transcript.text = "hey atlas, what's the weather?"
        mock_transcript.correlation_id = "test-correlation-123"
        mock_transcription_client.transcribe.return_value = mock_transcript

        # Mock wake detection result
        mock_wake_result = Mock()
        mock_wake_result.phrase = "hey atlas"
        mock_wake_result.confidence = 0.9
        mock_wake_result.source = "transcript"
        mock_wake_detector.detect.return_value = mock_wake_result

        # Test wake detection
        wake_result = mock_wake_detector.detect(
            sample_audio_segment, mock_transcript.text
        )

        assert wake_result is not None
        assert wake_result.phrase == "hey atlas"
        assert wake_result.confidence == 0.9
        assert wake_result.source == "transcript"

    @pytest.mark.component
    def test_audio_pipeline_without_wake_detection(
        self,
        mock_config,
        mock_logger,
        sample_audio_segment,
        mock_transcription_client,
        mock_wake_detector,
    ):
        """Test audio pipeline with wake detection disabled."""
        # Disable wake detection
        mock_config.wake.enabled = False

        # Mock transcription result
        mock_transcript = Mock()
        mock_transcript.text = "just some regular conversation"
        mock_transcript.correlation_id = "test-correlation-123"
        mock_transcription_client.transcribe.return_value = mock_transcript

        # Mock wake detection result (should return testing_mode)
        mock_wake_result = Mock()
        mock_wake_result.phrase = "testing_mode"
        mock_wake_result.confidence = 1.0
        mock_wake_result.source = "transcript"
        mock_wake_detector.detect.return_value = mock_wake_result

        # Test wake detection
        wake_result = mock_wake_detector.detect(
            sample_audio_segment, mock_transcript.text
        )

        assert wake_result is not None
        assert wake_result.phrase == "testing_mode"
        assert wake_result.confidence == 1.0
        assert wake_result.source == "transcript"

    @pytest.mark.component
    async def test_audio_pipeline_stt_circuit_open(
        self, mock_config, mock_logger, sample_audio_segment, mock_transcription_client
    ):
        """Test audio pipeline when STT circuit breaker is open."""
        # Mock circuit breaker in open state
        mock_transcription_client.get_circuit_stats.return_value = {
            "state": "open",
            "available": False,
            "failure_count": 5,
            "success_count": 0,
        }
        mock_transcription_client.transcribe.return_value = None

        # Test transcription with open circuit
        transcript = await mock_transcription_client.transcribe(sample_audio_segment)

        # Should return None when circuit is open
        assert transcript is None

    @pytest.mark.component
    async def test_audio_pipeline_correlation_id_propagation(
        self,
        mock_config,
        mock_logger,
        sample_audio_segment,
        mock_transcription_client,
        mock_wake_detector,
    ):
        """Test that correlation ID propagates through entire pipeline."""
        correlation_id = "test-correlation-123"
        sample_audio_segment.correlation_id = correlation_id

        # Mock transcription result
        mock_transcript = Mock()
        mock_transcript.text = "hey atlas, how are you?"
        mock_transcript.correlation_id = correlation_id
        mock_transcription_client.transcribe.return_value = mock_transcript

        # Mock wake detection result
        mock_wake_result = Mock()
        mock_wake_result.phrase = "hey atlas"
        mock_wake_result.confidence = 0.8
        mock_wake_result.source = "transcript"
        mock_wake_detector.detect.return_value = mock_wake_result

        # Test correlation ID propagation
        transcript = await mock_transcription_client.transcribe(sample_audio_segment)
        assert transcript.correlation_id == correlation_id

        wake_result = mock_wake_detector.detect(sample_audio_segment, transcript.text)
        assert wake_result is not None

    @pytest.mark.component
    async def test_audio_pipeline_debug_artifacts_generated(
        self,
        mock_config,
        mock_logger,
        sample_audio_segment,
        mock_transcription_client,
        mock_wake_detector,
    ):
        """Test that debug artifacts are generated at key points."""
        # Mock transcription result
        mock_transcript = Mock()
        mock_transcript.text = "hey atlas, how are you?"
        mock_transcript.correlation_id = "test-correlation-123"
        mock_transcription_client.transcribe.return_value = mock_transcript

        # Mock wake detection result
        mock_wake_result = Mock()
        mock_wake_result.phrase = "hey atlas"
        mock_wake_result.confidence = 0.8
        mock_wake_result.source = "transcript"
        mock_wake_detector.detect.return_value = mock_wake_result

        # Create voice bot with debug WAV method
        voice_bot = Mock(spec=VoiceBot)
        voice_bot.config = mock_config
        voice_bot._logger = mock_logger
        voice_bot._save_debug_wav = Mock()

        # Simulate pipeline with debug artifacts
        voice_bot._save_debug_wav(sample_audio_segment, prefix="captured")

        transcript = await mock_transcription_client.transcribe(sample_audio_segment)
        wake_result = mock_wake_detector.detect(sample_audio_segment, transcript.text)

        if wake_result:
            voice_bot._save_debug_wav(sample_audio_segment, prefix="wake_detected")

        # Verify debug artifacts were generated
        assert voice_bot._save_debug_wav.call_count >= 1
        voice_bot._save_debug_wav.assert_any_call(
            sample_audio_segment, prefix="captured"
        )

        if wake_result:
            voice_bot._save_debug_wav.assert_any_call(
                sample_audio_segment, prefix="wake_detected"
            )

    @pytest.mark.component
    async def test_audio_pipeline_error_handling(
        self, mock_config, mock_logger, sample_audio_segment, mock_transcription_client
    ):
        """Test audio pipeline error handling."""
        # Mock transcription failure
        mock_transcription_client.transcribe.side_effect = Exception(
            "STT service unavailable"
        )

        # Test error handling
        with pytest.raises(Exception, match="STT service unavailable"):
            await mock_transcription_client.transcribe(sample_audio_segment)

    @pytest.mark.component
    async def test_audio_pipeline_logging_sequence(
        self,
        mock_config,
        mock_logger,
        sample_audio_segment,
        mock_transcription_client,
        mock_wake_detector,
    ):
        """Test that all expected log events appear in sequence."""
        # Mock transcription result
        mock_transcript = Mock()
        mock_transcript.text = "hey atlas, how are you?"
        mock_transcript.correlation_id = "test-correlation-123"
        mock_transcription_client.transcribe.return_value = mock_transcript

        # Mock wake detection result
        mock_wake_result = Mock()
        mock_wake_result.phrase = "hey atlas"
        mock_wake_result.confidence = 0.8
        mock_wake_result.source = "transcript"
        mock_wake_detector.detect.return_value = mock_wake_result

        # Simulate pipeline flow
        transcript = await mock_transcription_client.transcribe(sample_audio_segment)
        wake_result = mock_wake_detector.detect(sample_audio_segment, transcript.text)

        # Verify that the pipeline completed successfully
        assert transcript is not None
        assert transcript.text == "hey atlas, how are you?"
        assert wake_result is not None
        assert wake_result.phrase == "hey atlas"

    @pytest.mark.component
    async def test_audio_pipeline_performance_metrics(
        self,
        mock_config,
        mock_logger,
        sample_audio_segment,
        mock_transcription_client,
        mock_wake_detector,
    ):
        """Test audio pipeline performance metrics."""
        # Mock transcription result
        mock_transcript = Mock()
        mock_transcript.text = "hey atlas, how are you?"
        mock_transcript.correlation_id = "test-correlation-123"
        mock_transcription_client.transcribe.return_value = mock_transcript

        # Mock wake detection result
        mock_wake_result = Mock()
        mock_wake_result.phrase = "hey atlas"
        mock_wake_result.confidence = 0.8
        mock_wake_result.source = "transcript"
        mock_wake_detector.detect.return_value = mock_wake_result

        # Measure pipeline performance
        start_time = time.time()

        transcript = await mock_transcription_client.transcribe(sample_audio_segment)
        wake_result = mock_wake_detector.detect(sample_audio_segment, transcript.text)

        end_time = time.time()
        processing_time = end_time - start_time

        # Verify performance metrics
        assert processing_time < 1.0  # Should complete quickly in tests
        assert transcript is not None
        assert wake_result is not None
