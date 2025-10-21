"""Audio quality validation helpers for testing."""

import io
import wave
from typing import Any

import numpy as np


def calculate_snr(audio_data: bytes, noise_floor: float = 0.01) -> float:
    """
    Calculate Signal-to-Noise Ratio (SNR) of audio data.

    Args:
        audio_data: Raw PCM audio data
        noise_floor: Minimum noise floor level

    Returns:
        SNR in decibels
    """
    try:
        # Convert to numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        if len(audio_array) == 0:
            return 0.0

        # Convert to float and normalize
        audio_float = audio_array.astype(np.float32) / 32768.0

        # Calculate signal power
        signal_power = np.mean(audio_float**2)

        # Estimate noise power (using minimum values as noise floor)
        noise_power = max(noise_floor, float(np.var(audio_float[audio_float < noise_floor])))

        if noise_power == 0:
            return float("inf")

        # Calculate SNR in dB
        snr_db = 10 * np.log10(signal_power / noise_power)
        return float(snr_db)

    except Exception:
        return 0.0


def calculate_thd(
    audio_data: bytes, fundamental_freq: float = 440.0, sample_rate: int = 16000
) -> float:
    """
    Calculate Total Harmonic Distortion (THD) of audio data.

    Args:
        audio_data: Raw PCM audio data
        fundamental_freq: Fundamental frequency in Hz
        sample_rate: Sample rate in Hz

    Returns:
        THD as percentage
    """
    try:
        # Convert to numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        if len(audio_array) == 0:
            return 0.0

        # Convert to float and normalize
        audio_float = audio_array.astype(np.float32) / 32768.0

        # Apply FFT
        fft = np.fft.fft(audio_float)
        _freqs = np.fft.fftfreq(len(audio_float), 1 / sample_rate)

        # Find fundamental frequency bin
        fundamental_bin = int(fundamental_freq * len(audio_float) / sample_rate)
        if fundamental_bin >= len(fft):
            return 0.0

        # Calculate harmonic components
        fundamental_magnitude = abs(fft[fundamental_bin])
        harmonic_magnitudes = []

        # Check harmonics (2nd, 3rd, 4th, 5th)
        for harmonic in range(2, 6):
            harmonic_bin = fundamental_bin * harmonic
            if harmonic_bin < len(fft):
                harmonic_magnitudes.append(abs(fft[harmonic_bin]))

        if not harmonic_magnitudes or fundamental_magnitude == 0:
            return 0.0

        # Calculate THD
        total_harmonic_power = sum(mag**2 for mag in harmonic_magnitudes)
        fundamental_power = fundamental_magnitude**2

        thd = np.sqrt(total_harmonic_power / fundamental_power) * 100
        return float(thd)

    except Exception:
        return 0.0


def measure_frequency_response(audio_data: bytes, sample_rate: int = 16000) -> dict[str, Any]:
    """
    Measure frequency response of audio data.

    Args:
        audio_data: Raw PCM audio data
        sample_rate: Sample rate in Hz

    Returns:
        Dictionary with frequency response metrics
    """
    try:
        # Convert to numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        if len(audio_array) == 0:
            return {"error": "Empty audio data"}

        # Convert to float and normalize
        audio_float = audio_array.astype(np.float32) / 32768.0

        # Apply FFT
        fft = np.fft.fft(audio_float)
        _freqs = np.fft.fftfreq(len(audio_float), 1 / sample_rate)

        # Get magnitude spectrum
        magnitude = np.abs(fft)

        # Find peak frequency
        peak_idx = np.argmax(magnitude[: len(magnitude) // 2])
        peak_freq = _freqs[peak_idx]

        # Calculate frequency response metrics
        # Human voice range: 300Hz - 3400Hz
        voice_range_mask = (_freqs >= 300) & (_freqs <= 3400)
        voice_range_power: float = float(np.sum(magnitude[voice_range_mask] ** 2))
        total_power: float = float(np.sum(magnitude**2))
        voice_ratio = voice_range_power / total_power if total_power > 0 else 0

        # Check for aliasing (frequencies above Nyquist/2)
        nyquist = sample_rate / 2
        aliasing_mask = _freqs > nyquist
        aliasing_power: float = float(np.sum(magnitude[aliasing_mask] ** 2))
        aliasing_ratio = aliasing_power / total_power if total_power > 0 else 0

        return {
            "peak_frequency": float(peak_freq),
            "voice_range_ratio": float(voice_ratio),
            "aliasing_ratio": float(aliasing_ratio),
            "total_power": float(total_power),
            "sample_rate": sample_rate,
        }

    except Exception as e:
        return {"error": str(e)}


def validate_audio_fidelity(
    original: bytes, processed: bytes, tolerance: float = 0.1
) -> dict[str, Any]:
    """
    Validate audio fidelity between original and processed audio.

    Args:
        original: Original audio data
        processed: Processed audio data
        tolerance: Acceptable difference tolerance (0.0 to 1.0)

    Returns:
        Dictionary with fidelity validation results
    """
    try:
        # Convert to numpy arrays
        orig_array = np.frombuffer(original, dtype=np.int16)
        proc_array = np.frombuffer(processed, dtype=np.int16)

        if len(orig_array) == 0 or len(proc_array) == 0:
            return {"error": "Empty audio data", "fidelity_score": 0.0}

        # Normalize lengths (pad shorter array with zeros)
        max_len = max(len(orig_array), len(proc_array))
        if len(orig_array) < max_len:
            orig_array = np.pad(orig_array, (0, max_len - len(orig_array)))
        if len(proc_array) < max_len:
            proc_array = np.pad(proc_array, (0, max_len - len(proc_array)))

        # Calculate correlation coefficient
        correlation = np.corrcoef(orig_array, proc_array)[0, 1]
        if np.isnan(correlation):
            correlation = 0.0

        # Calculate mean squared error
        mse = np.mean((orig_array.astype(np.float32) - proc_array.astype(np.float32)) ** 2)

        # Calculate signal-to-noise ratio between original and processed
        signal_power = np.mean(orig_array.astype(np.float32) ** 2)
        noise_power = mse
        snr = 10 * np.log10(signal_power / noise_power) if noise_power > 0 else float("inf")

        # Calculate fidelity score (0.0 to 1.0)
        fidelity_score = max(0.0, min(1.0, correlation * (1.0 - mse / (32768.0**2))))

        # Check if within tolerance
        within_tolerance = fidelity_score >= (1.0 - tolerance)

        return {
            "fidelity_score": float(fidelity_score),
            "correlation": float(correlation),
            "mse": float(mse),
            "snr_db": float(snr),
            "within_tolerance": within_tolerance,
            "tolerance": tolerance,
        }

    except Exception as e:
        return {"error": str(e), "fidelity_score": 0.0}


def validate_wav_format(audio_data: bytes) -> dict[str, Any]:
    """
    Validate WAV format and extract metadata.

    Args:
        audio_data: WAV audio data

    Returns:
        Dictionary with WAV validation results
    """
    try:
        with wave.open(io.BytesIO(audio_data), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frames = wav_file.getnframes()
            duration = frames / sample_rate

            # Validate format
            is_valid = (
                channels in [1, 2]  # Mono or stereo
                and sample_width in [1, 2, 4]  # 8, 16, or 32 bit
                and sample_rate > 0
                and frames > 0
            )

            return {
                "is_valid": is_valid,
                "channels": channels,
                "sample_width": sample_width,
                "sample_rate": sample_rate,
                "frames": frames,
                "duration": duration,
                "bit_depth": sample_width * 8,
            }

    except Exception as e:
        return {"is_valid": False, "error": str(e)}


def generate_test_audio(
    duration: float = 1.0,
    sample_rate: int = 16000,
    frequency: float = 440.0,
    amplitude: float = 0.5,
    noise_level: float = 0.0,
) -> bytes:
    """
    Generate synthetic test audio for quality testing.

    Args:
        duration: Duration in seconds
        sample_rate: Sample rate in Hz
        frequency: Frequency in Hz
        amplitude: Amplitude (0.0 to 1.0)
        noise_level: Noise level (0.0 to 1.0)

    Returns:
        PCM audio data as bytes
    """
    try:
        # Generate time array
        t = np.linspace(0, duration, int(sample_rate * duration), False)

        # Generate sine wave
        signal = amplitude * np.sin(2 * np.pi * frequency * t)

        # Add noise if specified
        if noise_level > 0:
            noise = noise_level * np.random.randn(len(t))
            signal += noise

        # Convert to 16-bit PCM
        audio_int16 = (signal * 32767).astype(np.int16)

        return audio_int16.tobytes()

    except Exception:
        # Return silence on error
        return b"\x00" * int(sample_rate * duration * 2)


def create_wav_file(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """
    Create WAV file from PCM data.

    Args:
        pcm_data: Raw PCM audio data
        sample_rate: Sample rate in Hz
        channels: Number of channels

    Returns:
        WAV file data as bytes
    """
    try:
        buffer = io.BytesIO()

        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)

        return buffer.getvalue()

    except Exception:
        # Return minimal WAV on error
        return b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
