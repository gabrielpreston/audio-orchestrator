"""Unit tests for audio pipeline."""

import pytest

from services.orchestrator.adapters.types import AudioChunk, AudioMetadata
from services.orchestrator.pipeline.audio_processor import AudioProcessor
from services.orchestrator.pipeline.pipeline import AudioPipeline
from services.orchestrator.pipeline.types import ProcessingConfig, ProcessingStatus
from services.orchestrator.pipeline.wake_detector import WakeDetector


class TestAudioPipeline:
    """Test AudioPipeline class."""

    def test_audio_pipeline_creation(self):
        """Test creating an audio pipeline."""
        config = ProcessingConfig()
        processor = AudioProcessor(config)
        wake_detector = WakeDetector(config)
        pipeline = AudioPipeline(processor, wake_detector, config)

        assert pipeline.config == config
        assert pipeline.audio_processor == processor
        assert pipeline.wake_detector == wake_detector

    def test_audio_pipeline_creation_with_defaults(self):
        """Test creating an audio pipeline with default components."""
        pipeline = AudioPipeline()

        assert pipeline.config is not None
        assert pipeline.audio_processor is not None
        assert pipeline.wake_detector is not None

    @pytest.mark.asyncio
    async def test_process_single_chunk(self):
        """Test processing a single audio chunk."""
        pipeline = AudioPipeline()

        # Create mock audio chunk
        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.1,
            frames=4800,
            format="pcm",
            bit_depth=16,
        )

        audio_chunk = AudioChunk(
            data=b"\x00" * 1024,
            metadata=metadata,
            correlation_id="test-123",
            sequence_number=1,
        )

        result = await pipeline.process_single_chunk(audio_chunk, "session-456")

        assert result.correlation_id == "test-123"
        assert result.session_id == "session-456"
        assert result.status == ProcessingStatus.COMPLETED
        assert result.sample_rate == 16000
        assert result.channels == 1

    @pytest.mark.asyncio
    async def test_process_audio_stream(self):
        """Test processing an audio stream."""
        pipeline = AudioPipeline()

        # Create mock audio chunks
        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.1,
            frames=4800,
            format="pcm",
            bit_depth=16,
        )

        audio_chunks = [
            AudioChunk(
                data=b"\x00" * 1024,
                metadata=metadata,
                correlation_id=f"test-{i}",
                sequence_number=i,
            )
            for i in range(3)
        ]

        async def mock_audio_stream():
            for chunk in audio_chunks:
                yield chunk

        # Process the stream
        results = []
        async for result in pipeline.process_audio_stream(
            mock_audio_stream(), "session-789"
        ):
            results.append(result)

        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.correlation_id == f"test-{i}"
            assert result.session_id == "session-789"
            assert result.status == ProcessingStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_process_audio_stream_with_multiple_chunks(self):
        """Test processing audio stream with multiple chunks."""
        pipeline = AudioPipeline()

        # Create mock audio chunks
        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.1,
            frames=4800,
            format="pcm",
            bit_depth=16,
        )

        audio_chunks = [
            AudioChunk(
                data=b"\x00" * 1024,
                metadata=metadata,
                correlation_id="test-1",
                sequence_number=1,
            ),
            AudioChunk(
                data=b"\x00" * 512,
                metadata=metadata,
                correlation_id="test-2",
                sequence_number=2,
            ),
            AudioChunk(
                data=b"\x00" * 1024,
                metadata=metadata,
                correlation_id="test-3",
                sequence_number=3,
            ),
        ]

        async def mock_audio_stream():
            for chunk in audio_chunks:
                yield chunk

        # Process the stream
        results = []
        async for result in pipeline.process_audio_stream(
            mock_audio_stream(), "session-101"
        ):
            results.append(result)

        # Should get all successful results
        assert len(results) == 3
        assert results[0].correlation_id == "test-1"
        assert results[1].correlation_id == "test-2"
        assert results[2].correlation_id == "test-3"

    @pytest.mark.asyncio
    async def test_get_statistics(self):
        """Test getting pipeline statistics."""
        pipeline = AudioPipeline()

        # Process some chunks to generate statistics
        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.1,
            frames=4800,
            format="pcm",
            bit_depth=16,
        )

        audio_chunk = AudioChunk(
            data=b"\x00" * 1024,
            metadata=metadata,
            correlation_id="test-stats",
            sequence_number=1,
        )

        await pipeline.process_single_chunk(audio_chunk, "session-stats")

        stats = await pipeline.get_statistics()

        assert "processed_count" in stats
        assert "failed_count" in stats
        assert "wake_detected_count" in stats
        assert "success_rate" in stats
        assert "wake_detection_rate" in stats
        assert stats["processed_count"] >= 1

    @pytest.mark.asyncio
    async def test_reset_statistics(self):
        """Test resetting pipeline statistics."""
        pipeline = AudioPipeline()

        # Process some chunks to generate statistics
        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.1,
            frames=4800,
            format="pcm",
            bit_depth=16,
        )

        audio_chunk = AudioChunk(
            data=b"\x00" * 1024,
            metadata=metadata,
            correlation_id="test-reset",
            sequence_number=1,
        )

        await pipeline.process_single_chunk(audio_chunk, "session-reset")

        # Check statistics are non-zero
        stats_before = await pipeline.get_statistics()
        assert stats_before["processed_count"] > 0

        # Reset statistics
        await pipeline.reset_statistics()

        # Check statistics are zero
        stats_after = await pipeline.get_statistics()
        assert stats_after["processed_count"] == 0
        assert stats_after["failed_count"] == 0
        assert stats_after["wake_detected_count"] == 0

    @pytest.mark.asyncio
    async def test_get_capabilities(self):
        """Test getting pipeline capabilities."""
        pipeline = AudioPipeline()

        capabilities = await pipeline.get_capabilities()

        assert "pipeline_type" in capabilities
        assert "config" in capabilities
        assert "processor" in capabilities
        assert "wake_detector" in capabilities
        assert capabilities["pipeline_type"] == "AudioPipeline"

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        pipeline = AudioPipeline()

        health = await pipeline.health_check()

        assert health["status"] == "healthy"
        assert health["pipeline_type"] == "AudioPipeline"
        assert "statistics" in health
        assert "processor" in health
        assert "wake_detector" in health
