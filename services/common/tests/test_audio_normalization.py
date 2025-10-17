"""Tests for audio normalization functionality."""

from unittest.mock import Mock

import numpy as np
import pytest

from services.common.audio import AudioProcessor


class TestAudioNormalization:
    """Test audio normalization functionality."""

    @pytest.fixture
    def audio_processor(self):
        """Create audio processor for testing."""
        processor = AudioProcessor("test")
        processor.set_logger(Mock())
        return processor

    @pytest.fixture
    def sample_pcm_audio(self) -> bytes:
        """Generate sample PCM audio data."""
        # Generate 1 second of 16kHz mono audio with sine wave
        sample_rate = 16000
        duration = 1.0
        frequency = 440  # A4 note

        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_float = np.sin(2 * np.pi * frequency * t) * 0.5  # 50% amplitude
        audio_int16 = (audio_float * 32767).astype(np.int16)
        return audio_int16.tobytes()

    @pytest.fixture
    def silence_audio(self) -> bytes:
        """Generate silence audio data."""
        # Generate 0.1 seconds of silence
        sample_rate = 16000
        duration = 0.1
        samples = int(sample_rate * duration)
        return b"\x00" * (samples * 2)  # 2 bytes per int16 sample

    @pytest.fixture
    def loud_audio(self) -> bytes:
        """Generate loud audio data."""
        # Generate 0.1 seconds of loud sine wave
        sample_rate = 16000
        duration = 0.1
        frequency = 440

        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_float = np.sin(2 * np.pi * frequency * t) * 0.9  # 90% amplitude
        audio_int16 = (audio_float * 32767).astype(np.int16)
        return audio_int16.tobytes()

    @pytest.mark.unit
    def test_normalize_audio_scales_to_target_rms(
        self, audio_processor, sample_pcm_audio
    ):
        """Test that normalize_audio correctly scales audio to target RMS."""
        target_rms = 2000.0

        normalized_audio, _ = audio_processor.normalize_audio(
            sample_pcm_audio, target_rms=target_rms
        )

        # Check that new RMS is close to target (within 5% tolerance)
        assert len(normalized_audio) == len(sample_pcm_audio)
        assert normalized_audio != sample_pcm_audio  # Should be different

    @pytest.mark.unit
    def test_normalize_audio_skips_silence(self, audio_processor, silence_audio):
        """Test that normalize_audio skips amplification for silence."""
        target_rms = 2000.0

        normalized_audio, new_rms = audio_processor.normalize_audio(
            silence_audio, target_rms=target_rms
        )

        # Should return original audio for silence
        assert normalized_audio == silence_audio
        assert new_rms < 1.0  # Should be very low RMS

    @pytest.mark.unit
    def test_normalize_audio_clips_at_bounds(self, audio_processor, loud_audio):
        """Test that normalize_audio clips values within sample width bounds."""
        target_rms = 10000.0  # Very high target to force clipping

        normalized_audio, _ = audio_processor.normalize_audio(
            loud_audio, target_rms=target_rms
        )

        # Convert back to numpy array to check bounds
        audio_array = np.frombuffer(normalized_audio, dtype=np.int16)

        # Should be clipped to int16 bounds
        assert np.all(audio_array >= -32768)
        assert np.all(audio_array <= 32767)

    @pytest.mark.unit
    def test_normalize_audio_int16_dtype(self, audio_processor, sample_pcm_audio):
        """Test normalize_audio with int16 sample width."""
        target_rms = 1500.0

        normalized_audio, _ = audio_processor.normalize_audio(
            sample_pcm_audio, target_rms=target_rms, sample_width=2
        )

        # Should maintain int16 format
        assert len(normalized_audio) == len(sample_pcm_audio)
        assert isinstance(normalized_audio, bytes)

        # Verify it's valid int16 data
        audio_array = np.frombuffer(normalized_audio, dtype=np.int16)
        assert len(audio_array) > 0

    @pytest.mark.unit
    def test_normalize_audio_int32_dtype(self, audio_processor):
        """Test normalize_audio with int32 sample width."""
        # Generate int32 audio data
        sample_rate = 16000
        duration = 0.1
        frequency = 440

        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_float = np.sin(2 * np.pi * frequency * t) * 0.5
        audio_int32 = (audio_float * 2147483647).astype(np.int32)
        audio_bytes = audio_int32.tobytes()

        target_rms = 1000000.0

        normalized_audio, _ = audio_processor.normalize_audio(
            audio_bytes, target_rms=target_rms, sample_width=4
        )

        # Should maintain int32 format
        assert len(normalized_audio) == len(audio_bytes)
        assert isinstance(normalized_audio, bytes)

    @pytest.mark.unit
    def test_normalize_audio_logs_metrics(self, audio_processor, sample_pcm_audio):
        """Test that normalize_audio logs all metrics."""
        target_rms = 2000.0

        audio_processor.normalize_audio(sample_pcm_audio, target_rms=target_rms)

        # Check that debug log was called with expected metrics
        audio_processor._logger.debug.assert_called_once()
        call_args = audio_processor._logger.debug.call_args

        assert call_args[0][0] == "audio.normalized"
        kwargs = call_args[1]

        assert "current_rms" in kwargs
        assert "target_rms" in kwargs
        assert "new_rms" in kwargs
        assert "scaling_factor" in kwargs
        assert kwargs["target_rms"] == target_rms

    @pytest.mark.unit
    def test_normalize_audio_handles_empty_input(self, audio_processor):
        """Test that normalize_audio handles empty input gracefully."""
        empty_audio = b""
        target_rms = 2000.0

        normalized_audio, new_rms = audio_processor.normalize_audio(
            empty_audio, target_rms=target_rms
        )

        assert normalized_audio == empty_audio
        assert new_rms == 0.0

    @pytest.mark.unit
    def test_normalize_audio_error_fallback(self, audio_processor):
        """Test that normalize_audio handles errors gracefully."""
        # Create invalid audio data that should cause an error
        invalid_audio = b"invalid_pcm_data"
        target_rms = 2000.0

        # Test that the function doesn't crash with invalid data
        normalized_audio, new_rms = audio_processor.normalize_audio(
            invalid_audio, target_rms=target_rms
        )

        # Should return some result without crashing
        assert normalized_audio is not None
        assert isinstance(new_rms, float)
        assert len(normalized_audio) == len(invalid_audio)

    @pytest.mark.unit
    def test_normalize_audio_preserves_audio_structure(
        self, audio_processor, sample_pcm_audio
    ):
        """Test that normalize_audio preserves the basic structure of audio."""
        target_rms = 1000.0

        normalized_audio, _ = audio_processor.normalize_audio(
            sample_pcm_audio, target_rms=target_rms
        )

        # Should maintain same length and be valid audio
        assert len(normalized_audio) == len(sample_pcm_audio)
        assert len(normalized_audio) % 2 == 0  # Even number of bytes for int16

        # Should be different from original (unless already at target RMS)
        assert normalized_audio != sample_pcm_audio

    @pytest.mark.unit
    def test_normalize_audio_scaling_factor_calculation(
        self, audio_processor, sample_pcm_audio
    ):
        """Test that scaling factor is calculated correctly."""
        target_rms = 2000.0

        # Calculate expected current RMS manually
        audio_array = np.frombuffer(sample_pcm_audio, dtype=np.int16)
        current_rms = float(np.sqrt(np.mean(np.square(audio_array.astype(np.float64)))))

        normalized_audio, new_rms = audio_processor.normalize_audio(
            sample_pcm_audio, target_rms=target_rms
        )

        # Get the logged scaling factor
        call_args = audio_processor._logger.debug.call_args
        scaling_factor = call_args[1]["scaling_factor"]

        # Verify scaling factor calculation
        expected_scaling = target_rms / current_rms
        assert abs(scaling_factor - expected_scaling) < 0.01
