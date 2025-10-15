"""Mock audio processor for testing."""

import io
from typing import Any, Dict, List, Optional, Tuple, Union
from unittest import mock

import numpy as np
import soundfile as sf


class MockAudioProcessor:
    """Mock audio processor for testing."""

    def __init__(self):
        self._mock_audio_data = {}
        self._mock_metadata = {}
        self._load_calls = []
        self._write_calls = []

    def set_mock_audio_data(
        self, file_path: str, audio_data: np.ndarray, sample_rate: int = 48000
    ) -> None:
        """Set mock audio data for a file path.

        Args:
            file_path: File path to mock
            audio_data: Audio data to return
            sample_rate: Sample rate
        """
        self._mock_audio_data[file_path] = (audio_data, sample_rate)

    def set_mock_metadata(self, file_path: str, metadata: Dict[str, Any]) -> None:
        """Set mock metadata for a file path.

        Args:
            file_path: File path to mock
            metadata: Metadata to return
        """
        self._mock_metadata[file_path] = metadata

    def get_load_calls(self) -> List[Dict[str, Any]]:
        """Get all load calls."""
        return self._load_calls.copy()

    def get_write_calls(self) -> List[Dict[str, Any]]:
        """Get all write calls."""
        return self._write_calls.copy()

    def clear_calls(self) -> None:
        """Clear all recorded calls."""
        self._load_calls.clear()
        self._write_calls.clear()

    def load(
        self, file_path: str, sr: Optional[int] = None, mono: bool = True, **kwargs
    ) -> Tuple[np.ndarray, int]:
        """Mock load method."""
        call_data = {"file_path": file_path, "sr": sr, "mono": mono, "kwargs": kwargs}
        self._load_calls.append(call_data)

        if file_path in self._mock_audio_data:
            audio_data, sample_rate = self._mock_audio_data[file_path]
            if sr is not None and sr != sample_rate:
                # Simulate resampling
                audio_data = self._resample(audio_data, sample_rate, sr)
                sample_rate = sr
            return audio_data, sample_rate

        # Default mock data
        duration = 1.0
        sample_rate = sr or 48000
        audio_data = np.random.randn(int(duration * sample_rate)).astype(np.float32)
        return audio_data, sample_rate

    def write(
        self,
        file_path: str,
        data: np.ndarray,
        samplerate: int,
        format: str = "WAV",
        subtype: str = "PCM_16",
        **kwargs,
    ) -> None:
        """Mock write method."""
        call_data = {
            "file_path": file_path,
            "data_shape": data.shape,
            "samplerate": samplerate,
            "format": format,
            "subtype": subtype,
            "kwargs": kwargs,
        }
        self._write_calls.append(call_data)

    def info(self, file_path: str) -> Dict[str, Any]:
        """Mock info method."""
        if file_path in self._mock_metadata:
            return self._mock_metadata[file_path]

        # Default mock info
        return {
            "samplerate": 48000,
            "frames": 48000,
            "channels": 1,
            "format": "WAV",
            "subtype": "PCM_16",
            "duration": 1.0,
        }

    def _resample(self, audio_data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Mock resampling."""
        if orig_sr == target_sr:
            return audio_data

        # Simple linear interpolation resampling
        ratio = target_sr / orig_sr
        new_length = int(len(audio_data) * ratio)
        indices = np.linspace(0, len(audio_data) - 1, new_length)
        return np.interp(indices, np.arange(len(audio_data)), audio_data)


class MockLibrosa:
    """Mock librosa for testing."""

    def __init__(self):
        self._mock_audio_data = {}
        self._load_calls = []
        self._stft_calls = []
        self._istft_calls = []

    def set_mock_audio_data(
        self, file_path: str, audio_data: np.ndarray, sample_rate: int = 48000
    ) -> None:
        """Set mock audio data for a file path."""
        self._mock_audio_data[file_path] = (audio_data, sample_rate)

    def load(
        self,
        path: str,
        sr: Optional[int] = None,
        mono: bool = True,
        offset: float = 0.0,
        duration: Optional[float] = None,
        dtype: np.dtype = np.float32,
        res_type: str = "kaiser_best",
        **kwargs,
    ) -> Tuple[np.ndarray, int]:
        """Mock load method."""
        call_data = {
            "path": path,
            "sr": sr,
            "mono": mono,
            "offset": offset,
            "duration": duration,
            "dtype": dtype,
            "res_type": res_type,
            "kwargs": kwargs,
        }
        self._load_calls.append(call_data)

        if path in self._mock_audio_data:
            audio_data, sample_rate = self._mock_audio_data[path]
            if sr is not None and sr != sample_rate:
                # Simulate resampling
                audio_data = self._resample(audio_data, sample_rate, sr)
                sample_rate = sr
            return audio_data, sample_rate

        # Default mock data
        duration = duration or 1.0
        sample_rate = sr or 48000
        audio_data = np.random.randn(int(duration * sample_rate)).astype(dtype)
        return audio_data, sample_rate

    def stft(
        self,
        y: np.ndarray,
        n_fft: int = 2048,
        hop_length: Optional[int] = None,
        win_length: Optional[int] = None,
        window: str = "hann",
        center: bool = True,
        pad_mode: str = "constant",
        **kwargs,
    ) -> np.ndarray:
        """Mock STFT method."""
        call_data = {
            "y_shape": y.shape,
            "n_fft": n_fft,
            "hop_length": hop_length,
            "win_length": win_length,
            "window": window,
            "center": center,
            "pad_mode": pad_mode,
            "kwargs": kwargs,
        }
        self._stft_calls.append(call_data)

        # Return mock STFT data
        n_frames = len(y) // (hop_length or n_fft // 4)
        return np.random.randn(n_fft // 2 + 1, n_frames).astype(np.complex64)

    def istft(
        self,
        stft_matrix: np.ndarray,
        hop_length: Optional[int] = None,
        win_length: Optional[int] = None,
        window: str = "hann",
        center: bool = True,
        length: Optional[int] = None,
        **kwargs,
    ) -> np.ndarray:
        """Mock ISTFT method."""
        call_data = {
            "stft_matrix_shape": stft_matrix.shape,
            "hop_length": hop_length,
            "win_length": win_length,
            "window": window,
            "center": center,
            "length": length,
            "kwargs": kwargs,
        }
        self._istft_calls.append(call_data)

        # Return mock reconstructed audio
        n_frames = stft_matrix.shape[1]
        hop_length = hop_length or 512
        return np.random.randn(n_frames * hop_length).astype(np.float32)

    def _resample(self, audio_data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Mock resampling."""
        if orig_sr == target_sr:
            return audio_data

        ratio = target_sr / orig_sr
        new_length = int(len(audio_data) * ratio)
        indices = np.linspace(0, len(audio_data) - 1, new_length)
        return np.interp(indices, np.arange(len(audio_data)), audio_data)


def create_mock_audio_processor() -> MockAudioProcessor:
    """Create a mock audio processor for testing.

    Returns:
        Mock audio processor
    """
    return MockAudioProcessor()


def create_mock_librosa() -> MockLibrosa:
    """Create a mock librosa for testing.

    Returns:
        Mock librosa
    """
    return MockLibrosa()


def create_mock_audio_data(
    duration: float = 1.0, sample_rate: int = 48000, channels: int = 1, dtype: np.dtype = np.float32
) -> np.ndarray:
    """Create mock audio data for testing.

    Args:
        duration: Duration in seconds
        sample_rate: Sample rate in Hz
        channels: Number of channels
        dtype: Data type

    Returns:
        Mock audio data
    """
    samples = int(duration * sample_rate * channels)
    return np.random.randn(samples).astype(dtype)


def create_mock_wav_file(
    file_path: str, duration: float = 1.0, sample_rate: int = 48000, channels: int = 1
) -> str:
    """Create a mock WAV file for testing.

    Args:
        file_path: Path to create the file
        duration: Duration in seconds
        sample_rate: Sample rate in Hz
        channels: Number of channels

    Returns:
        Path to the created file
    """
    audio_data = create_mock_audio_data(duration, sample_rate, channels, np.int16)

    with sf.SoundFile(file_path, "w", samplerate=sample_rate, channels=channels) as f:
        f.write(audio_data)

    return file_path


def create_mock_audio_metadata(
    sample_rate: int = 48000,
    frames: int = 48000,
    channels: int = 1,
    format: str = "WAV",
    subtype: str = "PCM_16",
) -> Dict[str, Any]:
    """Create mock audio metadata for testing.

    Args:
        sample_rate: Sample rate in Hz
        frames: Number of frames
        channels: Number of channels
        format: Audio format
        subtype: Audio subtype

    Returns:
        Mock audio metadata
    """
    return {
        "samplerate": sample_rate,
        "frames": frames,
        "channels": channels,
        "format": format,
        "subtype": subtype,
        "duration": frames / sample_rate,
    }
