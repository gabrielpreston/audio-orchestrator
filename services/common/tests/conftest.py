"""Test fixtures for common service tests."""

from typing import Callable, Generator
from unittest.mock import Mock

import numpy as np
import pytest

from services.common.audio import AudioProcessor


@pytest.fixture
def generate_test_audio() -> Callable[[int, float, float], bytes]:
    """Generate test audio data."""
    def _generate_audio(sample_rate: int = 16000, duration: float = 1.0, frequency: float = 440.0) -> bytes:
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_float = np.sin(2 * np.pi * frequency * t) * 0.5
        audio_int16 = (audio_float * 32767).astype(np.int16)
        return audio_int16.tobytes()
    return _generate_audio


@pytest.fixture
def assert_audio_properties() -> Callable[[bytes, int, float], None]:
    """Assert audio properties."""
    def _assert_audio(pcm_data: bytes, sample_rate: int, duration: float):
        assert len(pcm_data) > 0
        assert len(pcm_data) == sample_rate * duration * 2  # 2 bytes per int16 sample
        assert isinstance(pcm_data, bytes)
    return _assert_audio


@pytest.fixture
def capture_structured_logs() -> Generator[Mock, None, None]:
    """Capture structured logs for testing."""
    # This would be implemented with a log capture mechanism
    # For now, return a mock
    yield Mock()


@pytest.fixture
def sample_pcm_audio() -> bytes:
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
def silence_audio() -> bytes:
    """Generate silence audio data."""
    # Generate 0.1 seconds of silence
    sample_rate = 16000
    duration = 0.1
    samples = int(sample_rate * duration)
    return b'\x00' * (samples * 2)  # 2 bytes per int16 sample


@pytest.fixture
def loud_audio() -> bytes:
    """Generate loud audio data."""
    # Generate 0.1 seconds of loud sine wave
    sample_rate = 16000
    duration = 0.1
    frequency = 440
    
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio_float = np.sin(2 * np.pi * frequency * t) * 0.9  # 90% amplitude
    audio_int16 = (audio_float * 32767).astype(np.int16)
    return audio_int16.tobytes()


@pytest.fixture
def audio_processor():
    """Create audio processor for testing."""
    processor = AudioProcessor("test")
    processor.set_logger(Mock())
    return processor


@pytest.fixture
def mock_logger():
    """Create mock logger for testing."""
    return Mock()


@pytest.fixture
def test_audio_data():
    """Generate various test audio data."""
    return {
        'silence': b'\x00' * 3200,  # 0.1 seconds of silence
        'sine_440': np.sin(2 * np.pi * 440 * np.linspace(0, 1, 16000, False)).astype(np.int16).tobytes(),
        'sine_880': np.sin(2 * np.pi * 880 * np.linspace(0, 1, 16000, False)).astype(np.int16).tobytes(),
        'noise': np.random.randint(-1000, 1000, 16000, dtype=np.int16).tobytes(),
    }


@pytest.fixture
def audio_validation_helpers():
    """Audio validation helper functions."""
    def validate_pcm_format(pcm_data: bytes, sample_rate: int, duration: float):
        """Validate PCM data format."""
        expected_bytes = int(sample_rate * duration * 2)  # 2 bytes per int16 sample
        assert len(pcm_data) == expected_bytes, f"Expected {expected_bytes} bytes, got {len(pcm_data)}"
        assert len(pcm_data) % 2 == 0, "PCM data should be even number of bytes"
        
    def validate_rms_range(rms: float, min_rms: float = 0.0, max_rms: float = 32768.0):
        """Validate RMS value is in expected range."""
        assert min_rms <= rms <= max_rms, f"RMS {rms} not in range [{min_rms}, {max_rms}]"
        
    def validate_audio_array(audio_array: np.ndarray, dtype: np.dtype = np.dtype(np.int16)):
        """Validate audio array properties."""
        assert audio_array.dtype == dtype, f"Expected dtype {dtype}, got {audio_array.dtype}"
        assert len(audio_array) > 0, "Audio array should not be empty"
        
    return {
        'validate_pcm_format': validate_pcm_format,
        'validate_rms_range': validate_rms_range,
        'validate_audio_array': validate_audio_array,
    }