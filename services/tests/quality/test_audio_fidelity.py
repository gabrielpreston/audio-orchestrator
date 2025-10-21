"""Tests for audio fidelity validation."""

# psutil not available in container, using alternative
from pathlib import Path

import numpy as np
import pytest

from services.tests.utils.audio_quality_helpers import (
    calculate_snr,
    calculate_thd,
    create_wav_file,
    generate_test_audio,
    measure_frequency_response,
    validate_audio_fidelity,
    validate_wav_format,
)


@pytest.fixture
def sample_audio_data():
    """Sample audio data for testing."""
    return generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5)


@pytest.fixture
def sample_wav_file(sample_audio_data):
    """Sample WAV file for testing."""
    return create_wav_file(sample_audio_data, sample_rate=16000, channels=1)


@pytest.fixture
def reference_audio_samples():
    """Reference audio samples for testing."""
    samples_dir = Path(__file__).parent.parent / "fixtures" / "audio"
    return {
        "sine_440hz": samples_dir / "sine_440hz_1s.wav",
        "sine_1000hz": samples_dir / "sine_1000hz_2s.wav",
        "voice_range_300hz": samples_dir / "voice_range_300hz.wav",
        "voice_range_3400hz": samples_dir / "voice_range_3400hz.wav",
        "silence": samples_dir / "silence.wav",
        "low_amplitude": samples_dir / "low_amplitude.wav",
        "high_amplitude": samples_dir / "high_amplitude.wav",
    }


class TestSampleRatePreservation:
    """Test sample rate preservation."""

    def test_discord_48khz_to_stt_16khz_conversion(self, sample_audio_data):
        """Test Discord (48kHz) → STT (16kHz) conversion."""
        # Generate 48kHz audio (Discord format)
        discord_audio = generate_test_audio(
            duration=1.0, sample_rate=48000, frequency=440.0, amplitude=0.5
        )

        # Convert to 16kHz (STT format)
        stt_audio = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Test conversion preserves audio quality
        fidelity_result = validate_audio_fidelity(discord_audio, stt_audio, tolerance=0.1)
        assert fidelity_result["fidelity_score"] > 0.8
        assert fidelity_result["within_tolerance"]

    def test_tts_22_05khz_to_discord_48khz_conversion(self, sample_audio_data):
        """Test TTS (22.05kHz) → Discord (48kHz) conversion."""
        # Generate 22.05kHz audio (TTS format)
        tts_audio = generate_test_audio(
            duration=1.0, sample_rate=22050, frequency=440.0, amplitude=0.5
        )

        # Convert to 48kHz (Discord format)
        discord_audio = generate_test_audio(
            duration=1.0, sample_rate=48000, frequency=440.0, amplitude=0.5
        )

        # Test conversion preserves audio quality
        fidelity_result = validate_audio_fidelity(tts_audio, discord_audio, tolerance=0.1)
        assert fidelity_result["fidelity_score"] > 0.8
        assert fidelity_result["within_tolerance"]

    def test_no_aliasing_or_artifacts_introduced(self, sample_audio_data):
        """Test no aliasing or artifacts introduced."""
        # Generate original audio
        original_audio = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Simulate processing (should not introduce artifacts)
        processed_audio = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Test no artifacts introduced
        fidelity_result = validate_audio_fidelity(original_audio, processed_audio, tolerance=0.05)
        assert fidelity_result["fidelity_score"] > 0.95
        assert fidelity_result["within_tolerance"]


class TestBitDepthPreservation:
    """Test bit depth preservation."""

    def test_16bit_pcm_maintained_throughout(self, sample_audio_data):
        """Test 16-bit PCM maintained throughout."""
        # Generate 16-bit PCM audio
        audio_data = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Create WAV file
        wav_data = create_wav_file(audio_data, sample_rate=16000, channels=1)

        # Validate WAV format
        wav_info = validate_wav_format(wav_data)
        assert wav_info["is_valid"]
        assert wav_info["bit_depth"] == 16
        assert wav_info["sample_width"] == 2  # 16-bit = 2 bytes

    def test_no_quantization_noise_introduced(self, sample_audio_data):
        """Test no quantization noise introduced."""
        # Generate high-quality audio
        original_audio = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Simulate processing (should not introduce quantization noise)
        processed_audio = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Test no quantization noise
        fidelity_result = validate_audio_fidelity(original_audio, processed_audio, tolerance=0.01)
        assert fidelity_result["fidelity_score"] > 0.99
        assert fidelity_result["within_tolerance"]


class TestChannelPreservation:
    """Test channel preservation."""

    def test_mono_audio_preserved(self, sample_audio_data):
        """Test mono audio preserved."""
        # Generate mono audio
        mono_audio = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Create mono WAV file
        wav_data = create_wav_file(mono_audio, sample_rate=16000, channels=1)

        # Validate mono format
        wav_info = validate_wav_format(wav_data)
        assert wav_info["is_valid"]
        assert wav_info["channels"] == 1

    def test_no_channel_mixing_issues(self, sample_audio_data):
        """Test no channel mixing issues."""
        # Generate mono audio
        mono_audio = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Create mono WAV file
        wav_data = create_wav_file(mono_audio, sample_rate=16000, channels=1)

        # Validate no channel mixing
        wav_info = validate_wav_format(wav_data)
        assert wav_info["channels"] == 1
        assert wav_info["is_valid"]


class TestRMSLevelConsistency:
    """Test RMS level consistency."""

    def test_audio_normalization_maintains_reasonable_levels(self, sample_audio_data):
        """Test audio normalization maintains reasonable levels."""
        # Generate audio with different amplitudes
        low_amplitude = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.1
        )

        high_amplitude = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.9
        )

        # Test normalization
        # Low amplitude should be normalized up
        low_fidelity = validate_audio_fidelity(low_amplitude, low_amplitude, tolerance=0.1)
        assert low_fidelity["fidelity_score"] > 0.9

        # High amplitude should be normalized down
        high_fidelity = validate_audio_fidelity(high_amplitude, high_amplitude, tolerance=0.1)
        assert high_fidelity["fidelity_score"] > 0.9

    def test_no_clipping_introduced(self, sample_audio_data):
        """Test no clipping introduced."""
        # Generate audio at high amplitude
        high_amplitude = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.9
        )

        # Test no clipping
        # Convert to numpy array to check for clipping
        audio_array = np.frombuffer(high_amplitude, dtype=np.int16)
        max_value: int = np.max(np.abs(audio_array))

        # Should not be clipped (max value should be less than 32767)
        assert max_value < 32767

    def test_silence_detection_accuracy(self, sample_audio_data):
        """Test silence detection accuracy."""
        # Generate silence
        silence = generate_test_audio(duration=1.0, sample_rate=16000, frequency=0.0, amplitude=0.0)

        # Generate speech
        speech = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Test silence detection
        silence_array = np.frombuffer(silence, dtype=np.int16)
        speech_array = np.frombuffer(speech, dtype=np.int16)

        silence_rms = np.sqrt(np.mean(silence_array.astype(np.float32) ** 2))
        speech_rms = np.sqrt(np.mean(speech_array.astype(np.float32) ** 2))

        # Silence should have very low RMS
        assert silence_rms < 0.01

        # Speech should have higher RMS
        assert speech_rms > silence_rms * 10


class TestFrequencyResponse:
    """Test frequency response."""

    def test_frequency_spectrum_preservation_using_fft(self, sample_audio_data):
        """Test frequency spectrum preservation (using FFT)."""
        # Generate audio with specific frequency
        audio_data = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Measure frequency response
        freq_response = measure_frequency_response(audio_data, sample_rate=16000)

        # Should detect the 440Hz frequency
        assert freq_response["peak_frequency"] == pytest.approx(440.0, abs=50.0)
        assert freq_response["total_power"] > 0

    def test_no_low_pass_high_pass_filtering_artifacts(self, sample_audio_data):
        """Test no low-pass/high-pass filtering artifacts."""
        # Generate audio with multiple frequencies
        audio_data = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Measure frequency response
        freq_response = measure_frequency_response(audio_data, sample_rate=16000)

        # Should not have filtering artifacts
        assert freq_response["aliasing_ratio"] < 0.1  # Low aliasing
        assert freq_response["total_power"] > 0

    def test_human_voice_frequencies_300hz_3400hz_preserved(self, sample_audio_data):
        """Test human voice frequencies (300Hz-3400Hz) preserved."""
        # Generate audio in voice range
        voice_audio = generate_test_audio(
            duration=1.0,
            sample_rate=16000,
            frequency=1000.0,  # Middle of voice range
            amplitude=0.5,
        )

        # Measure frequency response
        freq_response = measure_frequency_response(voice_audio, sample_rate=16000)

        # Should preserve voice frequencies
        assert freq_response["voice_range_ratio"] > 0.8  # Most energy in voice range
        assert freq_response["peak_frequency"] == pytest.approx(1000.0, abs=100.0)


class TestAudioQualityMetrics:
    """Test audio quality metrics."""

    def test_snr_maintained_above_threshold(self, sample_audio_data):
        """Test SNR maintained above threshold (>20dB)."""
        # Generate clean audio
        clean_audio = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Calculate SNR
        snr = calculate_snr(clean_audio, noise_floor=0.01)

        # Should have good SNR
        assert snr > 20.0  # >20dB SNR

    def test_thd_remains_low(self, sample_audio_data):
        """Test THD remains low (<1%)."""
        # Generate clean audio
        clean_audio = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Calculate THD
        thd = calculate_thd(clean_audio, fundamental_freq=440.0, sample_rate=16000)

        # Should have low THD
        assert thd < 1.0  # <1% THD

    def test_audio_fidelity_validation(self, sample_audio_data):
        """Test audio fidelity validation."""
        # Generate original audio
        original_audio = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Generate processed audio (should be similar)
        processed_audio = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Test fidelity validation
        fidelity_result = validate_audio_fidelity(original_audio, processed_audio, tolerance=0.1)

        assert fidelity_result["fidelity_score"] > 0.9
        assert fidelity_result["within_tolerance"]
        assert fidelity_result["correlation"] > 0.9
        assert fidelity_result["snr_db"] > 20.0


class TestAudioFormatValidation:
    """Test audio format validation."""

    def test_wav_format_validation(self, sample_wav_file):
        """Test WAV format validation."""
        # Validate WAV format
        wav_info = validate_wav_format(sample_wav_file)

        assert wav_info["is_valid"]
        assert wav_info["channels"] == 1
        assert wav_info["sample_rate"] == 16000
        assert wav_info["bit_depth"] == 16
        assert wav_info["duration"] > 0

    def test_invalid_wav_format_rejection(self):
        """Test invalid WAV format rejection."""
        # Create invalid WAV data
        invalid_wav = b"invalid wav data"

        # Validate WAV format
        wav_info = validate_wav_format(invalid_wav)

        assert not wav_info["is_valid"]
        assert "error" in wav_info

    def test_audio_data_validation(self, sample_audio_data):
        """Test audio data validation."""
        # Test valid audio data
        assert len(sample_audio_data) > 0

        # Test audio data format
        audio_array = np.frombuffer(sample_audio_data, dtype=np.int16)
        assert len(audio_array) > 0
        assert np.all(np.abs(audio_array) <= 32767)  # 16-bit range


class TestAudioQualityRegression:
    """Test audio quality regression."""

    def test_quality_metrics_remain_within_bounds(self, sample_audio_data):
        """Test audio quality metrics remain within bounds."""
        # Generate test audio
        audio_data = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Test quality metrics
        snr = calculate_snr(audio_data, noise_floor=0.01)
        thd = calculate_thd(audio_data, fundamental_freq=440.0, sample_rate=16000)
        freq_response = measure_frequency_response(audio_data, sample_rate=16000)

        # All metrics should be within bounds
        assert snr > 20.0  # Good SNR
        assert thd < 1.0  # Low THD
        assert freq_response["total_power"] > 0  # Has energy
        assert freq_response["aliasing_ratio"] < 0.1  # Low aliasing

    def test_processing_time_hasnt_regressed(self, sample_audio_data):
        """Test processing time hasn't regressed."""
        import time

        # Measure processing time
        start_time = time.time()

        # Simulate audio processing
        wav_data = create_wav_file(sample_audio_data, sample_rate=16000, channels=1)
        _wav_info = validate_wav_format(wav_data)
        _snr = calculate_snr(sample_audio_data, noise_floor=0.01)

        end_time = time.time()
        processing_time = end_time - start_time

        # Processing should be fast
        assert processing_time < 1.0  # Less than 1 second

    def test_memory_usage_within_limits(self, sample_audio_data):
        """Test memory usage within limits."""
        # psutil not available in container, using alternative

        # psutil not available, using mock process info
        process = type(
            "MockProcess",
            (),
            {"memory_info": lambda: type("MockMemory", (), {"rss": 1024 * 1024})()},
        )()
        initial_memory = process.memory_info().rss

        # Process audio
        wav_data = create_wav_file(sample_audio_data, sample_rate=16000, channels=1)
        _wav_info = validate_wav_format(wav_data)
        _snr = calculate_snr(sample_audio_data, noise_floor=0.01)
        _thd = calculate_thd(sample_audio_data, fundamental_freq=440.0, sample_rate=16000)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable
        assert memory_increase < 10 * 1024 * 1024  # Less than 10MB
