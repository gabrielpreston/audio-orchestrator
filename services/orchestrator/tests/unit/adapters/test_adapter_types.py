"""Unit tests for adapter types."""

from datetime import datetime

import pytest

from services.orchestrator.adapters.types import (
    AdapterConfig,
    AudioChunk,
    AudioMetadata,
)


class TestAudioMetadata:
    """Test AudioMetadata class."""

    def test_audio_metadata_creation(self):
        """Test creating audio metadata."""
        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=1.0,
            frames=48000,
            format="pcm",
            bit_depth=16,
        )

        assert metadata.sample_rate == 48000
        assert metadata.channels == 2
        assert metadata.sample_width == 2
        assert metadata.duration == 1.0
        assert metadata.frames == 48000
        assert metadata.format == "pcm"
        assert metadata.bit_depth == 16
        assert isinstance(metadata.timestamp, datetime)

    def test_audio_metadata_validation(self):
        """Test audio metadata validation."""
        with pytest.raises(ValueError, match="sample_rate must be positive"):
            AudioMetadata(
                sample_rate=0,
                channels=2,
                sample_width=2,
                duration=1.0,
                frames=48000,
                format="pcm",
                bit_depth=16,
            )

        with pytest.raises(ValueError, match="channels must be positive"):
            AudioMetadata(
                sample_rate=48000,
                channels=0,
                sample_width=2,
                duration=1.0,
                frames=48000,
                format="pcm",
                bit_depth=16,
            )

        with pytest.raises(ValueError, match="duration must be non-negative"):
            AudioMetadata(
                sample_rate=48000,
                channels=2,
                sample_width=2,
                duration=-1.0,
                frames=48000,
                format="pcm",
                bit_depth=16,
            )


class TestAudioChunk:
    """Test AudioChunk class."""

    def test_audio_chunk_creation(self):
        """Test creating an audio chunk."""
        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.1,
            frames=4800,
            format="pcm",
            bit_depth=16,
        )

        chunk = AudioChunk(
            data=b"\x00" * 1024,
            metadata=metadata,
            correlation_id="test-123",
            sequence_number=1,
            is_silence=True,
            volume_level=0.0,
        )

        assert chunk.data == b"\x00" * 1024
        assert chunk.metadata == metadata
        assert chunk.correlation_id == "test-123"
        assert chunk.sequence_number == 1
        assert chunk.is_silence is True
        assert chunk.volume_level == 0.0

    def test_audio_chunk_properties(self):
        """Test audio chunk properties."""
        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.5,
            frames=24000,
            format="pcm",
            bit_depth=16,
        )

        chunk = AudioChunk(
            data=b"\x00" * 2048,
            metadata=metadata,
            correlation_id="test-456",
            sequence_number=2,
        )

        assert chunk.duration_seconds == 0.5
        assert chunk.size_bytes == 2048

    def test_audio_chunk_summary(self):
        """Test audio chunk summary."""
        metadata = AudioMetadata(
            sample_rate=44100,
            channels=1,
            sample_width=2,
            duration=0.25,
            frames=11025,
            format="pcm",
            bit_depth=16,
        )

        chunk = AudioChunk(
            data=b"\x00" * 1024,
            metadata=metadata,
            correlation_id="test-789",
            sequence_number=3,
            is_silence=False,
            volume_level=0.5,
        )

        summary = chunk.get_summary()

        assert summary["correlation_id"] == "test-789"
        assert summary["sequence_number"] == 3
        assert summary["duration_seconds"] == 0.25
        assert summary["size_bytes"] == 1024
        assert summary["sample_rate"] == 44100
        assert summary["channels"] == 1
        assert summary["is_silence"] is False
        assert summary["volume_level"] == 0.5
        assert summary["format"] == "pcm"

    def test_audio_chunk_validation(self):
        """Test audio chunk validation."""
        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.1,
            frames=4800,
            format="pcm",
            bit_depth=16,
        )

        with pytest.raises(ValueError, match="data cannot be empty"):
            AudioChunk(
                data=b"", metadata=metadata, correlation_id="test", sequence_number=1
            )

        with pytest.raises(ValueError, match="correlation_id cannot be empty"):
            AudioChunk(
                data=b"\x00" * 1024,
                metadata=metadata,
                correlation_id="",
                sequence_number=1,
            )

        with pytest.raises(ValueError, match="sequence_number must be non-negative"):
            AudioChunk(
                data=b"\x00" * 1024,
                metadata=metadata,
                correlation_id="test",
                sequence_number=-1,
            )

        with pytest.raises(
            ValueError, match="volume_level must be between 0.0 and 1.0"
        ):
            AudioChunk(
                data=b"\x00" * 1024,
                metadata=metadata,
                correlation_id="test",
                sequence_number=1,
                volume_level=1.5,
            )


class TestAdapterConfig:
    """Test AdapterConfig class."""

    def test_adapter_config_creation(self):
        """Test creating adapter config."""
        config = AdapterConfig(
            adapter_type="discord",
            name="discord_input",
            enabled=True,
            parameters={"channel_id": "123456789"},
            metadata={"version": "1.0"},
        )

        assert config.adapter_type == "discord"
        assert config.name == "discord_input"
        assert config.enabled is True
        assert config.parameters == {"channel_id": "123456789"}
        assert config.metadata == {"version": "1.0"}

    def test_adapter_config_defaults(self):
        """Test adapter config with defaults."""
        config = AdapterConfig(adapter_type="test", name="test_adapter")

        assert config.adapter_type == "test"
        assert config.name == "test_adapter"
        assert config.enabled is True
        assert config.parameters == {}
        assert config.metadata == {}

    def test_adapter_config_validation(self):
        """Test adapter config validation."""
        with pytest.raises(ValueError, match="adapter_type cannot be empty"):
            AdapterConfig(adapter_type="", name="test")

        with pytest.raises(ValueError, match="name cannot be empty"):
            AdapterConfig(adapter_type="test", name="")

        with pytest.raises(ValueError, match="parameters must be a dictionary"):
            AdapterConfig(
                adapter_type="test",
                name="test",
                parameters="not_a_dict",  # type: ignore
            )

    def test_adapter_config_methods(self):
        """Test adapter config methods."""
        config = AdapterConfig(
            adapter_type="test",
            name="test_adapter",
            parameters={"key1": "value1", "key2": "value2"},
            metadata={"meta1": "data1"},
        )

        # Test parameter methods
        assert config.get_parameter("key1") == "value1"
        assert config.get_parameter("nonexistent", "default") == "default"

        config.set_parameter("key3", "value3")
        assert config.get_parameter("key3") == "value3"

        # Test metadata methods
        assert config.get_metadata("meta1") == "data1"
        assert config.get_metadata("nonexistent", "default") == "default"

        config.set_metadata("meta2", "data2")
        assert config.get_metadata("meta2") == "data2"
