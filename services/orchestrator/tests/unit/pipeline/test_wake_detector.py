"""Unit tests for wake detector."""

import pytest

from services.orchestrator.pipeline.types import (
    AudioFormat,
    ProcessedSegment,
    ProcessingConfig,
    ProcessingStatus,
)
from services.orchestrator.pipeline.wake_detector import WakeDetector


class TestWakeDetector:
    """Test WakeDetector class."""

    def test_wake_detector_creation(self):
        """Test creating a wake detector."""
        config = ProcessingConfig()
        detector = WakeDetector(config)

        assert detector.config == config
        assert detector.config.wake_phrases == ["hey assistant", "computer"]
        assert detector.config.wake_confidence_threshold == 0.8
        assert detector.config.wake_detection_enabled is True

    def test_wake_detector_creation_with_custom_phrases(self):
        """Test creating a wake detector with custom phrases."""
        config = ProcessingConfig(
            wake_phrases=["hello bot", "wake up"],
            wake_confidence_threshold=0.9,
        )
        detector = WakeDetector(config)

        assert detector.config.wake_phrases == ["hello bot", "wake up"]
        assert detector.config.wake_confidence_threshold == 0.9

    def test_wake_detector_creation_with_defaults(self):
        """Test creating a wake detector with default config."""
        detector = WakeDetector()

        assert detector.config is not None
        assert detector.config.wake_phrases == ["hey assistant", "computer"]

    @pytest.mark.asyncio
    async def test_detect_wake_phrase_enabled(self):
        """Test wake phrase detection when enabled."""
        config = ProcessingConfig(wake_detection_enabled=True)
        detector = WakeDetector(config)

        # Create processed segment
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

        result = await detector.detect_wake_phrase(segment)

        assert result.correlation_id == "test-123"
        assert result.session_id == "session-456"
        # Wake detection results are set (may be True or False due to random mock)
        assert isinstance(result.wake_detected, bool)
        assert isinstance(result.wake_confidence, float)
        assert 0.0 <= result.wake_confidence <= 1.0

    @pytest.mark.asyncio
    async def test_detect_wake_phrase_disabled(self):
        """Test wake phrase detection when disabled."""
        config = ProcessingConfig(wake_detection_enabled=False)
        detector = WakeDetector(config)

        segment = ProcessedSegment(
            audio_data=b"\x00" * 1024,
            correlation_id="test-456",
            session_id="session-789",
            original_format=AudioFormat.PCM,
            processed_format=AudioFormat.PCM,
            sample_rate=16000,
            channels=1,
            duration=0.1,
            status=ProcessingStatus.COMPLETED,
            processing_time=0.01,
        )

        result = await detector.detect_wake_phrase(segment)

        # Should return unchanged segment when disabled
        assert result.correlation_id == "test-456"
        assert result.session_id == "session-789"
        assert result.wake_detected is False
        assert result.wake_phrase is None
        assert result.wake_confidence == 0.0

    @pytest.mark.asyncio
    async def test_update_wake_phrases(self):
        """Test updating wake phrases."""
        config = ProcessingConfig()
        detector = WakeDetector(config)

        new_phrases = ["new phrase", "another phrase"]
        await detector.update_wake_phrases(new_phrases)

        assert detector.config.wake_phrases == new_phrases

    @pytest.mark.asyncio
    async def test_set_confidence_threshold(self):
        """Test setting confidence threshold."""
        config = ProcessingConfig()
        detector = WakeDetector(config)

        new_threshold = 0.9
        await detector.set_confidence_threshold(new_threshold)

        assert detector.config.wake_confidence_threshold == new_threshold

    @pytest.mark.asyncio
    async def test_set_confidence_threshold_invalid(self):
        """Test setting invalid confidence threshold."""
        config = ProcessingConfig()
        detector = WakeDetector(config)

        with pytest.raises(
            ValueError, match="Confidence threshold must be between 0.0 and 1.0"
        ):
            await detector.set_confidence_threshold(1.5)

    @pytest.mark.asyncio
    async def test_get_capabilities(self):
        """Test getting wake detector capabilities."""
        config = ProcessingConfig()
        detector = WakeDetector(config)

        capabilities = await detector.get_capabilities()

        assert "wake_phrases" in capabilities
        assert "confidence_threshold" in capabilities
        assert "enabled" in capabilities
        assert "model_count" in capabilities
        assert "supported_models" in capabilities

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        config = ProcessingConfig()
        detector = WakeDetector(config)

        health = await detector.health_check()

        assert health["status"] == "healthy"
        assert health["detector_type"] == "WakeDetector"
        assert "enabled" in health
        assert "wake_phrases" in health
        assert "confidence_threshold" in health
        assert "model_count" in health
