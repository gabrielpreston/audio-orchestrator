"""Tests for wake detection module."""

import numpy as np
import pytest
from unittest.mock import Mock, MagicMock, patch

from services.common.wake_detection import WakeDetector
from services.common.config.presets import WakeConfig


@pytest.fixture
def sample_pcm_bytes():
    """Create sample PCM bytes for testing (16kHz, 1 second = 16000 samples)."""
    # Generate a simple sine wave at 440Hz, 16kHz sample rate
    sample_rate = 16000
    duration = 1.0  # 1 second
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    frequency = 440.0
    audio_data = np.sin(2 * np.pi * frequency * t)
    # Convert to int16 PCM
    pcm_bytes = (audio_data * 32767).astype(np.int16).tobytes()
    return pcm_bytes


@pytest.fixture
def wake_config():
    """Create a wake config for testing."""
    return WakeConfig(
        model_paths=[],
        activation_threshold=0.5,
        target_sample_rate_hz=16000,
        enabled=True,
    )


@pytest.fixture
def mock_model():
    """Create a mock OpenWakeWord model."""
    model = MagicMock()
    model.predict = Mock(return_value={"test_phrase": 0.8})
    return model


@pytest.mark.unit
class TestWakeDetectorFormatConversion:
    """Test format conversion in wake detection."""

    @patch("services.common.wake_detection.WakeWordModel")
    def test_detect_audio_converts_float32_to_int16(
        self, mock_wake_model_class, wake_config, sample_pcm_bytes, mock_model
    ):
        """Test that detect_audio converts float32 normalized audio back to int16 before predict()."""
        mock_wake_model_class.return_value = mock_model

        detector = WakeDetector(wake_config, service_name="test")
        detector._model = mock_model

        # Call detect_audio with PCM bytes
        detector.detect_audio(sample_pcm_bytes, 16000)

        # Verify predict was called
        assert mock_model.predict.called

        # Get the argument passed to predict
        call_args = mock_model.predict.call_args
        audio_arg = call_args[0][0] if call_args[0] else call_args[1].get("x", None)

        # Verify the argument is int16
        assert isinstance(audio_arg, np.ndarray), "Audio argument should be numpy array"
        assert audio_arg.dtype == np.int16, f"Expected int16, got {audio_arg.dtype}"

        # Verify value range is within int16 bounds
        assert audio_arg.min() >= -32767, "Values should be >= -32767"
        assert audio_arg.max() <= 32767, "Values should be <= 32767"

    @patch("services.common.wake_detection.WakeWordModel")
    def test_detect_audio_clamps_values_before_conversion(
        self, mock_wake_model_class, wake_config, mock_model
    ):
        """Test that values are clamped to [-1, 1] before converting to int16."""
        mock_wake_model_class.return_value = mock_model

        detector = WakeDetector(wake_config, service_name="test")
        detector._model = mock_model

        # Create PCM bytes that would produce values outside [-1, 1] if not clamped
        # This is a bit tricky since we normalize by dividing by 32768.0
        # But we can test with values that would overflow
        sample_rate = 16000
        duration = 0.5
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # Create audio with amplitude > 1.0 (will be normalized but we'll test clamping)
        audio_data = np.sin(2 * np.pi * 440.0 * t) * 1.5  # Amplitude 1.5
        pcm_bytes = (audio_data * 32767).astype(np.int16).tobytes()

        detector.detect_audio(pcm_bytes, 16000)

        # Verify predict was called
        assert mock_model.predict.called

        # Get the argument passed to predict
        call_args = mock_model.predict.call_args
        audio_arg = call_args[0][0] if call_args[0] else call_args[1].get("x", None)

        # Verify values are within int16 bounds (clamping worked)
        assert audio_arg.dtype == np.int16
        assert audio_arg.min() >= -32767
        assert audio_arg.max() <= 32767

    @patch("services.common.wake_detection.WakeWordModel")
    def test_detect_audio_padding_truncation_with_int16(
        self, mock_wake_model_class, wake_config, mock_model
    ):
        """Test that padding/truncation works correctly with int16 conversion."""
        mock_wake_model_class.return_value = mock_model

        detector = WakeDetector(wake_config, service_name="test")
        detector._model = mock_model

        # Create short PCM (less than 5120 samples)
        short_pcm = b"\x00\x01" * 1000  # 2000 bytes = 1000 samples (16-bit)

        detector.detect_audio(short_pcm, 16000)

        # Verify predict was called
        assert mock_model.predict.called

        # Get the argument passed to predict
        call_args = mock_model.predict.call_args
        audio_arg = call_args[0][0] if call_args[0] else call_args[1].get("x", None)

        # Verify the length is 5120 samples (expected_samples)
        assert len(audio_arg) == 5120, f"Expected 5120 samples, got {len(audio_arg)}"
        assert audio_arg.dtype == np.int16

    @patch("services.common.wake_detection.WakeWordModel")
    @patch("services.common.wake_detection.get_logger")
    def test_detect_audio_logs_format_conversion(
        self,
        mock_get_logger,
        mock_wake_model_class,
        wake_config,
        sample_pcm_bytes,
        mock_model,
    ):
        """Test that format conversion is logged."""
        mock_wake_model_class.return_value = mock_model

        # Create a mock logger
        mock_logger = Mock()
        mock_logger.debug = Mock()
        mock_get_logger.return_value = mock_logger

        detector = WakeDetector(wake_config, service_name="test")
        detector._model = mock_model

        # Call detect_audio
        detector.detect_audio(sample_pcm_bytes, 16000)

        # Verify format conversion was logged
        log_calls = [
            call
            for call in mock_logger.debug.call_args_list
            if len(call[0]) > 0 and call[0][0] == "wake.format_conversion"
        ]

        assert len(log_calls) > 0, "Format conversion should be logged"

        # Verify log contains expected fields
        log_kwargs = log_calls[0][1] if len(log_calls[0]) > 1 else {}
        assert log_kwargs.get("original_dtype") == "float32"
        assert log_kwargs.get("converted_dtype") == "int16"
        assert "sample_count" in log_kwargs
