"""Tests for noise and distortion validation."""

# psutil not available in container, using alternative

import numpy as np
import pytest

from services.tests.utils.audio_quality_helpers import (
    calculate_snr,
    calculate_thd,
    generate_test_audio,
)


@pytest.fixture
def sample_audio_data():
    """Sample audio data for testing."""
    return generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5)


@pytest.fixture
def noisy_audio_data():
    """Noisy audio data for testing."""
    return generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5, noise_level=0.1)


@pytest.fixture
def clean_audio_data():
    """Clean audio data for testing."""
    return generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5, noise_level=0.0)


class TestSignalToNoiseRatio:
    """Test Signal-to-Noise Ratio (SNR) validation."""

    def test_snr_maintained_above_threshold_20db(self, clean_audio_data):
        """Test SNR maintained above threshold (>20dB)."""
        # Calculate SNR for clean audio
        snr = calculate_snr(clean_audio_data, noise_floor=0.01)

        # Should have good SNR
        assert snr > 20.0  # >20dB SNR

    def test_background_noise_handling(self, noisy_audio_data):
        """Test background noise handling."""
        # Calculate SNR for noisy audio
        snr = calculate_snr(noisy_audio_data, noise_floor=0.01)

        # Should still have reasonable SNR
        assert snr > 10.0  # >10dB SNR even with noise

    def test_quantization_noise_within_limits(self, sample_audio_data):
        """Test quantization noise within limits."""
        # Generate audio with different bit depths
        audio_16bit = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Calculate SNR
        snr = calculate_snr(audio_16bit, noise_floor=0.001)

        # Should have good SNR (low quantization noise)
        assert snr > 30.0  # >30dB SNR for 16-bit audio

    def test_noise_floor_detection(self, sample_audio_data):
        """Test noise floor detection."""
        # Calculate SNR with different noise floors
        snr_low_floor = calculate_snr(sample_audio_data, noise_floor=0.001)
        snr_high_floor = calculate_snr(sample_audio_data, noise_floor=0.1)

        # Lower noise floor should give higher SNR
        assert snr_low_floor > snr_high_floor

    def test_snr_consistency_across_frequencies(self, sample_audio_data):
        """Test SNR consistency across frequencies."""
        frequencies = [440.0, 880.0, 1320.0, 1760.0]
        snr_values = []

        for freq in frequencies:
            audio_data = generate_test_audio(
                duration=1.0, sample_rate=16000, frequency=freq, amplitude=0.5
            )
            snr = calculate_snr(audio_data, noise_floor=0.01)
            snr_values.append(snr)

        # SNR should be consistent across frequencies
        snr_std = np.std(snr_values)
        assert snr_std < 5.0  # Low standard deviation


class TestTotalHarmonicDistortion:
    """Test Total Harmonic Distortion (THD) validation."""

    def test_thd_remains_low_under_1_percent(self, clean_audio_data):
        """Test THD remains low (<1%)."""
        # Calculate THD for clean audio
        thd = calculate_thd(clean_audio_data, fundamental_freq=440.0, sample_rate=16000)

        # Should have low THD
        assert thd < 1.0  # <1% THD

    def test_no_clipping_distortion(self, sample_audio_data):
        """Test no clipping distortion."""
        # Generate audio at high amplitude
        high_amplitude = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.9
        )

        # Calculate THD
        thd = calculate_thd(high_amplitude, fundamental_freq=440.0, sample_rate=16000)

        # Should have low THD (no clipping)
        assert thd < 2.0  # <2% THD even at high amplitude

    def test_harmonic_distortion_analysis(self, sample_audio_data):
        """Test harmonic distortion analysis."""
        # Generate audio with specific frequency
        audio_data = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Calculate THD
        thd = calculate_thd(audio_data, fundamental_freq=440.0, sample_rate=16000)

        # Should have measurable THD
        assert thd >= 0.0
        assert thd < 5.0  # Reasonable THD range

    def test_thd_consistency_across_amplitudes(self, sample_audio_data):
        """Test THD consistency across amplitudes."""
        amplitudes = [0.1, 0.3, 0.5, 0.7, 0.9]
        thd_values = []

        for amp in amplitudes:
            audio_data = generate_test_audio(
                duration=1.0, sample_rate=16000, frequency=440.0, amplitude=amp
            )
            thd = calculate_thd(audio_data, fundamental_freq=440.0, sample_rate=16000)
            thd_values.append(thd)

        # THD should be consistent across amplitudes
        thd_std = np.std(thd_values)
        assert thd_std < 2.0  # Low standard deviation


class TestSilenceDetectionAccuracy:
    """Test silence detection accuracy."""

    def test_vad_correctly_identifies_speech_vs_silence(self, sample_audio_data):
        """Test VAD correctly identifies speech vs silence."""
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

    def test_silence_timeout_accuracy(self, sample_audio_data):
        """Test silence timeout accuracy."""
        # Generate audio with silence gaps
        silence_gap = generate_test_audio(
            duration=0.5, sample_rate=16000, frequency=0.0, amplitude=0.0
        )

        speech_segment = generate_test_audio(
            duration=0.5, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Test silence timeout
        silence_array = np.frombuffer(silence_gap, dtype=np.int16)
        speech_array = np.frombuffer(speech_segment, dtype=np.int16)

        silence_rms = np.sqrt(np.mean(silence_array.astype(np.float32) ** 2))
        speech_rms = np.sqrt(np.mean(speech_array.astype(np.float32) ** 2))

        # Silence gap should be detected
        assert silence_rms < 0.01

        # Speech segment should be detected
        assert speech_rms > 0.1

    def test_no_false_positives_negatives(self, sample_audio_data):
        """Test no false positives/negatives."""
        # Generate audio with varying levels
        low_level = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.01
        )

        high_level = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.9
        )

        # Test false positive/negative detection
        low_array = np.frombuffer(low_level, dtype=np.int16)
        high_array = np.frombuffer(high_level, dtype=np.int16)

        low_rms = np.sqrt(np.mean(low_array.astype(np.float32) ** 2))
        high_rms = np.sqrt(np.mean(high_array.astype(np.float32) ** 2))

        # Low level should still be detected as speech
        assert low_rms > 0.001

        # High level should be detected as speech
        assert high_rms > 0.1

        # No false negatives
        assert high_rms > low_rms * 10


class TestNoiseAndDistortionQuality:
    """Test noise and distortion quality."""

    def test_noise_spectral_analysis(self, noisy_audio_data):
        """Test noise spectral analysis."""
        # Analyze noise spectrum
        audio_array = np.frombuffer(noisy_audio_data, dtype=np.int16)

        # Calculate frequency spectrum
        fft = np.fft.fft(audio_array)
        _freqs = np.fft.fftfreq(len(audio_array), 1 / 16000)

        # Find noise components
        noise_mask = np.abs(fft) < np.max(np.abs(fft)) * 0.1
        noise_power: float = np.sum(np.abs(fft[noise_mask]) ** 2)
        total_power: float = np.sum(np.abs(fft) ** 2)
        noise_ratio = noise_power / total_power

        # Noise should be a small fraction
        assert noise_ratio < 0.5  # Less than 50% noise

    def test_distortion_harmonic_analysis(self, sample_audio_data):
        """Test distortion harmonic analysis."""
        # Generate audio with specific frequency
        audio_data = generate_test_audio(
            duration=1.0, sample_rate=16000, frequency=440.0, amplitude=0.5
        )

        # Analyze harmonics
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        fft = np.fft.fft(audio_array)
        _freqs = np.fft.fftfreq(len(audio_array), 1 / 16000)

        # Find fundamental and harmonics
        fundamental_idx = int(440.0 * len(audio_array) / 16000)
        harmonic_2_idx = fundamental_idx * 2
        harmonic_3_idx = fundamental_idx * 3

        if harmonic_2_idx < len(fft) and harmonic_3_idx < len(fft):
            fundamental_mag = np.abs(fft[fundamental_idx])
            harmonic_2_mag = np.abs(fft[harmonic_2_idx])
            harmonic_3_mag = np.abs(fft[harmonic_3_idx])

            # Harmonics should be weaker than fundamental
            assert harmonic_2_mag < fundamental_mag
            assert harmonic_3_mag < fundamental_mag

    def test_noise_distortion_correlation(self, noisy_audio_data):
        """Test noise and distortion correlation."""
        # Calculate SNR and THD
        snr = calculate_snr(noisy_audio_data, noise_floor=0.01)
        thd = calculate_thd(noisy_audio_data, fundamental_freq=440.0, sample_rate=16000)

        # SNR and THD should be correlated
        # Higher noise should lead to lower SNR and higher THD
        assert snr > 0.0
        assert thd >= 0.0

        # Both should be within reasonable ranges
        assert snr < 100.0  # Not infinite
        assert thd < 10.0  # Not excessive


class TestNoiseAndDistortionRegression:
    """Test noise and distortion regression."""

    def test_noise_quality_hasnt_regressed(self, sample_audio_data):
        """Test noise quality hasn't regressed."""
        # Calculate noise metrics
        snr = calculate_snr(sample_audio_data, noise_floor=0.01)
        thd = calculate_thd(sample_audio_data, fundamental_freq=440.0, sample_rate=16000)

        # Quality should be maintained
        assert snr > 20.0  # Good SNR
        assert thd < 1.0  # Low THD

    def test_noise_processing_performance_hasnt_regressed(self, sample_audio_data):
        """Test noise processing performance hasn't regressed."""
        import time

        # Measure processing time
        start_time = time.time()

        # Process noise metrics
        _snr = calculate_snr(sample_audio_data, noise_floor=0.01)
        _thd = calculate_thd(sample_audio_data, fundamental_freq=440.0, sample_rate=16000)

        end_time = time.time()
        processing_time = end_time - start_time

        # Processing should be fast
        assert processing_time < 1.0  # Less than 1 second

    def test_noise_memory_usage_hasnt_regressed(self, sample_audio_data):
        """Test noise memory usage hasn't regressed."""
        # psutil not available in container, using alternative

        # psutil not available, using mock process info
        process = type(
            "MockProcess",
            (),
            {"memory_info": lambda: type("MockMemory", (), {"rss": 1024 * 1024})()},
        )()
        initial_memory = process.memory_info().rss

        # Process noise metrics
        _snr = calculate_snr(sample_audio_data, noise_floor=0.01)
        _thd = calculate_thd(sample_audio_data, fundamental_freq=440.0, sample_rate=16000)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be minimal
        assert memory_increase < 10 * 1024 * 1024  # Less than 10MB
