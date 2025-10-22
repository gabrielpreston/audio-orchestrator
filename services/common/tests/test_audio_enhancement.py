"""Test audio enhancement module."""

import numpy as np
from unittest.mock import Mock, patch

from services.common.audio_enhancement import AudioEnhancer


def test_audio_enhancer_init_disabled():
    """Test AudioEnhancer initialization with MetricGAN disabled."""
    enhancer = AudioEnhancer(enable_metricgan=False)

    assert enhancer.enable_metricgan is False
    assert enhancer.device == "cpu"
    assert enhancer._metricgan_model is None
    assert enhancer.is_enhancement_enabled is False


@patch("services.common.audio_enhancement.SpectralMaskEnhancement")
def test_audio_enhancer_init_enabled(mock_spectral):
    """Test AudioEnhancer initialization with MetricGAN enabled."""
    mock_model = Mock()
    mock_spectral.from_hparams.return_value = mock_model

    enhancer = AudioEnhancer(enable_metricgan=True)

    assert enhancer.enable_metricgan is True
    assert enhancer._metricgan_model is mock_model
    assert enhancer.is_enhancement_enabled is True


@patch("services.common.audio_enhancement.SpectralMaskEnhancement")
def test_audio_enhancer_init_load_failure(mock_spectral):
    """Test AudioEnhancer initialization when model loading fails."""
    mock_spectral.from_hparams.side_effect = Exception("Model load failed")

    enhancer = AudioEnhancer(enable_metricgan=True)

    assert enhancer._metricgan_model is None
    assert enhancer.is_enhancement_enabled is False


def test_apply_high_pass_filter():
    """Test high-pass filter application."""
    enhancer = AudioEnhancer(enable_metricgan=False)

    # Create test audio with low-frequency content
    sample_rate = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Mix of low and high frequency
    low_freq = 50  # Below cutoff
    high_freq = 200  # Above cutoff
    audio = np.sin(2 * np.pi * low_freq * t) + 0.5 * np.sin(2 * np.pi * high_freq * t)

    # Apply high-pass filter
    filtered = enhancer.apply_high_pass_filter(audio, sample_rate, cutoff_freq=80.0)

    # Should reduce low-frequency content
    assert len(filtered) == len(audio)
    assert not np.array_equal(filtered, audio)


def test_apply_high_pass_filter_invalid_cutoff():
    """Test high-pass filter with invalid cutoff frequency."""
    enhancer = AudioEnhancer(enable_metricgan=False)

    audio = np.random.randn(16000)
    filtered = enhancer.apply_high_pass_filter(
        audio, sample_rate=16000, cutoff_freq=20000.0
    )

    # Should return original audio when cutoff is invalid
    assert np.array_equal(filtered, audio)


def test_enhance_audio_disabled():
    """Test audio enhancement when disabled."""
    enhancer = AudioEnhancer(enable_metricgan=False)

    audio = np.random.randn(16000).astype(np.float32)
    enhanced = enhancer.enhance_audio(audio)

    # Should return original audio when disabled
    assert np.array_equal(enhanced, audio)


@patch("services.common.audio_enhancement.SpectralMaskEnhancement")
def test_enhance_audio_enabled(mock_spectral):
    """Test audio enhancement when enabled."""
    # Mock the model
    mock_model = Mock()
    mock_enhanced = np.random.randn(16000).astype(np.float32)
    mock_model.enhance_batch.return_value = mock_enhanced
    mock_spectral.from_hparams.return_value = mock_model

    enhancer = AudioEnhancer(enable_metricgan=True)

    audio = np.random.randn(16000).astype(np.float32)
    enhanced = enhancer.enhance_audio(audio)

    # Should call the model
    mock_model.enhance_batch.assert_called_once()
    assert len(enhanced) == len(audio)


@patch("services.common.audio_enhancement.SpectralMaskEnhancement")
def test_enhance_audio_failure(mock_spectral):
    """Test audio enhancement when model fails."""
    # Mock the model to raise exception
    mock_model = Mock()
    mock_model.enhance_batch.side_effect = Exception("Enhancement failed")
    mock_spectral.from_hparams.return_value = mock_model

    enhancer = AudioEnhancer(enable_metricgan=True)

    audio = np.random.randn(16000).astype(np.float32)
    enhanced = enhancer.enhance_audio(audio)

    # Should return original audio on failure
    assert np.array_equal(enhanced, audio)


def test_enhance_audio_pipeline():
    """Test complete audio enhancement pipeline."""
    enhancer = AudioEnhancer(enable_metricgan=False)

    audio = np.random.randn(16000).astype(np.float32)
    enhanced = enhancer.enhance_audio_pipeline(
        audio,
        sample_rate=16000,
        apply_high_pass=True,
        high_pass_cutoff=80.0,
    )

    assert len(enhanced) == len(audio)
    assert enhanced.dtype == np.float32


def test_get_enhancement_info():
    """Test getting enhancement information."""
    enhancer = AudioEnhancer(enable_metricgan=False)

    info = enhancer.get_enhancement_info()

    assert "enhancement_enabled" in info
    assert "metricgan_available" in info
    assert "device" in info
    assert "model_source" in info
    assert info["enhancement_enabled"] is False
    assert info["metricgan_available"] is False
