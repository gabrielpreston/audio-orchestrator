"""
Tests for audio contract and media gateway.

This module validates that the canonical audio contract is properly
enforced and that media gateway conversions work correctly.
"""

import pytest

from services.common.surfaces.audio_contract import AudioContract, AudioContractSpec
from services.common.surfaces.media_gateway import JitterBuffer, MediaGateway


class TestAudioContractSpec:
    """Test AudioContractSpec data structure."""

    def test_contract_spec_defaults(self):
        """Test default contract specification values."""
        spec = AudioContractSpec()

        assert spec.sample_rate == 16000
        assert spec.channels == 1
        assert spec.sample_width == 2
        assert spec.bit_depth == 16
        assert spec.frame_duration_ms == 20.0
        assert spec.frame_size_samples == 320
        assert spec.transport_codec == "opus"
        assert spec.transport_sample_rate == 48000

    def test_contract_spec_properties(self):
        """Test calculated properties."""
        spec = AudioContractSpec()

        assert spec.frame_size_bytes == 640  # 320 * 1 * 2
        assert spec.bytes_per_second == 32000  # 16000 * 1 * 2


class TestAudioContract:
    """Test AudioContract validation and normalization."""

    def test_contract_creation(self):
        """Test creating AudioContract with default spec."""
        contract = AudioContract()
        assert contract.spec.sample_rate == 16000
        assert contract.spec.channels == 1

    def test_contract_creation_custom_spec(self):
        """Test creating AudioContract with custom spec."""
        spec = AudioContractSpec(sample_rate=8000, channels=2)
        contract = AudioContract(spec)
        assert contract.spec.sample_rate == 8000
        assert contract.spec.channels == 2

    def test_validate_audio_data_valid(self):
        """Test validation with valid audio data."""
        contract = AudioContract()
        audio_data = b"\x00\x01\x02\x03" * 100  # Some PCM data
        metadata = {
            "sample_rate": 16000,
            "channels": 1,
            "sample_width": 2,
        }

        assert contract.validate_audio_data(audio_data, metadata) is True

    def test_validate_audio_data_invalid_sample_rate(self):
        """Test validation with invalid sample rate."""
        contract = AudioContract()
        audio_data = b"\x00\x01\x02\x03" * 100
        metadata = {
            "sample_rate": 48000,  # Wrong rate
            "channels": 1,
            "sample_width": 2,
        }

        assert contract.validate_audio_data(audio_data, metadata) is False

    def test_validate_audio_data_invalid_channels(self):
        """Test validation with invalid channels."""
        contract = AudioContract()
        audio_data = b"\x00\x01\x02\x03" * 100
        metadata = {
            "sample_rate": 16000,
            "channels": 2,  # Wrong channels
            "sample_width": 2,
        }

        assert contract.validate_audio_data(audio_data, metadata) is False

    def test_validate_audio_data_empty(self):
        """Test validation with empty audio data."""
        contract = AudioContract()
        audio_data = b""
        metadata = {
            "sample_rate": 16000,
            "channels": 1,
            "sample_width": 2,
        }

        assert contract.validate_audio_data(audio_data, metadata) is False

    def test_normalize_audio_no_change_needed(self):
        """Test normalization when no changes are needed."""
        contract = AudioContract()
        audio_data = b"\x00\x01\x02\x03" * 100
        metadata = {
            "sample_rate": 16000,
            "channels": 1,
            "sample_width": 2,
        }

        normalized_data, normalized_metadata = contract.normalize_audio(
            audio_data, metadata
        )

        assert normalized_data == audio_data
        assert normalized_metadata["sample_rate"] == 16000
        assert normalized_metadata["channels"] == 1
        assert normalized_metadata["sample_width"] == 2

    def test_extract_metadata_wav(self):
        """Test metadata extraction from WAV data."""
        contract = AudioContract()

        # Create a simple WAV file in memory
        import io
        import wave

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b"\x00\x01" * 100)

        wav_data = buffer.getvalue()
        metadata = contract.extract_metadata(wav_data)

        assert metadata["sample_rate"] == 16000
        assert metadata["channels"] == 1
        assert metadata["sample_width"] == 2
        assert metadata["format"] == "wav"

    def test_extract_metadata_pcm(self):
        """Test metadata extraction from PCM data."""
        contract = AudioContract()
        pcm_data = b"\x00\x01" * 100

        metadata = contract.extract_metadata(pcm_data)

        assert metadata["sample_rate"] == 16000
        assert metadata["channels"] == 1
        assert metadata["sample_width"] == 2
        assert metadata["format"] == "pcm"


class TestJitterBuffer:
    """Test JitterBuffer functionality."""

    def test_jitter_buffer_creation(self):
        """Test creating JitterBuffer with defaults."""
        buffer = JitterBuffer()

        assert buffer.max_size == 10
        assert buffer.target_latency_ms == 100.0
        assert buffer.current_frames == []

    def test_jitter_buffer_add_frame(self):
        """Test adding frames to jitter buffer."""
        buffer = JitterBuffer()

        audio_data = b"\x00\x01\x02\x03"
        timestamp = 1234567890.0

        buffer.add_frame(audio_data, timestamp)

        assert len(buffer.current_frames) == 1
        assert buffer.current_frames[0] == (audio_data, timestamp)

    def test_jitter_buffer_get_ready_frames(self):
        """Test getting ready frames from jitter buffer."""
        buffer = JitterBuffer()
        current_time = 1234567890.0

        # Add frame that's ready
        buffer.add_frame(b"\x00\x01", current_time - 0.2)  # 200ms old

        # Add frame that's not ready
        buffer.add_frame(b"\x02\x03", current_time - 0.05)  # 50ms old

        ready_frames = buffer.get_ready_frames(current_time)

        assert len(ready_frames) == 1
        assert ready_frames[0] == b"\x00\x01"
        assert len(buffer.current_frames) == 1  # One frame removed

    def test_jitter_buffer_is_empty(self):
        """Test checking if jitter buffer is empty."""
        buffer = JitterBuffer()

        assert buffer.is_empty() is True

        buffer.add_frame(b"\x00\x01", 1234567890.0)
        assert buffer.is_empty() is False


class TestMediaGateway:
    """Test MediaGateway functionality."""

    def test_media_gateway_creation(self):
        """Test creating MediaGateway with defaults."""
        gateway = MediaGateway()

        assert gateway.contract is not None
        assert gateway.enable_jitter_buffer is True
        assert gateway.jitter_buffer is not None

    def test_media_gateway_creation_no_jitter_buffer(self):
        """Test creating MediaGateway without jitter buffer."""
        gateway = MediaGateway(enable_jitter_buffer=False)

        assert gateway.enable_jitter_buffer is False
        assert gateway.jitter_buffer is None

    @pytest.mark.asyncio
    async def test_normalize_audio_valid(self):
        """Test normalizing valid audio data."""
        gateway = MediaGateway()
        audio_data = b"\x00\x01\x02\x03" * 100
        metadata = {
            "sample_rate": 16000,
            "channels": 1,
            "sample_width": 2,
        }

        normalized_data, normalized_metadata = await gateway.normalize_audio(
            audio_data, metadata, "pcm"
        )

        assert normalized_data == audio_data
        assert normalized_metadata["sample_rate"] == 16000
        assert normalized_metadata["channels"] == 1
        assert normalized_metadata["sample_width"] == 2

    @pytest.mark.asyncio
    async def test_normalize_audio_to_wav(self):
        """Test normalizing audio to WAV format."""
        gateway = MediaGateway()
        audio_data = b"\x00\x01\x02\x03" * 100
        metadata = {
            "sample_rate": 16000,
            "channels": 1,
            "sample_width": 2,
        }

        normalized_data, normalized_metadata = await gateway.normalize_audio(
            audio_data, metadata, "wav"
        )

        # Should have WAV header
        assert normalized_data.startswith(b"RIFF")
        assert normalized_metadata["format"] == "wav"

    @pytest.mark.asyncio
    async def test_convert_from_transport_pcm(self):
        """Test converting from PCM transport."""
        gateway = MediaGateway()
        audio_data = b"\x00\x01\x02\x03" * 100
        metadata = {
            "sample_rate": 16000,
            "channels": 1,
            "sample_width": 2,
        }

        converted_data, converted_metadata = await gateway.convert_from_transport(
            audio_data, "pcm", metadata
        )

        assert converted_data == audio_data
        assert converted_metadata["sample_rate"] == 16000

    @pytest.mark.asyncio
    async def test_convert_to_transport_pcm(self):
        """Test converting to PCM transport."""
        gateway = MediaGateway()
        audio_data = b"\x00\x01\x02\x03" * 100
        metadata = {
            "sample_rate": 16000,
            "channels": 1,
            "sample_width": 2,
        }

        converted_data, converted_metadata = await gateway.convert_to_transport(
            audio_data, metadata, "pcm"
        )

        assert converted_data == audio_data
        assert converted_metadata["sample_rate"] == 16000

    def test_jitter_buffer_operations(self):
        """Test jitter buffer operations."""
        gateway = MediaGateway()

        audio_data = b"\x00\x01\x02\x03"
        timestamp = 1234567890.0

        gateway.add_to_jitter_buffer(audio_data, timestamp)

        # Should have one frame in buffer
        assert len(gateway.jitter_buffer.current_frames) == 1

        # Get frames (none should be ready yet)
        ready_frames = gateway.get_from_jitter_buffer()
        assert len(ready_frames) == 0

        # Clear buffer
        gateway.clear_jitter_buffer()
        assert len(gateway.jitter_buffer.current_frames) == 0

    def test_performance_stats(self):
        """Test getting performance statistics."""
        gateway = MediaGateway()

        stats = gateway.get_performance_stats()

        assert "conversion_count" in stats
        assert "total_conversion_time" in stats
        assert "avg_conversion_time_ms" in stats
        assert "jitter_buffer_enabled" in stats
        assert "jitter_buffer_size" in stats

        assert stats["conversion_count"] == 0
        assert stats["total_conversion_time"] == 0.0
        assert stats["jitter_buffer_enabled"] is True
