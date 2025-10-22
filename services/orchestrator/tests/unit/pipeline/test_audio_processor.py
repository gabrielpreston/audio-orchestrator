"""Unit tests for audio processor."""

import pytest

from services.orchestrator.adapters.types import AudioChunk, AudioMetadata
from services.orchestrator.pipeline.audio_processor import AudioProcessor
from services.orchestrator.pipeline.types import (
    AudioFormat,
    ProcessingConfig,
    ProcessingStatus,
)


class TestAudioProcessor:
    """Test AudioProcessor class."""

    def test_audio_processor_creation(self):
        """Test creating an audio processor."""
        config = ProcessingConfig()
        processor = AudioProcessor(config)

        assert processor.config == config
        assert processor.config.target_sample_rate == 16000
        assert processor.config.target_channels == 1
        assert processor.config.target_format == AudioFormat.PCM

    def test_audio_processor_creation_with_defaults(self):
        """Test creating an audio processor with default config."""
        processor = AudioProcessor()

        assert processor.config is not None
        assert processor.config.target_sample_rate == 16000
        assert processor.config.target_channels == 1

    @pytest.mark.asyncio
    async def test_process_audio_chunk_success(self):
        """Test successful audio chunk processing."""
        config = ProcessingConfig()
        processor = AudioProcessor(config)

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

        # Process the chunk
        result = await processor.process_audio_chunk(audio_chunk, "session-456")

        assert result.correlation_id == "test-123"
        assert result.session_id == "session-456"
        assert result.status == ProcessingStatus.COMPLETED
        assert result.original_format == AudioFormat.PCM
        assert result.processed_format == AudioFormat.PCM
        assert result.sample_rate == 16000
        assert result.channels == 1
        assert result.processing_time > 0
        assert 0.0 <= result.volume_level <= 1.0
        assert 0.0 <= result.noise_level <= 1.0
        assert 0.0 <= result.clarity_score <= 1.0

    @pytest.mark.asyncio
    async def test_process_audio_chunk_with_enhancement(self):
        """Test audio chunk processing with enhancement enabled."""
        config = ProcessingConfig(
            enable_audio_enhancement=True,
            enable_noise_reduction=True,
            enable_volume_normalization=True,
        )
        processor = AudioProcessor(config)

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
            correlation_id="test-456",
            sequence_number=1,
        )

        result = await processor.process_audio_chunk(audio_chunk, "session-789")

        assert result.status == ProcessingStatus.COMPLETED
        assert "enhancement" in result.metadata.get("processing_stages", [])
        assert "noise_reduction" in result.metadata.get("processing_stages", [])
        assert "normalization" in result.metadata.get("processing_stages", [])

    @pytest.mark.asyncio
    async def test_process_audio_chunk_without_enhancement(self):
        """Test audio chunk processing without enhancement."""
        config = ProcessingConfig(
            enable_audio_enhancement=False,
            enable_noise_reduction=False,
            enable_volume_normalization=False,
        )
        processor = AudioProcessor(config)

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
            correlation_id="test-789",
            sequence_number=1,
        )

        result = await processor.process_audio_chunk(audio_chunk, "session-101")

        assert result.status == ProcessingStatus.COMPLETED
        assert "enhancement" not in result.metadata.get("processing_stages", [])
        assert "noise_reduction" not in result.metadata.get("processing_stages", [])
        assert "normalization" not in result.metadata.get("processing_stages", [])

    @pytest.mark.asyncio
    async def test_get_capabilities(self):
        """Test getting processor capabilities."""
        config = ProcessingConfig()
        processor = AudioProcessor(config)

        capabilities = await processor.get_capabilities()

        assert "supported_formats" in capabilities
        assert "target_sample_rate" in capabilities
        assert "target_channels" in capabilities
        assert "target_format" in capabilities
        assert "enhancement_enabled" in capabilities
        assert "noise_reduction_enabled" in capabilities
        assert "normalization_enabled" in capabilities

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        config = ProcessingConfig()
        processor = AudioProcessor(config)

        health = await processor.health_check()

        assert health["status"] == "healthy"
        assert health["processor_type"] == "AudioProcessor"
        assert "config" in health
        assert "capabilities" in health

    @pytest.mark.asyncio
    async def test_calculate_volume_level(self):
        """Test volume level calculation."""
        config = ProcessingConfig()
        processor = AudioProcessor(config)

        # Test with empty data
        volume = await processor._calculate_volume_level(b"")
        assert volume == 0.0

        # Test with mock data
        volume = await processor._calculate_volume_level(b"\x00" * 1024)
        assert 0.0 <= volume <= 1.0

    @pytest.mark.asyncio
    async def test_calculate_noise_level(self):
        """Test noise level calculation."""
        config = ProcessingConfig()
        processor = AudioProcessor(config)

        noise = await processor._calculate_noise_level(b"\x00" * 1024)
        assert 0.0 <= noise <= 1.0

    @pytest.mark.asyncio
    async def test_calculate_clarity_score(self):
        """Test clarity score calculation."""
        config = ProcessingConfig()
        processor = AudioProcessor(config)

        clarity = await processor._calculate_clarity_score(b"\x00" * 1024)
        assert 0.0 <= clarity <= 1.0
