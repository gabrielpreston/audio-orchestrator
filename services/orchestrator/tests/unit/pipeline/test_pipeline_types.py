"""Unit tests for pipeline types."""

import pytest
from datetime import datetime

from services.orchestrator.pipeline.types import (
    AudioFormat,
    ProcessedSegment,
    ProcessingConfig,
    ProcessingStatus,
)


class TestProcessingConfig:
    """Test ProcessingConfig class."""

    def test_processing_config_creation(self):
        """Test creating a processing config."""
        config = ProcessingConfig()
        
        assert config.target_sample_rate == 16000
        assert config.target_channels == 1
        assert config.target_format == AudioFormat.PCM
        assert config.wake_phrases == ["hey assistant", "computer"]
        assert config.wake_confidence_threshold == 0.8
        assert config.wake_detection_enabled is True
        assert config.max_segment_duration == 30.0
        assert config.min_segment_duration == 0.5
        assert config.silence_threshold == 0.01
        assert config.silence_duration == 2.0
        assert config.enable_audio_enhancement is True
        assert config.enable_noise_reduction is True
        assert config.enable_volume_normalization is True

    def test_processing_config_creation_with_custom_values(self):
        """Test creating a processing config with custom values."""
        config = ProcessingConfig(
            target_sample_rate=44100,
            target_channels=2,
            target_format=AudioFormat.WAV,
            wake_phrases=["hello bot"],
            wake_confidence_threshold=0.9,
            wake_detection_enabled=False,
            max_segment_duration=60.0,
            min_segment_duration=1.0,
            silence_threshold=0.05,
            silence_duration=3.0,
            enable_audio_enhancement=False,
            enable_noise_reduction=False,
            enable_volume_normalization=False,
        )
        
        assert config.target_sample_rate == 44100
        assert config.target_channels == 2
        assert config.target_format == AudioFormat.WAV
        assert config.wake_phrases == ["hello bot"]
        assert config.wake_confidence_threshold == 0.9
        assert config.wake_detection_enabled is False
        assert config.max_segment_duration == 60.0
        assert config.min_segment_duration == 1.0
        assert config.silence_threshold == 0.05
        assert config.silence_duration == 3.0
        assert config.enable_audio_enhancement is False
        assert config.enable_noise_reduction is False
        assert config.enable_volume_normalization is False

    def test_processing_config_validation_negative_sample_rate(self):
        """Test processing config validation with negative sample rate."""
        with pytest.raises(ValueError, match="target_sample_rate must be positive"):
            ProcessingConfig(target_sample_rate=-1)

    def test_processing_config_validation_negative_channels(self):
        """Test processing config validation with negative channels."""
        with pytest.raises(ValueError, match="target_channels must be positive"):
            ProcessingConfig(target_channels=-1)

    def test_processing_config_validation_invalid_confidence_threshold(self):
        """Test processing config validation with invalid confidence threshold."""
        with pytest.raises(ValueError, match="wake_confidence_threshold must be between 0.0 and 1.0"):
            ProcessingConfig(wake_confidence_threshold=1.5)

    def test_processing_config_validation_negative_max_duration(self):
        """Test processing config validation with negative max duration."""
        with pytest.raises(ValueError, match="max_segment_duration must be positive"):
            ProcessingConfig(max_segment_duration=-1)

    def test_processing_config_validation_negative_min_duration(self):
        """Test processing config validation with negative min duration."""
        with pytest.raises(ValueError, match="min_segment_duration must be positive"):
            ProcessingConfig(min_segment_duration=-1)

    def test_processing_config_validation_min_greater_than_max_duration(self):
        """Test processing config validation with min duration greater than max."""
        with pytest.raises(ValueError, match="min_segment_duration must be less than max_segment_duration"):
            ProcessingConfig(min_segment_duration=10.0, max_segment_duration=5.0)

    def test_processing_config_validation_invalid_silence_threshold(self):
        """Test processing config validation with invalid silence threshold."""
        with pytest.raises(ValueError, match="silence_threshold must be between 0.0 and 1.0"):
            ProcessingConfig(silence_threshold=1.5)

    def test_processing_config_validation_negative_silence_duration(self):
        """Test processing config validation with negative silence duration."""
        with pytest.raises(ValueError, match="silence_duration must be positive"):
            ProcessingConfig(silence_duration=-1)


class TestProcessedSegment:
    """Test ProcessedSegment class."""

    def test_processed_segment_creation(self):
        """Test creating a processed segment."""
        segment = ProcessedSegment(
            audio_data=b"\x00" * 1024,
            correlation_id="test-123",
            session_id="session-456",
            original_format=AudioFormat.PCM,
            processed_format=AudioFormat.WAV,
            sample_rate=16000,
            channels=1,
            duration=0.1,
            status=ProcessingStatus.COMPLETED,
            processing_time=0.01,
        )
        
        assert segment.audio_data == b"\x00" * 1024
        assert segment.correlation_id == "test-123"
        assert segment.session_id == "session-456"
        assert segment.original_format == AudioFormat.PCM
        assert segment.processed_format == AudioFormat.WAV
        assert segment.sample_rate == 16000
        assert segment.channels == 1
        assert segment.duration == 0.1
        assert segment.status == ProcessingStatus.COMPLETED
        assert segment.processing_time == 0.01
        assert segment.wake_detected is False
        assert segment.wake_phrase is None
        assert segment.wake_confidence == 0.0
        assert segment.volume_level == 0.0
        assert segment.noise_level == 0.0
        assert segment.clarity_score == 0.0
        assert isinstance(segment.created_at, datetime)
        assert isinstance(segment.processed_at, datetime)
        assert segment.metadata == {}

    def test_processed_segment_creation_with_all_fields(self):
        """Test creating a processed segment with all fields."""
        segment = ProcessedSegment(
            audio_data=b"\x00" * 2048,
            correlation_id="test-789",
            session_id="session-101",
            original_format=AudioFormat.MP3,
            processed_format=AudioFormat.PCM,
            sample_rate=44100,
            channels=2,
            duration=0.2,
            status=ProcessingStatus.COMPLETED,
            processing_time=0.02,
            wake_detected=True,
            wake_phrase="hello bot",
            wake_confidence=0.9,
            volume_level=0.8,
            noise_level=0.1,
            clarity_score=0.9,
            metadata={"test": "value"},
        )
        
        assert segment.audio_data == b"\x00" * 2048
        assert segment.correlation_id == "test-789"
        assert segment.session_id == "session-101"
        assert segment.original_format == AudioFormat.MP3
        assert segment.processed_format == AudioFormat.PCM
        assert segment.sample_rate == 44100
        assert segment.channels == 2
        assert segment.duration == 0.2
        assert segment.status == ProcessingStatus.COMPLETED
        assert segment.processing_time == 0.02
        assert segment.wake_detected is True
        assert segment.wake_phrase == "hello bot"
        assert segment.wake_confidence == 0.9
        assert segment.volume_level == 0.8
        assert segment.noise_level == 0.1
        assert segment.clarity_score == 0.9
        assert segment.metadata == {"test": "value"}

    def test_processed_segment_validation_empty_audio_data(self):
        """Test processed segment validation with empty audio data."""
        with pytest.raises(ValueError, match="audio_data cannot be empty"):
            ProcessedSegment(
                audio_data=b"",
                correlation_id="test-123",
                session_id="session-456",
                original_format=AudioFormat.PCM,
                processed_format=AudioFormat.PCM,
                sample_rate=16000,
                channels=1,
                duration=0.1,
                status=ProcessingStatus.COMPLETED,
                processing_time=0.01,
            )

    def test_processed_segment_validation_empty_correlation_id(self):
        """Test processed segment validation with empty correlation ID."""
        with pytest.raises(ValueError, match="correlation_id cannot be empty"):
            ProcessedSegment(
                audio_data=b"\x00" * 1024,
                correlation_id="",
                session_id="session-456",
                original_format=AudioFormat.PCM,
                processed_format=AudioFormat.PCM,
                sample_rate=16000,
                channels=1,
                duration=0.1,
                status=ProcessingStatus.COMPLETED,
                processing_time=0.01,
            )

    def test_processed_segment_validation_empty_session_id(self):
        """Test processed segment validation with empty session ID."""
        with pytest.raises(ValueError, match="session_id cannot be empty"):
            ProcessedSegment(
                audio_data=b"\x00" * 1024,
                correlation_id="test-123",
                session_id="",
                original_format=AudioFormat.PCM,
                processed_format=AudioFormat.PCM,
                sample_rate=16000,
                channels=1,
                duration=0.1,
                status=ProcessingStatus.COMPLETED,
                processing_time=0.01,
            )

    def test_processed_segment_validation_negative_sample_rate(self):
        """Test processed segment validation with negative sample rate."""
        with pytest.raises(ValueError, match="sample_rate must be positive"):
            ProcessedSegment(
                audio_data=b"\x00" * 1024,
                correlation_id="test-123",
                session_id="session-456",
                original_format=AudioFormat.PCM,
                processed_format=AudioFormat.PCM,
                sample_rate=-1,
                channels=1,
                duration=0.1,
                status=ProcessingStatus.COMPLETED,
                processing_time=0.01,
            )

    def test_processed_segment_validation_negative_channels(self):
        """Test processed segment validation with negative channels."""
        with pytest.raises(ValueError, match="channels must be positive"):
            ProcessedSegment(
                audio_data=b"\x00" * 1024,
                correlation_id="test-123",
                session_id="session-456",
                original_format=AudioFormat.PCM,
                processed_format=AudioFormat.PCM,
                sample_rate=16000,
                channels=-1,
                duration=0.1,
                status=ProcessingStatus.COMPLETED,
                processing_time=0.01,
            )

    def test_processed_segment_validation_negative_duration(self):
        """Test processed segment validation with negative duration."""
        with pytest.raises(ValueError, match="duration must be positive"):
            ProcessedSegment(
                audio_data=b"\x00" * 1024,
                correlation_id="test-123",
                session_id="session-456",
                original_format=AudioFormat.PCM,
                processed_format=AudioFormat.PCM,
                sample_rate=16000,
                channels=1,
                duration=-0.1,
                status=ProcessingStatus.COMPLETED,
                processing_time=0.01,
            )

    def test_processed_segment_validation_negative_processing_time(self):
        """Test processed segment validation with negative processing time."""
        with pytest.raises(ValueError, match="processing_time must be non-negative"):
            ProcessedSegment(
                audio_data=b"\x00" * 1024,
                correlation_id="test-123",
                session_id="session-456",
                original_format=AudioFormat.PCM,
                processed_format=AudioFormat.PCM,
                sample_rate=16000,
                channels=1,
                duration=0.1,
                status=ProcessingStatus.COMPLETED,
                processing_time=-0.01,
            )

    def test_processed_segment_validation_invalid_wake_confidence(self):
        """Test processed segment validation with invalid wake confidence."""
        with pytest.raises(ValueError, match="wake_confidence must be between 0.0 and 1.0"):
            ProcessedSegment(
                audio_data=b"\x00" * 1024,
                correlation_id="test-123",
                session_id="session-456",
                original_format=AudioFormat.PCM,
                processed_format=AudioFormat.PCM,
                sample_rate=16000,
                channels=1,
                duration=0.1,
                status=ProcessingStatus.COMPLETED,
                processing_time=0.01,
                wake_confidence=1.5,
            )

    def test_processed_segment_validation_invalid_volume_level(self):
        """Test processed segment validation with invalid volume level."""
        with pytest.raises(ValueError, match="volume_level must be between 0.0 and 1.0"):
            ProcessedSegment(
                audio_data=b"\x00" * 1024,
                correlation_id="test-123",
                session_id="session-456",
                original_format=AudioFormat.PCM,
                processed_format=AudioFormat.PCM,
                sample_rate=16000,
                channels=1,
                duration=0.1,
                status=ProcessingStatus.COMPLETED,
                processing_time=0.01,
                volume_level=1.5,
            )

    def test_processed_segment_validation_invalid_noise_level(self):
        """Test processed segment validation with invalid noise level."""
        with pytest.raises(ValueError, match="noise_level must be between 0.0 and 1.0"):
            ProcessedSegment(
                audio_data=b"\x00" * 1024,
                correlation_id="test-123",
                session_id="session-456",
                original_format=AudioFormat.PCM,
                processed_format=AudioFormat.PCM,
                sample_rate=16000,
                channels=1,
                duration=0.1,
                status=ProcessingStatus.COMPLETED,
                processing_time=0.01,
                noise_level=1.5,
            )

    def test_processed_segment_validation_invalid_clarity_score(self):
        """Test processed segment validation with invalid clarity score."""
        with pytest.raises(ValueError, match="clarity_score must be between 0.0 and 1.0"):
            ProcessedSegment(
                audio_data=b"\x00" * 1024,
                correlation_id="test-123",
                session_id="session-456",
                original_format=AudioFormat.PCM,
                processed_format=AudioFormat.PCM,
                sample_rate=16000,
                channels=1,
                duration=0.1,
                status=ProcessingStatus.COMPLETED,
                processing_time=0.01,
                clarity_score=1.5,
            )

    def test_processed_segment_size_bytes(self):
        """Test processed segment size_bytes property."""
        segment = ProcessedSegment(
            audio_data=b"\x00" * 1024,
            correlation_id="test-123",
            session_id="session-456",
            original_format=AudioFormat.PCM,
            processed_format=AudioFormat.PCM,
            sample_rate=16000,
            channels=1,
            duration=0.1,
            status=ProcessingStatus.COMPLETED,
            processing_time=0.01,
        )
        
        assert segment.size_bytes == 1024

    def test_processed_segment_is_high_quality_true(self):
        """Test processed segment is_high_quality property when True."""
        segment = ProcessedSegment(
            audio_data=b"\x00" * 1024,
            correlation_id="test-123",
            session_id="session-456",
            original_format=AudioFormat.PCM,
            processed_format=AudioFormat.PCM,
            sample_rate=16000,
            channels=1,
            duration=0.1,
            status=ProcessingStatus.COMPLETED,
            processing_time=0.01,
            clarity_score=0.8,
            noise_level=0.2,
            volume_level=0.5,
        )
        
        assert segment.is_high_quality is True

    def test_processed_segment_is_high_quality_false(self):
        """Test processed segment is_high_quality property when False."""
        segment = ProcessedSegment(
            audio_data=b"\x00" * 1024,
            correlation_id="test-123",
            session_id="session-456",
            original_format=AudioFormat.PCM,
            processed_format=AudioFormat.PCM,
            sample_rate=16000,
            channels=1,
            duration=0.1,
            status=ProcessingStatus.COMPLETED,
            processing_time=0.01,
            clarity_score=0.5,
            noise_level=0.5,
            volume_level=0.05,
        )
        
        assert segment.is_high_quality is False

    def test_processed_segment_get_summary(self):
        """Test processed segment get_summary method."""
        segment = ProcessedSegment(
            audio_data=b"\x00" * 1024,
            correlation_id="test-123",
            session_id="session-456",
            original_format=AudioFormat.PCM,
            processed_format=AudioFormat.WAV,
            sample_rate=16000,
            channels=1,
            duration=0.1,
            status=ProcessingStatus.COMPLETED,
            processing_time=0.01,
            wake_detected=True,
            wake_phrase="hello bot",
            wake_confidence=0.9,
            volume_level=0.8,
            noise_level=0.1,
            clarity_score=0.9,
        )
        
        summary = segment.get_summary()
        
        assert summary["correlation_id"] == "test-123"
        assert summary["session_id"] == "session-456"
        assert summary["status"] == "completed"
        assert summary["duration"] == 0.1
        assert summary["size_bytes"] == 1024
        assert summary["sample_rate"] == 16000
        assert summary["channels"] == 1
        assert summary["wake_detected"] is True
        assert summary["wake_phrase"] == "hello bot"
        assert summary["wake_confidence"] == 0.9
        assert summary["volume_level"] == 0.8
        assert summary["noise_level"] == 0.1
        assert summary["clarity_score"] == 0.9
        assert summary["is_high_quality"] is True
        assert summary["processing_time"] == 0.01
        assert "created_at" in summary
        assert "processed_at" in summary
