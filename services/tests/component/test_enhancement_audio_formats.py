"""Component tests for enhancement audio format edge cases."""

import io
import wave

import numpy as np
import pytest

from services.tests.fixtures.audio_samples import AudioSampleGenerator


@pytest.mark.component
class TestEnhancementAudioFormats:
    """Test enhancement with various audio format edge cases."""

    async def test_enhancement_with_different_sample_rates(self):
        """Test enhancement with various sample rates."""
        sample_rates = [8000, 16000, 22050, 44100, 48000]

        for sample_rate in sample_rates:
            # Generate test audio at different sample rates
            generator = AudioSampleGenerator(sample_rate=sample_rate)
            sample = generator.generate_clean_speech()

            from services.stt.app import _enhance_audio_if_enabled

            # Should handle different sample rates
            result = await _enhance_audio_if_enabled(sample.data)
            assert result is not None
            assert len(result) > 0

    async def test_enhancement_with_stereo_audio(self):
        """Test enhancement with stereo input."""
        # Create stereo audio sample
        generator = AudioSampleGenerator()
        mono_sample = generator.generate_clean_speech()

        # Convert to stereo (duplicate channel)
        stereo_data = self._convert_to_stereo(mono_sample.data)

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle stereo audio
        result = await _enhance_audio_if_enabled(stereo_data)
        assert result is not None
        assert len(result) > 0

    async def test_enhancement_with_mono_audio(self):
        """Test enhancement with mono audio."""
        generator = AudioSampleGenerator()
        mono_sample = generator.generate_clean_speech()

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle mono audio
        result = await _enhance_audio_if_enabled(mono_sample.data)
        assert result is not None
        assert len(result) > 0

    async def test_enhancement_with_very_short_audio(self):
        """Test enhancement with very short audio."""
        # Create very short audio (100ms)
        generator = AudioSampleGenerator(duration_seconds=0.1)
        short_sample = generator.generate_clean_speech()

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle very short audio
        result = await _enhance_audio_if_enabled(short_sample.data)
        assert result is not None
        assert len(result) > 0

    async def test_enhancement_with_very_long_audio(self):
        """Test enhancement with very long audio."""
        # Create very long audio (30 seconds)
        generator = AudioSampleGenerator(duration_seconds=30.0)
        long_sample = generator.generate_clean_speech()

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle very long audio
        result = await _enhance_audio_if_enabled(long_sample.data)
        assert result is not None
        assert len(result) > 0

    async def test_enhancement_with_silent_audio(self):
        """Test enhancement with silent audio."""
        # Create silent audio
        silent_audio = self._create_silent_audio()

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle silent audio
        result = await _enhance_audio_if_enabled(silent_audio)
        assert result is not None
        assert len(result) > 0

    async def test_enhancement_with_maximum_amplitude_audio(self):
        """Test enhancement with maximum amplitude audio."""
        # Create audio at maximum amplitude
        max_amp_audio = self._create_max_amplitude_audio()

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle maximum amplitude audio
        result = await _enhance_audio_if_enabled(max_amp_audio)
        assert result is not None
        assert len(result) > 0

    async def test_enhancement_with_dc_offset_audio(self):
        """Test enhancement with DC offset audio."""
        # Create audio with DC offset
        dc_offset_audio = self._create_dc_offset_audio()

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle DC offset audio
        result = await _enhance_audio_if_enabled(dc_offset_audio)
        assert result is not None
        assert len(result) > 0

    async def test_enhancement_with_clipped_audio(self):
        """Test enhancement with clipped audio."""
        # Create clipped audio
        clipped_audio = self._create_clipped_audio()

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle clipped audio
        result = await _enhance_audio_if_enabled(clipped_audio)
        assert result is not None
        assert len(result) > 0

    async def test_enhancement_with_low_bitrate_audio(self):
        """Test enhancement with low bitrate audio."""
        # Create low bitrate audio
        low_bitrate_audio = self._create_low_bitrate_audio()

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle low bitrate audio
        result = await _enhance_audio_if_enabled(low_bitrate_audio)
        assert result is not None
        assert len(result) > 0

    async def test_enhancement_with_high_frequency_audio(self):
        """Test enhancement with high frequency audio."""
        # Create high frequency audio
        high_freq_audio = self._create_high_frequency_audio()

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle high frequency audio
        result = await _enhance_audio_if_enabled(high_freq_audio)
        assert result is not None
        assert len(result) > 0

    async def test_enhancement_with_low_frequency_audio(self):
        """Test enhancement with low frequency audio."""
        # Create low frequency audio
        low_freq_audio = self._create_low_frequency_audio()

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle low frequency audio
        result = await _enhance_audio_if_enabled(low_freq_audio)
        assert result is not None
        assert len(result) > 0

    async def test_enhancement_with_impulse_audio(self):
        """Test enhancement with impulse audio."""
        # Create impulse audio
        impulse_audio = self._create_impulse_audio()

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle impulse audio
        result = await _enhance_audio_if_enabled(impulse_audio)
        assert result is not None
        assert len(result) > 0

    async def test_enhancement_with_white_noise_audio(self):
        """Test enhancement with white noise audio."""
        # Create white noise audio
        noise_audio = self._create_white_noise_audio()

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle white noise audio
        result = await _enhance_audio_if_enabled(noise_audio)
        assert result is not None
        assert len(result) > 0

    async def test_enhancement_with_empty_audio(self):
        """Test enhancement with empty audio."""
        # Create empty audio
        empty_audio = b""

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle empty audio gracefully
        result = await _enhance_audio_if_enabled(empty_audio)
        assert result == empty_audio

    async def test_enhancement_with_corrupted_wav_header(self):
        """Test enhancement with corrupted WAV header."""
        # Create corrupted WAV header
        corrupted_audio = b"RIFF\x00\x00\x00\x00WAVE"  # Minimal corrupted header

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle corrupted header gracefully
        result = await _enhance_audio_if_enabled(corrupted_audio)
        assert result == corrupted_audio

    async def test_enhancement_with_unsupported_format(self):
        """Test enhancement with unsupported audio format."""
        # Create unsupported format
        unsupported_audio = b"NOT_A_WAV_FILE"

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle unsupported format gracefully
        result = await _enhance_audio_if_enabled(unsupported_audio)
        assert result == unsupported_audio

    async def test_enhancement_with_very_large_audio(self):
        """Test enhancement with very large audio file."""
        # Create very large audio (10MB)
        large_audio = self._create_large_audio()

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle very large audio
        result = await _enhance_audio_if_enabled(large_audio)
        assert result is not None
        assert len(result) > 0

    async def test_enhancement_with_very_small_audio(self):
        """Test enhancement with very small audio file."""
        # Create very small audio (1KB)
        small_audio = self._create_small_audio()

        from services.stt.app import _enhance_audio_if_enabled

        # Should handle very small audio
        result = await _enhance_audio_if_enabled(small_audio)
        assert result is not None
        assert len(result) > 0

    # Helper methods for creating test audio
    def _convert_to_stereo(self, mono_data: bytes) -> bytes:
        """Convert mono audio to stereo."""
        # This is a simplified conversion
        return mono_data + mono_data

    def _create_silent_audio(self) -> bytes:
        """Create silent audio."""
        # Create 1 second of silence at 16kHz
        duration = 1.0
        sample_rate = 16000
        samples = int(duration * sample_rate)
        silent_data = np.zeros(samples, dtype=np.int16)

        # Convert to WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(silent_data.tobytes())

        return wav_buffer.getvalue()

    def _create_max_amplitude_audio(self) -> bytes:
        """Create audio at maximum amplitude."""
        duration = 1.0
        sample_rate = 16000
        samples = int(duration * sample_rate)
        max_amp_data = np.full(samples, 32767, dtype=np.int16)

        # Convert to WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(max_amp_data.tobytes())

        return wav_buffer.getvalue()

    def _create_dc_offset_audio(self) -> bytes:
        """Create audio with DC offset."""
        duration = 1.0
        sample_rate = 16000
        samples = int(duration * sample_rate)
        dc_offset_data = np.full(samples, 1000, dtype=np.int16)  # DC offset

        # Convert to WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(dc_offset_data.tobytes())

        return wav_buffer.getvalue()

    def _create_clipped_audio(self) -> bytes:
        """Create clipped audio."""
        duration = 1.0
        sample_rate = 16000
        samples = int(duration * sample_rate)
        clipped_data = np.full(samples, 32767, dtype=np.int16)  # Clipped

        # Convert to WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(clipped_data.tobytes())

        return wav_buffer.getvalue()

    def _create_low_bitrate_audio(self) -> bytes:
        """Create low bitrate audio."""
        duration = 1.0
        sample_rate = 8000  # Lower sample rate
        samples = int(duration * sample_rate)
        low_bitrate_data = np.random.randint(-1000, 1000, samples, dtype=np.int16)

        # Convert to WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(low_bitrate_data.tobytes())

        return wav_buffer.getvalue()

    def _create_high_frequency_audio(self) -> bytes:
        """Create high frequency audio."""
        duration = 1.0
        sample_rate = 16000
        samples = int(duration * sample_rate)
        t = np.linspace(0, duration, samples)
        high_freq_data = (np.sin(2 * np.pi * 8000 * t) * 16000).astype(
            np.int16
        )  # 8kHz tone

        # Convert to WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(high_freq_data.tobytes())

        return wav_buffer.getvalue()

    def _create_low_frequency_audio(self) -> bytes:
        """Create low frequency audio."""
        duration = 1.0
        sample_rate = 16000
        samples = int(duration * sample_rate)
        t = np.linspace(0, duration, samples)
        low_freq_data = (np.sin(2 * np.pi * 50 * t) * 16000).astype(
            np.int16
        )  # 50Hz tone

        # Convert to WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(low_freq_data.tobytes())

        return wav_buffer.getvalue()

    def _create_impulse_audio(self) -> bytes:
        """Create impulse audio."""
        duration = 1.0
        sample_rate = 16000
        samples = int(duration * sample_rate)
        impulse_data = np.zeros(samples, dtype=np.int16)
        impulse_data[0] = 32767  # Single impulse

        # Convert to WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(impulse_data.tobytes())

        return wav_buffer.getvalue()

    def _create_white_noise_audio(self) -> bytes:
        """Create white noise audio."""
        duration = 1.0
        sample_rate = 16000
        samples = int(duration * sample_rate)
        noise_data = np.random.randint(-1000, 1000, samples, dtype=np.int16)

        # Convert to WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(noise_data.tobytes())

        return wav_buffer.getvalue()

    def _create_large_audio(self) -> bytes:
        """Create very large audio file."""
        duration = 10.0  # 10 seconds
        sample_rate = 16000
        samples = int(duration * sample_rate)
        large_data = np.random.randint(-1000, 1000, samples, dtype=np.int16)

        # Convert to WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(large_data.tobytes())

        return wav_buffer.getvalue()

    def _create_small_audio(self) -> bytes:
        """Create very small audio file."""
        duration = 0.01  # 10ms
        sample_rate = 16000
        samples = int(duration * sample_rate)
        small_data = np.random.randint(-1000, 1000, samples, dtype=np.int16)

        # Convert to WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(small_data.tobytes())

        return wav_buffer.getvalue()
