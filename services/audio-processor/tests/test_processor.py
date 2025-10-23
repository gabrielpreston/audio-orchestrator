"""Tests for the audio processor core logic."""

from unittest.mock import Mock, patch

import numpy as np
import pytest

from services.audio_processor.processor import AudioProcessor
from services.discord.audio import AudioSegment, PCMFrame


class TestAudioProcessor:
    """Test cases for AudioProcessor class."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        config = Mock()
        config.enable_vad = True
        config.enable_volume_normalization = True
        config.enable_noise_reduction = True
        config.sample_rate = 16000
        config.channels = 1
        return config

    @pytest.fixture
    def audio_processor(self, mock_config):
        """Create AudioProcessor instance for testing."""
        with patch("services.audio_processor.processor.webrtcvad.Vad"):
            return AudioProcessor(mock_config)

    @pytest.fixture
    def sample_pcm_frame(self):
        """Create sample PCM frame for testing."""
        # Generate 1 second of 16kHz audio
        sample_rate = 16000
        duration = 1.0
        samples = int(sample_rate * duration)

        # Generate sine wave
        frequency = 440  # A4 note
        t = np.linspace(0, duration, samples, False)
        audio_data = np.sin(2 * np.pi * frequency * t)

        # Convert to int16 PCM
        pcm_data = (audio_data * 32767).astype(np.int16).tobytes()

        return PCMFrame(
            pcm=pcm_data,
            timestamp=0.0,
            rms=0.5,
            duration=duration,
            sequence=1,
            sample_rate=sample_rate,
        )

    @pytest.fixture
    def sample_audio_segment(self):
        """Create sample audio segment for testing."""
        # Generate 2 seconds of 16kHz audio
        sample_rate = 16000
        duration = 2.0
        samples = int(sample_rate * duration)

        # Generate sine wave
        frequency = 440  # A4 note
        t = np.linspace(0, duration, samples, False)
        audio_data = np.sin(2 * np.pi * frequency * t)

        # Convert to int16 PCM
        pcm_data = (audio_data * 32767).astype(np.int16).tobytes()

        return AudioSegment(
            user_id=12345,
            pcm=pcm_data,
            start_timestamp=0.0,
            end_timestamp=duration,
            correlation_id="test-correlation-123",
            frame_count=1,
            sample_rate=sample_rate,
        )

    @pytest.mark.asyncio
    async def test_initialize(self, audio_processor):
        """Test audio processor initialization."""
        await audio_processor.initialize()
        # Should not raise any exceptions

    @pytest.mark.asyncio
    async def test_cleanup(self, audio_processor):
        """Test audio processor cleanup."""
        await audio_processor.cleanup()
        # Should not raise any exceptions

    @pytest.mark.asyncio
    async def test_process_frame(self, audio_processor, sample_pcm_frame):
        """Test frame processing."""
        result = await audio_processor.process_frame(sample_pcm_frame)

        assert isinstance(result, PCMFrame)
        assert result.sequence == sample_pcm_frame.sequence
        assert result.sample_rate == sample_pcm_frame.sample_rate
        assert len(result.pcm) > 0

    @pytest.mark.asyncio
    async def test_process_segment(self, audio_processor, sample_audio_segment):
        """Test segment processing."""
        result = await audio_processor.process_segment(sample_audio_segment)

        assert isinstance(result, AudioSegment)
        assert result.user_id == sample_audio_segment.user_id
        assert result.correlation_id == sample_audio_segment.correlation_id
        assert result.sample_rate == sample_audio_segment.sample_rate
        assert len(result.pcm) > 0

    @pytest.mark.asyncio
    async def test_calculate_quality_metrics_frame(
        self, audio_processor, sample_pcm_frame
    ):
        """Test quality metrics calculation for frame."""
        metrics = await audio_processor.calculate_quality_metrics(sample_pcm_frame)

        assert isinstance(metrics, dict)
        assert "rms" in metrics
        assert "snr_db" in metrics
        assert "clarity_score" in metrics
        assert "dominant_frequency_hz" in metrics
        assert "sample_rate" in metrics
        assert "duration_ms" in metrics

        assert isinstance(metrics["rms"], float)
        assert isinstance(metrics["snr_db"], float)
        assert isinstance(metrics["clarity_score"], float)
        assert 0.0 <= metrics["clarity_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_calculate_quality_metrics_segment(
        self, audio_processor, sample_audio_segment
    ):
        """Test quality metrics calculation for segment."""
        metrics = await audio_processor.calculate_quality_metrics(sample_audio_segment)

        assert isinstance(metrics, dict)
        assert "rms" in metrics
        assert "snr_db" in metrics
        assert "clarity_score" in metrics
        assert "dominant_frequency_hz" in metrics
        assert "sample_rate" in metrics
        assert "duration_ms" in metrics

        assert isinstance(metrics["rms"], float)
        assert isinstance(metrics["snr_db"], float)
        assert isinstance(metrics["clarity_score"], float)
        assert 0.0 <= metrics["clarity_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_process_frame_with_vad_disabled(self, mock_config, sample_pcm_frame):
        """Test frame processing with VAD disabled."""
        mock_config.enable_vad = False
        audio_processor = AudioProcessor(mock_config)

        result = await audio_processor.process_frame(sample_pcm_frame)

        assert isinstance(result, PCMFrame)
        assert result.sequence == sample_pcm_frame.sequence

    @pytest.mark.asyncio
    async def test_process_frame_error_handling(self, audio_processor):
        """Test frame processing error handling."""
        # Create invalid frame
        invalid_frame = PCMFrame(
            pcm=b"",  # Empty PCM data
            timestamp=0.0,
            rms=0.0,
            duration=0.0,
            sequence=1,
            sample_rate=16000,
        )

        result = await audio_processor.process_frame(invalid_frame)

        # Should return original frame on error
        assert isinstance(result, PCMFrame)
        assert result.sequence == invalid_frame.sequence

    @pytest.mark.asyncio
    async def test_process_segment_error_handling(self, audio_processor):
        """Test segment processing error handling."""
        # Create invalid segment
        invalid_segment = AudioSegment(
            user_id=12345,
            pcm=b"",  # Empty PCM data
            start_timestamp=0.0,
            end_timestamp=0.0,
            correlation_id="test-correlation-123",
            frame_count=0,
            sample_rate=16000,
        )

        result = await audio_processor.process_segment(invalid_segment)

        # Should return original segment on error
        assert isinstance(result, AudioSegment)
        assert result.correlation_id == invalid_segment.correlation_id

    def test_get_processing_stats(self, audio_processor):
        """Test processing statistics."""
        stats = audio_processor.get_processing_stats()

        assert isinstance(stats, dict)
        assert "total_frames" in stats
        assert "total_segments" in stats
        assert "total_processing_time" in stats
        assert "avg_frame_processing_time" in stats
        assert "avg_segment_processing_time" in stats

        assert stats["total_frames"] == 0
        assert stats["total_segments"] == 0

    @pytest.mark.asyncio
    async def test_processing_stats_update(
        self, audio_processor, sample_pcm_frame, sample_audio_segment
    ):
        """Test that processing statistics are updated correctly."""
        initial_stats = audio_processor.get_processing_stats()

        # Process a frame
        await audio_processor.process_frame(sample_pcm_frame)

        # Process a segment
        await audio_processor.process_segment(sample_audio_segment)

        updated_stats = audio_processor.get_processing_stats()

        assert updated_stats["total_frames"] == initial_stats["total_frames"] + 1
        assert updated_stats["total_segments"] == initial_stats["total_segments"] + 1
        assert (
            updated_stats["total_processing_time"]
            > initial_stats["total_processing_time"]
        )
