"""Tests for audio segment creation and logging functionality."""

from unittest.mock import Mock, patch

import pytest

from services.common.service_configs import TelemetryConfig
from services.discord.audio import Accumulator, AudioPipeline, FlushDecision
from services.discord.config import AudioConfig as DiscordAudioConfig


class TestAudioSegments:
    """Test audio segment creation and logging functionality."""

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
    def audio_pipeline(self, audio_config, telemetry_config, mock_logger):
        """Create audio pipeline for testing."""
        with patch("services.discord.audio.get_logger", return_value=mock_logger):
            return AudioPipeline(audio_config, telemetry_config)

    @pytest.fixture
    def sample_accumulator(self, audio_config):
        """Create sample accumulator for testing."""
        return Accumulator(user_id=12345, config=audio_config)

    @pytest.fixture
    def sample_pcm_data(self):
        """Generate sample PCM data."""
        import numpy as np

        # Generate 1 second of 16kHz audio
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_float = np.sin(2 * np.pi * 440 * t) * 0.5
        audio_int16 = (audio_float * 32767).astype(np.int16)
        return audio_int16.tobytes()

    @pytest.mark.component
    def test_segment_creation_generates_correlation_id(
        self, audio_pipeline, sample_accumulator, mock_logger
    ):
        """Test that segment creation generates a correlation ID."""
        # Add some frames to the accumulator
        sample_accumulator.append(
            Mock(
                pcm=b"frame1",
                timestamp=0.0,
                rms=1000.0,
                duration=0.030,
                sequence=1,
                sample_rate=16000,
            )
        )
        sample_accumulator.append(
            Mock(
                pcm=b"frame2",
                timestamp=0.030,
                rms=1000.0,
                duration=0.030,
                sequence=2,
                sample_rate=16000,
            )
        )

        # Mock the correlation ID generation
        with patch(
            "services.common.correlation.generate_discord_correlation_id",
            return_value="test-correlation-123",
        ):
            segment = audio_pipeline._flush_accumulator(
                sample_accumulator,
                decision=FlushDecision(
                    action="flush",
                    reason="silence_timeout",
                    silence_age=0.75,
                    total_duration=0.06,
                ),
                trigger="silence_check",
                timestamp=0.75,
            )

        # Should create segment with correlation ID
        assert segment is not None
        assert segment.correlation_id == "test-correlation-123"
        assert segment.user_id == 12345

    @pytest.mark.component
    def test_segment_ready_logs_all_metadata(self, audio_pipeline, sample_accumulator, mock_logger):
        """Test that segment ready logs all comprehensive metadata."""
        # Add frames to accumulator
        sample_accumulator.append(
            Mock(
                pcm=b"frame1",
                timestamp=0.0,
                rms=1000.0,
                duration=0.030,
                sequence=1,
                sample_rate=16000,
            )
        )
        sample_accumulator.append(
            Mock(
                pcm=b"frame2",
                timestamp=0.030,
                rms=1000.0,
                duration=0.030,
                sequence=2,
                sample_rate=16000,
            )
        )

        # Mock correlation ID generation and logger binding
        with (
            patch(
                "services.common.correlation.generate_discord_correlation_id",
                return_value="test-correlation-123",
            ),
            patch("services.common.logging.bind_correlation_id", return_value=mock_logger),
        ):

            audio_pipeline._flush_accumulator(
                sample_accumulator,
                decision=FlushDecision(
                    action="flush",
                    reason="silence_timeout",
                    silence_age=0.75,
                    total_duration=0.06,
                ),
                trigger="silence_check",
                timestamp=0.75,
            )

        # Check that info log was called with segment ready
        assert mock_logger.info.call_count == 2  # VAD config + segment ready

        # Find the segment_ready call
        segment_ready_calls = [
            call for call in mock_logger.info.call_args_list if call[0][0] == "voice.segment_ready"
        ]
        assert len(segment_ready_calls) == 1
        call_args = segment_ready_calls[0]
        kwargs = call_args[1]

        # Check all expected metadata fields
        assert "user_id" in kwargs
        assert "frames" in kwargs
        assert "duration" in kwargs
        assert "pcm_bytes" in kwargs
        assert "sample_rate" in kwargs
        assert "flush_reason" in kwargs
        assert "silence_age" in kwargs
        assert "total_duration" in kwargs
        assert "flush_trigger" in kwargs

        assert kwargs["user_id"] == 12345
        assert kwargs["frames"] == 2
        assert kwargs["flush_reason"] == "silence_timeout"
        assert kwargs["silence_age"] == 0.75
        assert kwargs["total_duration"] == 0.06
        assert kwargs["flush_trigger"] == "silence_check"

    @pytest.mark.component
    def test_segment_binds_correlation_id_to_logger(
        self, audio_pipeline, sample_accumulator, mock_logger
    ):
        """Test that segment binds correlation ID to logger context."""
        # Add frames to accumulator
        sample_accumulator.append(
            Mock(
                pcm=b"frame1",
                timestamp=0.0,
                rms=1000.0,
                duration=0.030,
                sequence=1,
                sample_rate=16000,
            )
        )

        # Mock correlation ID generation and logger binding
        with (
            patch(
                "services.common.correlation.generate_discord_correlation_id",
                return_value="test-correlation-123",
            ),
            patch("services.common.logging.bind_correlation_id") as mock_bind,
        ):

            mock_segment_logger = Mock()
            mock_bind.return_value = mock_segment_logger

            audio_pipeline._flush_accumulator(
                sample_accumulator,
                decision=FlushDecision(
                    action="flush",
                    reason="silence_timeout",
                    silence_age=0.75,
                    total_duration=0.06,
                ),
                trigger="silence_check",
                timestamp=0.75,
            )

        # Should bind correlation ID to logger
        mock_bind.assert_called_once_with(mock_logger, "test-correlation-123")

        # Should use the bound logger for segment ready log
        mock_segment_logger.info.assert_called_once()

    @pytest.mark.component
    def test_segment_flush_on_silence_timeout(
        self, audio_pipeline, sample_accumulator, mock_logger
    ):
        """Test that segment flushes on silence timeout."""
        # Add frames to accumulator
        sample_accumulator.append(
            Mock(
                pcm=b"frame1",
                timestamp=0.0,
                rms=1000.0,
                duration=0.030,
                sequence=1,
                sample_rate=16000,
            )
        )

        # Create silence timeout decision
        decision = FlushDecision(
            action="flush",
            reason="silence_timeout",
            silence_age=0.75,
            total_duration=0.03,
        )

        with (
            patch(
                "services.common.correlation.generate_discord_correlation_id",
                return_value="test-correlation-123",
            ),
            patch("services.common.logging.bind_correlation_id", return_value=mock_logger),
        ):

            segment = audio_pipeline._flush_accumulator(
                sample_accumulator,
                decision=decision,
                trigger="silence_check",
                timestamp=0.75,
            )

        # Should create segment
        assert segment is not None
        assert segment.correlation_id == "test-correlation-123"

        # Should log with silence timeout reason
        assert mock_logger.info.call_count == 2  # VAD config + segment ready

        # Find the segment_ready call
        segment_ready_calls = [
            call for call in mock_logger.info.call_args_list if call[0][0] == "voice.segment_ready"
        ]
        assert len(segment_ready_calls) == 1
        call_args = segment_ready_calls[0]
        assert call_args[1]["flush_reason"] == "silence_timeout"
        assert call_args[1]["silence_age"] == 0.75

    @pytest.mark.component
    def test_segment_flush_on_max_duration(self, audio_pipeline, sample_accumulator, mock_logger):
        """Test that segment flushes on max duration."""
        # Add frames to accumulator
        sample_accumulator.append(
            Mock(
                pcm=b"frame1",
                timestamp=0.0,
                rms=1000.0,
                duration=0.030,
                sequence=1,
                sample_rate=16000,
            )
        )

        # Create max duration decision
        decision = FlushDecision(
            action="flush", reason="max_duration", silence_age=0.0, total_duration=15.0
        )

        with (
            patch(
                "services.common.correlation.generate_discord_correlation_id",
                return_value="test-correlation-123",
            ),
            patch("services.common.logging.bind_correlation_id", return_value=mock_logger),
        ):

            segment = audio_pipeline._flush_accumulator(
                sample_accumulator,
                decision=decision,
                trigger="max_duration_check",
                timestamp=15.0,
            )

        # Should create segment
        assert segment is not None
        assert segment.correlation_id == "test-correlation-123"

        # Should log with max duration reason
        assert mock_logger.info.call_count == 2  # VAD config + segment ready

        # Find the segment_ready call
        segment_ready_calls = [
            call for call in mock_logger.info.call_args_list if call[0][0] == "voice.segment_ready"
        ]
        assert len(segment_ready_calls) == 1
        call_args = segment_ready_calls[0]
        assert call_args[1]["flush_reason"] == "max_duration"
        assert call_args[1]["total_duration"] == 15.0

    @pytest.mark.component
    def test_segment_flush_on_idle_timeout(self, audio_pipeline, sample_accumulator, mock_logger):
        """Test that segment flushes on idle timeout."""
        # Add frames to accumulator
        sample_accumulator.append(
            Mock(
                pcm=b"frame1",
                timestamp=0.0,
                rms=1000.0,
                duration=0.030,
                sequence=1,
                sample_rate=16000,
            )
        )

        # Create idle timeout decision
        decision = FlushDecision(
            action="flush", reason="idle_timeout", silence_age=0.0, total_duration=0.03
        )

        with (
            patch(
                "services.common.correlation.generate_discord_correlation_id",
                return_value="test-correlation-123",
            ),
            patch("services.common.logging.bind_correlation_id", return_value=mock_logger),
        ):

            segment = audio_pipeline._flush_accumulator(
                sample_accumulator,
                decision=decision,
                trigger="idle_flush",
                timestamp=1.0,
            )

        # Should create segment
        assert segment is not None
        assert segment.correlation_id == "test-correlation-123"

        # Should log with idle timeout reason
        assert mock_logger.info.call_count == 2  # VAD config + segment ready

        # Find the segment_ready call
        segment_ready_calls = [
            call for call in mock_logger.info.call_args_list if call[0][0] == "voice.segment_ready"
        ]
        assert len(segment_ready_calls) == 1
        call_args = segment_ready_calls[0]
        assert call_args[1]["flush_reason"] == "idle_timeout"
        assert call_args[1]["flush_trigger"] == "idle_flush"

    @pytest.mark.component
    def test_segment_creation_with_override_reason(
        self, audio_pipeline, sample_accumulator, mock_logger
    ):
        """Test that segment creation uses override reason when provided."""
        # Add frames to accumulator
        sample_accumulator.append(
            Mock(
                pcm=b"frame1",
                timestamp=0.0,
                rms=1000.0,
                duration=0.030,
                sequence=1,
                sample_rate=16000,
            )
        )

        with (
            patch(
                "services.common.correlation.generate_discord_correlation_id",
                return_value="test-correlation-123",
            ),
            patch("services.common.logging.bind_correlation_id", return_value=mock_logger),
        ):

            audio_pipeline._flush_accumulator(
                sample_accumulator,
                decision=FlushDecision(
                    action="flush",
                    reason="silence_timeout",
                    silence_age=0.75,
                    total_duration=0.06,
                ),
                trigger="silence_check",
                override_reason="manual_flush",
                timestamp=0.75,
            )

        # Should use override reason
        assert mock_logger.info.call_count == 2  # VAD config + segment ready

        # Find the segment_ready call
        segment_ready_calls = [
            call for call in mock_logger.info.call_args_list if call[0][0] == "voice.segment_ready"
        ]
        assert len(segment_ready_calls) == 1
        call_args = segment_ready_calls[0]
        assert call_args[1]["flush_reason"] == "manual_flush"

    @pytest.mark.component
    def test_segment_creation_with_no_decision(
        self, audio_pipeline, sample_accumulator, mock_logger
    ):
        """Test that segment creation handles no decision gracefully."""
        # Add frames to accumulator
        sample_accumulator.append(
            Mock(
                pcm=b"frame1",
                timestamp=0.0,
                rms=1000.0,
                duration=0.030,
                sequence=1,
                sample_rate=16000,
            )
        )

        with (
            patch(
                "services.common.correlation.generate_discord_correlation_id",
                return_value="test-correlation-123",
            ),
            patch("services.common.logging.bind_correlation_id", return_value=mock_logger),
        ):

            segment = audio_pipeline._flush_accumulator(
                sample_accumulator,
                decision=None,
                trigger="manual_flush",
                timestamp=0.75,
            )

        # Should create segment with unknown reason
        assert segment is not None
        assert segment.correlation_id == "test-correlation-123"

        # Should log with unknown reason
        assert mock_logger.info.call_count == 2  # VAD config + segment ready

        # Find the segment_ready call
        segment_ready_calls = [
            call for call in mock_logger.info.call_args_list if call[0][0] == "voice.segment_ready"
        ]
        assert len(segment_ready_calls) == 1
        call_args = segment_ready_calls[0]
        assert call_args[1]["flush_reason"] == "manual_flush"

    @pytest.mark.component
    def test_segment_creation_empty_accumulator(
        self, audio_pipeline, sample_accumulator, mock_logger
    ):
        """Test that segment creation handles empty accumulator gracefully."""
        # Don't add any frames to accumulator

        with patch(
            "services.common.correlation.generate_discord_correlation_id",
            return_value="test-correlation-123",
        ):
            segment = audio_pipeline._flush_accumulator(
                sample_accumulator,
                decision=FlushDecision(
                    action="flush",
                    reason="silence_timeout",
                    silence_age=0.75,
                    total_duration=0.0,
                ),
                trigger="silence_check",
                timestamp=0.75,
            )

        # Should return None for empty accumulator
        assert segment is None

        # Should only log VAD config (no segment ready for empty accumulator)
        assert mock_logger.info.call_count == 1  # Only VAD config

        # Verify it was the VAD config call, not segment ready
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "voice.vad_configured"

    @pytest.mark.component
    def test_segment_metadata_accuracy(self, audio_pipeline, sample_accumulator, mock_logger):
        """Test that segment metadata is accurate."""
        # Add multiple frames to accumulator
        frame1 = Mock(
            pcm=b"frame1",
            timestamp=0.0,
            rms=1000.0,
            duration=0.030,
            sequence=1,
            sample_rate=16000,
        )
        frame2 = Mock(
            pcm=b"frame2",
            timestamp=0.030,
            rms=1200.0,
            duration=0.030,
            sequence=2,
            sample_rate=16000,
        )
        frame3 = Mock(
            pcm=b"frame3",
            timestamp=0.060,
            rms=800.0,
            duration=0.030,
            sequence=3,
            sample_rate=16000,
        )

        sample_accumulator.append(frame1)
        sample_accumulator.append(frame2)
        sample_accumulator.append(frame3)

        with patch(
            "services.common.correlation.generate_discord_correlation_id",
            return_value="test-correlation-123",
        ):
            segment = audio_pipeline._flush_accumulator(
                sample_accumulator,
                decision=FlushDecision(
                    action="flush",
                    reason="silence_timeout",
                    silence_age=0.75,
                    total_duration=0.09,
                ),
                trigger="silence_check",
                timestamp=0.75,
            )

        # Should create segment with correct metadata
        assert segment is not None
        assert segment.user_id == 12345
        assert segment.frame_count == 3
        assert segment.duration == 0.09
        assert segment.sample_rate == 16000
        assert len(segment.pcm) == len(b"frame1") + len(b"frame2") + len(b"frame3")
