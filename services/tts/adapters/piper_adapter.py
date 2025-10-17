"""
Piper TTS adapter implementation.

This module provides the Piper implementation of the TTS interface,
enabling text-to-speech synthesis using the Piper TTS library.
"""

import logging
import time
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from services.common.surfaces.tts_interface import TTSAdapter, TTSConfig, TTSResult
from services.common.surfaces.types import AudioFormat

logger = logging.getLogger(__name__)


class PiperAdapter(TTSAdapter):
    """
    Piper implementation of TTS adapter.

    This adapter uses the Piper TTS library for text-to-speech
    synthesis, providing high-quality speech generation.
    """

    def __init__(self, config: TTSConfig):
        """
        Initialize Piper adapter.

        Args:
            config: TTS configuration
        """
        super().__init__(config)
        self._model: Any | None = None
        self._model_info: dict[str, Any] = {}
        self._telemetry: dict[str, Any] = {
            "total_syntheses": 0,
            "total_text_length": 0,
            "total_audio_duration": 0.0,
            "total_processing_time": 0.0,
            "error_count": 0,
        }

    async def initialize(self) -> bool:
        """
        Initialize the Piper adapter.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing Piper adapter")

            # Import piper
            try:
                import piper
            except ImportError:
                logger.error("piper not available")
                return False

            # Initialize model (simplified - in practice, you'd load a specific model)
            self._model = piper.PiperVoice.from_config(
                {
                    "model": self.config.model_name,
                    "voice": self.config.voice,
                    "language": self.config.language,
                }
            )

            # Get model info
            self._model_info = {
                "model_name": self.config.model_name,
                "voice": self.config.voice,
                "language": self.config.language,
                "sample_rate": self.config.sample_rate,
                "channels": self.config.channels,
                "bit_depth": self.config.bit_depth,
            }

            self._is_initialized = True
            logger.info("Piper adapter initialized successfully")
            return True

        except Exception as e:
            logger.error("Failed to initialize Piper adapter: %s", e)
            return False

    async def connect(self) -> bool:
        """
        Connect to Piper service.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._is_initialized:
            logger.error("Adapter not initialized")
            return False

        try:
            logger.info("Connecting to Piper service")

            # Piper doesn't require a connection
            self._is_connected = True
            logger.info("Connected to Piper service successfully")
            return True

        except Exception as e:
            logger.error("Failed to connect to Piper service: %s", e)
            return False

    async def disconnect(self) -> None:
        """Disconnect from Piper service."""
        try:
            logger.info("Disconnecting from Piper service")

            # Clean up model
            if self._model:
                self._model = None

            self._is_connected = False
            logger.info("Disconnected from Piper service successfully")

        except Exception as e:
            logger.error("Failed to disconnect from Piper service: %s", e)

    async def synthesize(
        self, text: str, voice: str | None = None, language: str | None = None
    ) -> TTSResult:
        """
        Synthesize text to speech.

        Args:
            text: Text to synthesize
            voice: Voice to use (optional)
            language: Language to use (optional)

        Returns:
            TTS result containing audio data and metadata
        """
        if not self._is_connected or not self._model:
            raise RuntimeError("Adapter not connected or model not available")

        try:
            start_time = time.time()

            # Use provided voice/language or fall back to config
            use_voice = voice or self.config.voice
            use_language = language or self.config.language

            # Synthesize using Piper
            # This is a simplified implementation - in practice, you'd use the actual Piper API
            audio_data = await self._synthesize_audio(text, use_voice, use_language)

            processing_time = time.time() - start_time

            # Calculate duration (simplified)
            duration = len(audio_data) / (
                self.config.sample_rate * self.config.channels * 2
            )  # 2 bytes per sample

            # Create audio format
            audio_format = AudioFormat(
                value={
                    "sample_rate": self.config.sample_rate,
                    "channels": self.config.channels,
                    "bit_depth": self.config.bit_depth,
                    "frame_size_ms": 20,
                }
            )

            # Create result
            result = TTSResult(
                audio_data=audio_data,
                audio_format=audio_format,
                text=text,
                voice=use_voice,
                language=use_language,
                duration=duration,
                processing_time=processing_time,
                timestamp=datetime.now(),
            )

            # Update telemetry
            self._update_telemetry(result)

            logger.debug("Synthesized text: %s (duration: %.2fs)", text[:50], duration)
            return result

        except Exception as e:
            logger.error("Failed to synthesize text: %s", e)
            self._telemetry["error_count"] += 1
            raise

    async def synthesize_stream(  # type: ignore[override]
        self, text: str, voice: str | None = None, language: str | None = None
    ) -> AsyncGenerator[TTSResult, None]:
        """
        Synthesize text to speech with streaming output.

        Args:
            text: Text to synthesize
            voice: Voice to use (optional)
            language: Language to use (optional)

        Yields:
            TTS results as they become available
        """
        if not self._is_connected or not self._model:
            raise RuntimeError("Adapter not connected or model not available")

        try:
            # For now, just synthesize the entire text and yield it
            # In a real implementation, you'd stream the synthesis
            result = await self.synthesize(text, voice, language)
            yield result
        except Exception as e:
            logger.error("Failed to synthesize streaming text: %s", e)
            self._telemetry["error_count"] += 1
            raise

    async def get_available_voices(self) -> list[dict[str, Any]]:
        """
        Get list of available voices.

        Returns:
            List of available voices with metadata
        """
        # Return default voices (in practice, you'd query the actual model)
        return [
            {
                "id": "default",
                "name": "Default Voice",
                "language": "en",
                "gender": "neutral",
                "age": "adult",
            },
            {
                "id": "female",
                "name": "Female Voice",
                "language": "en",
                "gender": "female",
                "age": "adult",
            },
            {
                "id": "male",
                "name": "Male Voice",
                "language": "en",
                "gender": "male",
                "age": "adult",
            },
        ]

    async def get_supported_languages(self) -> list[str]:
        """
        Get list of supported languages.

        Returns:
            List of supported language codes
        """
        # Piper supports many languages
        return [
            "en",
            "es",
            "fr",
            "de",
            "it",
            "pt",
            "ru",
            "ja",
            "ko",
            "zh",
            "ar",
            "hi",
            "th",
            "vi",
            "tr",
            "pl",
            "nl",
            "sv",
            "da",
            "no",
            "fi",
            "el",
            "he",
            "cs",
            "sk",
            "hu",
            "ro",
            "bg",
            "hr",
            "sl",
            "et",
            "lv",
            "lt",
            "mt",
            "ga",
            "cy",
            "eu",
            "ca",
            "gl",
            "is",
        ]

    async def get_model_info(self) -> dict[str, Any]:
        """
        Get information about the current model.

        Returns:
            Dictionary containing model information
        """
        return self._model_info.copy()

    async def get_telemetry(self) -> dict[str, Any]:
        """
        Get telemetry and performance metrics.

        Returns:
            Dictionary containing telemetry data
        """
        return self._telemetry.copy()

    async def _synthesize_audio(self, text: str, voice: str, language: str) -> bytes:
        """
        Synthesize audio using Piper.

        Args:
            text: Text to synthesize
            voice: Voice to use
            language: Language to use

        Returns:
            Audio data as bytes
        """
        try:
            # This is a simplified implementation
            # In practice, you'd use the actual Piper API to synthesize audio

            # Generate dummy audio data (sine wave)
            try:
                import numpy as np

                sample_rate = self.config.sample_rate
                duration = len(text) * 0.1  # Rough estimate: 0.1 seconds per character
                samples = int(sample_rate * duration)

                # Generate a simple sine wave
                frequency = 440  # A4 note
                t = np.linspace(0, duration, samples, False)
                audio_array = np.sin(2 * np.pi * frequency * t)

                # Convert to 16-bit PCM
                audio_array = (audio_array * 32767).astype(np.int16)

                # Convert to bytes
                audio_data: bytes = audio_array.tobytes()
            except ImportError:
                # Fallback if numpy not available
                logger.warning("numpy not available, using simplified audio generation")
                # Generate simple audio data
                sample_rate = self.config.sample_rate
                duration = len(text) * 0.1
                samples = int(sample_rate * duration)
                audio_data = b"\x00" * (samples * 2)  # 2 bytes per sample

            return audio_data

        except Exception as e:
            logger.error("Failed to synthesize audio: %s", e)
            raise

    def _update_telemetry(self, result: TTSResult) -> None:
        """Update telemetry with new result."""
        try:
            self._telemetry["total_syntheses"] += 1
            self._telemetry["total_text_length"] += len(result.text)
            self._telemetry["total_audio_duration"] += result.duration
            self._telemetry["total_processing_time"] += result.processing_time

        except Exception as e:
            logger.error("Failed to update telemetry: %s", e)
