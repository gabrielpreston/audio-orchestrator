"""Audio test fixtures for synthetic noisy samples.
# Trigger CI lint check
"""

from dataclasses import dataclass
import io
import wave

import numpy as np


@dataclass
class AudioSample:
    """Audio sample with metadata."""

    data: bytes
    sample_rate: int
    channels: int
    duration_seconds: float
    noise_type: str
    snr_db: float
    description: str


class AudioSampleGenerator:
    """Generate synthetic audio samples for testing."""

    def __init__(self, sample_rate: int = 16000, duration_seconds: float = 3.0):
        self.sample_rate = sample_rate
        self.duration_seconds = duration_seconds
        self.samples = int(sample_rate * duration_seconds)

    def generate_clean_speech(self) -> AudioSample:
        """Generate clean speech baseline (sine wave with speech-like envelope)."""
        # Create speech-like envelope
        t = np.linspace(0, self.duration_seconds, self.samples)
        envelope = np.exp(-t * 0.5) * (1 + 0.3 * np.sin(2 * np.pi * 0.5 * t))

        # Generate speech-like frequencies
        speech_freqs = [200, 400, 800, 1200, 1600]  # Formant-like frequencies
        signal = np.zeros(self.samples)
        for freq in speech_freqs:
            signal += 0.2 * np.sin(2 * np.pi * freq * t)

        # Apply envelope
        signal *= envelope

        # Normalize and convert to int16
        signal = np.clip(signal, -1, 1)
        audio_data: np.ndarray = (signal * 32767).astype(np.int16)

        return AudioSample(
            data=self._to_wav_bytes(audio_data),
            sample_rate=self.sample_rate,
            channels=1,
            duration_seconds=self.duration_seconds,
            noise_type="clean",
            snr_db=float("inf"),
            description="Clean speech baseline",
        )

    def add_white_noise(self, clean_signal: np.ndarray, snr_db: float) -> np.ndarray:
        """Add white noise to signal at specified SNR."""
        signal_power = np.mean(clean_signal**2)
        noise_power = signal_power / (10 ** (snr_db / 10))
        noise = np.random.normal(0, np.sqrt(noise_power), len(clean_signal))
        return clean_signal + noise

    def add_background_music(
        self, clean_signal: np.ndarray, snr_db: float
    ) -> np.ndarray:
        """Add background music/chatter simulation."""
        # Generate music-like signal (multiple sine waves)
        t = np.linspace(0, self.duration_seconds, len(clean_signal))
        music_freqs = [100, 150, 200, 250, 300, 350, 400]
        music_signal = np.zeros(len(clean_signal))
        for freq in music_freqs:
            music_signal += 0.1 * np.sin(2 * np.pi * freq * t)

        # Add some modulation
        music_signal *= 1 + 0.3 * np.sin(2 * np.pi * 0.1 * t)

        # Scale to desired SNR
        signal_power = np.mean(clean_signal**2)
        music_power = np.mean(music_signal**2)
        target_noise_power = signal_power / (10 ** (snr_db / 10))
        music_signal *= np.sqrt(target_noise_power / music_power)

        return clean_signal + music_signal

    def add_echo_reverb(
        self, clean_signal: np.ndarray, delay_ms: float = 100, decay: float = 0.3
    ) -> np.ndarray:
        """Add echo/reverb effect."""
        delay_samples = int(delay_ms * self.sample_rate / 1000)
        echo_signal = np.zeros_like(clean_signal)

        # Add delayed and attenuated version
        if delay_samples < len(clean_signal):
            echo_signal[delay_samples:] = clean_signal[:-delay_samples] * decay

        return clean_signal + echo_signal

    def generate_noisy_samples(self) -> list[AudioSample]:
        """Generate comprehensive set of test samples."""
        samples = []

        # Clean baseline
        clean_sample = self.generate_clean_speech()
        samples.append(clean_sample)

        # Extract clean signal for noise addition
        clean_signal = self._extract_audio_signal(clean_sample.data)

        # White noise variants
        for snr_db in [30, 20, 10]:
            noisy_signal = self.add_white_noise(clean_signal, snr_db)
            noisy_data = self._to_wav_bytes(noisy_signal)
            samples.append(
                AudioSample(
                    data=noisy_data,
                    sample_rate=self.sample_rate,
                    channels=1,
                    duration_seconds=self.duration_seconds,
                    noise_type="white_noise",
                    snr_db=snr_db,
                    description=f"White noise at {snr_db}dB SNR",
                )
            )

        # Background music variants
        for snr_db in [20, 10, 5]:
            music_signal = self.add_background_music(clean_signal, snr_db)
            music_data = self._to_wav_bytes(music_signal)
            samples.append(
                AudioSample(
                    data=music_data,
                    sample_rate=self.sample_rate,
                    channels=1,
                    duration_seconds=self.duration_seconds,
                    noise_type="background_music",
                    snr_db=snr_db,
                    description=f"Background music at {snr_db}dB SNR",
                )
            )

        # Echo/reverb variants
        echo_signal = self.add_echo_reverb(clean_signal, delay_ms=100, decay=0.3)
        echo_data = self._to_wav_bytes(echo_signal)
        samples.append(
            AudioSample(
                data=echo_data,
                sample_rate=self.sample_rate,
                channels=1,
                duration_seconds=self.duration_seconds,
                noise_type="echo",
                snr_db=float("inf"),  # Not applicable for echo
                description="Echo/reverb effect",
            )
        )

        return samples

    def _extract_audio_signal(self, wav_bytes: bytes) -> np.ndarray:
        """Extract audio signal from WAV bytes."""
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
            return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0

    def _to_wav_bytes(self, signal: np.ndarray) -> bytes:
        """Convert audio signal to WAV bytes."""
        # Convert to int16
        audio_int16 = (np.clip(signal, -1, 1) * 32767).astype(np.int16)

        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

        return wav_buffer.getvalue()


# Convenience function for tests
def get_test_audio_samples() -> list[AudioSample]:
    """Get standard set of test audio samples."""
    generator = AudioSampleGenerator()
    return generator.generate_noisy_samples()


# Specific sample getters for different test scenarios
def get_clean_sample() -> AudioSample:
    """Get clean speech sample."""
    generator = AudioSampleGenerator()
    return generator.generate_clean_speech()


def get_noisy_samples(snr_db: float = 20) -> AudioSample:
    """Get noisy sample at specific SNR."""
    generator = AudioSampleGenerator()
    clean_sample = generator.generate_clean_speech()
    clean_signal = generator._extract_audio_signal(clean_sample.data)
    noisy_signal = generator.add_white_noise(clean_signal, snr_db)
    noisy_data = generator._to_wav_bytes(noisy_signal)

    return AudioSample(
        data=noisy_data,
        sample_rate=generator.sample_rate,
        channels=1,
        duration_seconds=generator.duration_seconds,
        noise_type="white_noise",
        snr_db=snr_db,
        description=f"White noise at {snr_db}dB SNR",
    )
