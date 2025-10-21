"""Tests for VAD (Voice Activity Detection) pipeline functionality."""

from unittest.mock import Mock, patch

import pytest

from services.common.service_configs import TelemetryConfig
from services.discord.audio import AudioPipeline
from services.discord.config import AudioConfig as DiscordAudioConfig


class TestVADPipeline:
    """Test VAD pipeline functionality."""

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger for testing."""
        return Mock()

    @pytest.fixture
    def audio_config(self):
        """Create audio configuration for testing."""
        return DiscordAudioConfig(
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

    @pytest.fixture
    def telemetry_config(self):
        """Create telemetry configuration for testing."""
        return TelemetryConfig()

    @pytest.fixture
    def audio_pipeline(self, audio_config, telemetry_config):
        """Create audio pipeline for testing."""
        return AudioPipeline(audio_config, telemetry_config)

    @pytest.fixture
    def sample_pcm_frame(self):
        """Generate sample PCM frame data."""
        # Generate 30ms of 16kHz audio (480 samples)
        sample_rate = 16000
        frame_duration = 0.030  # 30ms
        samples = int(sample_rate * frame_duration)

        # Create a sine wave for speech-like content
        import numpy as np

        t = np.linspace(0, frame_duration, samples, False)
        audio_float = np.sin(2 * np.pi * 440 * t) * 0.5  # 440Hz tone
        audio_int16 = (audio_float * 32767).astype(np.int16)
        return audio_int16.tobytes()

    @pytest.fixture
    def silence_frame(self):
        """Generate silence frame data."""
        # Generate 30ms of silence
        sample_rate = 16000
        frame_duration = 0.030  # 30ms
        samples = int(sample_rate * frame_duration)
        return b"\x00" * (samples * 2)  # 2 bytes per int16 sample

    @pytest.mark.component
    def test_vad_initialization_logs_config(self, audio_config, telemetry_config, mock_logger):
        """Test that VAD initialization logs configuration."""
        with patch("services.discord.audio.get_logger", return_value=mock_logger):
            AudioPipeline(audio_config, telemetry_config)

        # Check that info log was called with VAD configuration
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args

        assert call_args[0][0] == "voice.vad_configured"
        kwargs = call_args[1]

        assert "aggressiveness" in kwargs
        assert "frame_duration_ms" in kwargs
        assert "target_sample_rate" in kwargs
        assert "frame_bytes" in kwargs
        assert kwargs["aggressiveness"] == 2
        assert kwargs["frame_duration_ms"] == 30
        assert kwargs["target_sample_rate"] == 16000

    @pytest.mark.component
    def test_vad_aggressiveness_clamping(self, telemetry_config, mock_logger):
        """Test that VAD aggressiveness is clamped to valid range (0-3)."""
        # Test aggressiveness too high
        config_high = DiscordAudioConfig(
            allowlist_user_ids=[],
            silence_timeout_seconds=0.75,
            max_segment_duration_seconds=15.0,
            min_segment_duration_seconds=0.3,
            aggregation_window_seconds=1.5,
            input_sample_rate_hz=48000,
            vad_sample_rate_hz=16000,
            vad_frame_duration_ms=30,
            vad_aggressiveness=5,  # Too high
        )

        with patch("services.discord.audio.get_logger", return_value=mock_logger):
            AudioPipeline(config_high, telemetry_config)

        # Should log warning about clamping
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args
        assert warning_call[0][0] == "voice.vad_aggressiveness_clamped"
        assert warning_call[1]["requested"] == 5
        assert warning_call[1]["applied"] == 3

    @pytest.mark.component
    def test_vad_frame_duration_validation(self, telemetry_config, mock_logger):
        """Test that VAD frame duration is validated and clamped."""
        # Test invalid frame duration
        config_invalid = DiscordAudioConfig(
            allowlist_user_ids=[],
            silence_timeout_seconds=0.75,
            max_segment_duration_seconds=15.0,
            min_segment_duration_seconds=0.3,
            aggregation_window_seconds=1.5,
            input_sample_rate_hz=48000,
            vad_sample_rate_hz=16000,
            vad_frame_duration_ms=5,  # Too low
            vad_aggressiveness=2,
        )

        with patch("services.discord.audio.get_logger", return_value=mock_logger):
            AudioPipeline(config_invalid, telemetry_config)

        # Should log warning about frame duration clamping
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args
        assert warning_call[0][0] == "voice.vad_frame_adjusted"
        assert warning_call[1]["requested"] == 5
        assert warning_call[1]["applied"] == 10  # Should be clamped to 10ms

    @pytest.mark.component
    def test_vad_decision_logs_speech_frame(self, audio_pipeline, sample_pcm_frame, mock_logger):
        """Test that VAD decision logging works for speech frames."""
        user_id = 12345
        rms = 1000.0
        duration = 0.030
        sample_rate = 16000

        # Mock the logger in the pipeline
        audio_pipeline._logger = mock_logger

        # Mock the VAD to return speech
        with patch.object(audio_pipeline, "_is_speech", return_value=True):
            audio_pipeline.register_frame(
                user_id=user_id,
                pcm=sample_pcm_frame,
                rms=rms,
                duration=duration,
                sample_rate=sample_rate,
            )

        # Check that debug log was called with VAD decision
        mock_logger.debug.assert_called()

        # Find the VAD decision log call
        vad_log_calls = [
            call for call in mock_logger.debug.call_args_list if call[0][0] == "voice.vad_decision"
        ]
        assert len(vad_log_calls) > 0

        vad_call = vad_log_calls[0]
        kwargs = vad_call[1]

        assert kwargs["user_id"] == user_id
        assert kwargs["is_speech"] is True
        # RMS may be normalized, so check it's close to expected value
        assert abs(kwargs["rms"] - rms) < 10.0  # Allow some tolerance for normalization
        assert kwargs["frame_bytes"] == len(sample_pcm_frame)
        assert kwargs["sample_rate"] == sample_rate

    @pytest.mark.component
    def test_vad_decision_logs_silence_frame(self, audio_pipeline, silence_frame, mock_logger):
        """Test that VAD decision logging works for silence frames."""
        user_id = 12345
        rms = 10.0  # Low RMS for silence
        duration = 0.030
        sample_rate = 16000

        # Mock the logger in the pipeline
        audio_pipeline._logger = mock_logger

        # Mock the VAD to return silence
        with patch.object(audio_pipeline, "_is_speech", return_value=False):
            audio_pipeline.register_frame(
                user_id=user_id,
                pcm=silence_frame,
                rms=rms,
                duration=duration,
                sample_rate=sample_rate,
            )

        # Check that debug log was called with VAD decision
        mock_logger.debug.assert_called()

        # Find the VAD decision log call
        vad_log_calls = [
            call for call in mock_logger.debug.call_args_list if call[0][0] == "voice.vad_decision"
        ]
        assert len(vad_log_calls) > 0

        vad_call = vad_log_calls[0]
        kwargs = vad_call[1]

        assert kwargs["user_id"] == user_id
        assert kwargs["is_speech"] is False
        # RMS may be normalized, so check it's close to expected value (allow more tolerance for silence)
        assert abs(kwargs["rms"] - rms) < 20.0  # Allow more tolerance for silence normalization
        assert kwargs["frame_bytes"] == len(silence_frame)
        assert kwargs["sample_rate"] == sample_rate

    @pytest.mark.component
    def test_vad_handles_rate_conversion(self, audio_pipeline, sample_pcm_frame, mock_logger):
        """Test that VAD handles sample rate conversion correctly."""
        user_id = 12345
        rms = 1000.0
        duration = 0.030
        sample_rate = 48000  # Different from VAD sample rate (16000)

        # Mock the logger in the pipeline
        audio_pipeline._logger = mock_logger

        # Mock the VAD to return speech
        with patch.object(audio_pipeline, "_is_speech", return_value=True):
            audio_pipeline.register_frame(
                user_id=user_id,
                pcm=sample_pcm_frame,
                rms=rms,
                duration=duration,
                sample_rate=sample_rate,
            )

        # Check that debug log was called with VAD decision
        mock_logger.debug.assert_called()

        # Find the VAD decision log call
        vad_log_calls = [
            call for call in mock_logger.debug.call_args_list if call[0][0] == "voice.vad_decision"
        ]
        assert len(vad_log_calls) > 0

        vad_call = vad_log_calls[0]
        kwargs = vad_call[1]

        # Should log the original sample rate
        assert kwargs["sample_rate"] == sample_rate
        assert kwargs["user_id"] == user_id
        assert kwargs["is_speech"] is True

    @pytest.mark.component
    def test_vad_sequence_numbering(self, audio_pipeline, sample_pcm_frame, mock_logger):
        """Test that VAD logs include sequence numbers."""
        user_id = 12345
        rms = 1000.0
        duration = 0.030
        sample_rate = 16000

        # Mock the logger in the pipeline
        audio_pipeline._logger = mock_logger

        # Mock the VAD to return speech
        with patch.object(audio_pipeline, "_is_speech", return_value=True):
            # Register multiple frames
            for _ in range(3):
                audio_pipeline.register_frame(
                    user_id=user_id,
                    pcm=sample_pcm_frame,
                    rms=rms,
                    duration=duration,
                    sample_rate=sample_rate,
                )

        # Check that debug logs were called with sequence numbers
        vad_log_calls = [
            call for call in mock_logger.debug.call_args_list if call[0][0] == "voice.vad_decision"
        ]
        assert len(vad_log_calls) == 3

        # Check sequence numbers are incrementing
        sequences = [call[1]["sequence"] for call in vad_log_calls]
        assert sequences == [1, 2, 3]

    @pytest.mark.component
    def test_vad_logs_frame_buffering(self, audio_pipeline, sample_pcm_frame, mock_logger):
        """Test that VAD logs frame buffering for speech frames."""
        user_id = 12345
        rms = 1000.0
        duration = 0.030
        sample_rate = 16000

        # Mock the logger in the pipeline
        audio_pipeline._logger = mock_logger

        # Mock the VAD to return speech
        with patch.object(audio_pipeline, "_is_speech", return_value=True):
            audio_pipeline.register_frame(
                user_id=user_id,
                pcm=sample_pcm_frame,
                rms=rms,
                duration=duration,
                sample_rate=sample_rate,
            )

        # Check that frame buffering was logged
        frame_log_calls = [
            call
            for call in mock_logger.debug.call_args_list
            if call[0][0] == "voice.frame_buffered"
        ]
        assert len(frame_log_calls) > 0

        frame_call = frame_log_calls[0]
        kwargs = frame_call[1]

        assert kwargs["user_id"] == user_id
        assert kwargs["sequence"] == 1
        assert kwargs["duration"] == duration
        # RMS may be normalized, so check it's close to expected value
        assert abs(kwargs["rms"] - rms) < 10.0  # Allow some tolerance for normalization

    @pytest.mark.component
    def test_segment_ready_counts_frames(self, audio_pipeline, sample_pcm_frame, mock_logger):
        """Ensure speech/silence frame counts are computed before clearing frames."""
        user_id = 12345
        rms = 1000.0
        duration = 0.030
        sample_rate = 16000

        # Use mock logger
        audio_pipeline._logger = mock_logger

        # Force VAD to treat frames as speech so they are buffered then flushed by timeout/min rules
        with patch.object(audio_pipeline, "_is_speech", return_value=True):
            # Push a few frames to create a segment
            for _ in range(5):
                audio_pipeline.register_frame(
                    user_id=user_id,
                    pcm=sample_pcm_frame,
                    rms=rms,
                    duration=duration,
                    sample_rate=sample_rate,
                )

        # Force a flush to emit segment_ready
        audio_pipeline.force_flush()

        # Find the segment_ready log call
        segment_calls = [
            call for call in mock_logger.info.call_args_list if call[0][0] == "voice.segment_ready"
        ]
        assert len(segment_calls) >= 1
        seg_kwargs = segment_calls[-1][1]

        assert seg_kwargs["frames"] > 0
        # At least one speech frame expected, and counts should be consistent
        assert seg_kwargs["speech_frames"] + seg_kwargs["silence_frames"] == seg_kwargs["frames"]
        assert seg_kwargs["speech_frames"] > 0
