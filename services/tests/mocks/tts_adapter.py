"""Mock TTS adapter for testing."""

from typing import Any

from services.tests.utils.audio_quality_helpers import (
    create_wav_file,
    generate_test_audio,
)


class MockTTSAdapter:
    """Mock TTS adapter that generates synthetic audio for testing."""

    def __init__(
        self,
        sample_rate: int = 22050,
        default_frequency: float = 440.0,
        default_amplitude: float = 0.5,
        default_noise_level: float = 0.0,
    ):
        """
        Initialize mock TTS adapter.

        Args:
            sample_rate: Audio sample rate
            default_frequency: Default frequency for generated audio
            default_amplitude: Default amplitude for generated audio
            default_noise_level: Default noise level for generated audio
        """
        self.sample_rate = sample_rate
        self.default_frequency = default_frequency
        self.default_amplitude = default_amplitude
        self.default_noise_level = default_noise_level

    def synthesize(
        self,
        text: str,
        voice: str | None = None,  # noqa: ARG002
        **kwargs: Any,
    ) -> bytes:
        """
        Generate synthetic audio based on text.

        Args:
            text: Text to synthesize
            voice: Voice to use (ignored in mock)
            **kwargs: Additional parameters

        Returns:
            WAV audio data
        """
        # Calculate duration based on text length (0.1s per character)
        duration = max(0.1, len(text) * 0.1)

        # Extract parameters from kwargs or use defaults
        frequency = kwargs.get("frequency", self.default_frequency)
        amplitude = kwargs.get("amplitude", self.default_amplitude)
        noise_level = kwargs.get("noise_level", self.default_noise_level)

        # Generate synthetic audio
        pcm_data = generate_test_audio(
            duration=duration,
            sample_rate=self.sample_rate,
            frequency=frequency,
            amplitude=amplitude,
            noise_level=noise_level,
        )

        # Create WAV file
        wav_data = create_wav_file(pcm_data, self.sample_rate, channels=1)

        return wav_data

    def get_available_voices(self) -> list[str]:
        """Get list of available voices."""
        return ["default", "male", "female", "child"]

    def get_voice_info(self, voice: str) -> dict[str, Any]:
        """Get voice information."""
        return {
            "name": voice,
            "language": "en-US",
            "gender": "neutral",
            "sample_rate": self.sample_rate,
        }
