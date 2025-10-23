"""Tests for the audio enhancement module."""

from unittest.mock import Mock

import numpy as np
import pytest

from services.audio_processor.enhancement import AudioEnhancer


class TestAudioEnhancer:
    """Test cases for AudioEnhancer class."""

    @pytest.fixture
    def mock_enhancement_class(self):
        """Mock enhancement class for testing."""
        mock_class = Mock()
        mock_instance = Mock()
        mock_instance.enhance_batch.return_value = Mock()
        mock_class.from_hparams.return_value = mock_instance
        return mock_class

    @pytest.fixture
    def audio_enhancer(self, mock_enhancement_class):
        """Create AudioEnhancer instance for testing."""
        return AudioEnhancer(
            enable_metricgan=True,
            device="cpu",
            enhancement_class=mock_enhancement_class,
        )

    @pytest.fixture
    def audio_enhancer_disabled(self):
        """Create AudioEnhancer instance with enhancement disabled."""
        return AudioEnhancer(enable_metricgan=False)

    @pytest.fixture
    def sample_audio_array(self):
        """Create sample audio array for testing."""
        # Generate 1 second of 16kHz audio
        sample_rate = 16000
        duration = 1.0
        samples = int(sample_rate * duration)

        # Generate sine wave with noise
        frequency = 440  # A4 note
        t = np.linspace(0, duration, samples, False)
        signal = np.sin(2 * np.pi * frequency * t)
        noise = np.random.normal(0, 0.1, samples)
        audio = signal + noise

        return audio.astype(np.float32)

    def test_initialization_with_metricgan(self, audio_enhancer):
        """Test initialization with MetricGAN enabled."""
        assert audio_enhancer.enable_metricgan is True
        assert audio_enhancer.device == "cpu"
        assert audio_enhancer.is_enhancement_enabled is True

    def test_initialization_without_metricgan(self, audio_enhancer_disabled):
        """Test initialization with MetricGAN disabled."""
        assert audio_enhancer_disabled.enable_metricgan is False
        assert audio_enhancer_disabled.is_enhancement_enabled is False

    def test_apply_high_pass_filter(self, audio_enhancer, sample_audio_array):
        """Test high-pass filter application."""
        filtered_audio = audio_enhancer.apply_high_pass_filter(
            sample_audio_array, sample_rate=16000, cutoff_freq=80.0
        )

        assert isinstance(filtered_audio, np.ndarray)
        assert len(filtered_audio) == len(sample_audio_array)
        assert filtered_audio.dtype == np.float32

    def test_apply_high_pass_filter_invalid_cutoff(
        self, audio_enhancer, sample_audio_array
    ):
        """Test high-pass filter with invalid cutoff frequency."""
        # Test with cutoff frequency >= Nyquist frequency
        filtered_audio = audio_enhancer.apply_high_pass_filter(
            sample_audio_array,
            sample_rate=16000,
            cutoff_freq=8000.0,  # Half of sample rate
        )

        # Should return original audio
        assert np.array_equal(filtered_audio, sample_audio_array)

    def test_enhance_audio_with_metricgan(self, audio_enhancer, sample_audio_array):
        """Test audio enhancement with MetricGAN."""
        enhanced_audio = audio_enhancer.enhance_audio(
            sample_audio_array, sample_rate=16000
        )

        assert isinstance(enhanced_audio, np.ndarray)
        assert len(enhanced_audio) == len(sample_audio_array)
        assert enhanced_audio.dtype == np.float32

    def test_enhance_audio_without_metricgan(
        self, audio_enhancer_disabled, sample_audio_array
    ):
        """Test audio enhancement without MetricGAN."""
        enhanced_audio = audio_enhancer_disabled.enhance_audio(
            sample_audio_array, sample_rate=16000
        )

        # Should return original audio when enhancement is disabled
        assert np.array_equal(enhanced_audio, sample_audio_array)

    def test_enhance_audio_pipeline(self, audio_enhancer, sample_audio_array):
        """Test complete audio enhancement pipeline."""
        enhanced_audio = audio_enhancer.enhance_audio_pipeline(
            sample_audio_array,
            sample_rate=16000,
            apply_high_pass=True,
            high_pass_cutoff=80.0,
        )

        assert isinstance(enhanced_audio, np.ndarray)
        assert len(enhanced_audio) == len(sample_audio_array)
        assert enhanced_audio.dtype == np.float32

    def test_enhance_audio_pipeline_without_high_pass(
        self, audio_enhancer, sample_audio_array
    ):
        """Test audio enhancement pipeline without high-pass filter."""
        enhanced_audio = audio_enhancer.enhance_audio_pipeline(
            sample_audio_array, sample_rate=16000, apply_high_pass=False
        )

        assert isinstance(enhanced_audio, np.ndarray)
        assert len(enhanced_audio) == len(sample_audio_array)
        assert enhanced_audio.dtype == np.float32

    @pytest.mark.asyncio
    async def test_enhance_audio_bytes(self, audio_enhancer):
        """Test audio enhancement with bytes input."""
        # Create sample audio bytes
        sample_rate = 16000
        duration = 1.0
        samples = int(sample_rate * duration)

        # Generate sine wave
        frequency = 440
        t = np.linspace(0, duration, samples, False)
        audio_data = np.sin(2 * np.pi * frequency * t)

        # Convert to int16 PCM bytes
        pcm_data = (audio_data * 32767).astype(np.int16).tobytes()

        enhanced_bytes = await audio_enhancer.enhance_audio(pcm_data)

        assert isinstance(enhanced_bytes, bytes)
        assert len(enhanced_bytes) > 0

    @pytest.mark.asyncio
    async def test_enhance_audio_bytes_error_handling(self, audio_enhancer):
        """Test audio enhancement error handling with bytes input."""
        # Test with empty bytes
        enhanced_bytes = await audio_enhancer.enhance_audio(b"")

        assert isinstance(enhanced_bytes, bytes)
        assert len(enhanced_bytes) == 0

    def test_get_enhancement_info(self, audio_enhancer):
        """Test enhancement information retrieval."""
        info = audio_enhancer.get_enhancement_info()

        assert isinstance(info, dict)
        assert "enhancement_enabled" in info
        assert "metricgan_available" in info
        assert "device" in info
        assert "model_source" in info

        assert isinstance(info["enhancement_enabled"], bool)
        assert isinstance(info["metricgan_available"], bool)
        assert isinstance(info["device"], str)
        assert isinstance(info["model_source"], str)

    def test_enhancement_info_disabled(self, audio_enhancer_disabled):
        """Test enhancement information when disabled."""
        info = audio_enhancer_disabled.get_enhancement_info()

        assert info["enhancement_enabled"] is False
        assert info["metricgan_available"] is False

    def test_high_pass_filter_edge_cases(self, audio_enhancer):
        """Test high-pass filter with edge cases."""
        # Test with very short audio
        short_audio = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        filtered = audio_enhancer.apply_high_pass_filter(short_audio, 16000, 80.0)

        assert isinstance(filtered, np.ndarray)
        assert len(filtered) == len(short_audio)

        # Test with zero audio
        zero_audio = np.zeros(1000, dtype=np.float32)
        filtered = audio_enhancer.apply_high_pass_filter(zero_audio, 16000, 80.0)

        assert isinstance(filtered, np.ndarray)
        assert len(filtered) == len(zero_audio)

    def test_enhancement_with_different_sample_rates(self, audio_enhancer):
        """Test enhancement with different sample rates."""
        # Test with 8kHz audio
        audio_8k = np.random.randn(8000).astype(np.float32)
        enhanced_8k = audio_enhancer.enhance_audio(audio_8k, sample_rate=8000)

        assert isinstance(enhanced_8k, np.ndarray)
        assert len(enhanced_8k) == len(audio_8k)

        # Test with 48kHz audio
        audio_48k = np.random.randn(48000).astype(np.float32)
        enhanced_48k = audio_enhancer.enhance_audio(audio_48k, sample_rate=48000)

        assert isinstance(enhanced_48k, np.ndarray)
        assert len(enhanced_48k) == len(audio_48k)
