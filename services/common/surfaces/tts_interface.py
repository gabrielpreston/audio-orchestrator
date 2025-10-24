"""
Text-to-Speech (TTS) adapter interface.

This module defines protocol-based interfaces for TTS adapters, allowing different
TTS services to be used interchangeably in the voice pipeline.
"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .types import AudioFormat


logger = logging.getLogger(__name__)


@dataclass
class TTSConfig:
    """Configuration for TTS adapter."""

    # Model configuration
    model_name: str = "piper"
    voice: str = "default"
    language: str = "en"

    # Audio configuration
    sample_rate: int = 22050
    channels: int = 1
    bit_depth: int = 16

    # Quality configuration
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0

    # Processing configuration
    enable_ssml: bool = False
    enable_emotion: bool = False
    enable_pronunciation: bool = False

    # Performance configuration
    batch_size: int = 1
    max_text_length: int = 1000
    chunk_size: int = 1024

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_name": self.model_name,
            "voice": self.voice,
            "language": self.language,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bit_depth": self.bit_depth,
            "speed": self.speed,
            "pitch": self.pitch,
            "volume": self.volume,
            "enable_ssml": self.enable_ssml,
            "enable_emotion": self.enable_emotion,
            "enable_pronunciation": self.enable_pronunciation,
            "batch_size": self.batch_size,
            "max_text_length": self.max_text_length,
            "chunk_size": self.chunk_size,
        }


@dataclass
class TTSResult:
    """Result from TTS processing."""

    # Audio data
    audio_data: bytes
    audio_format: AudioFormat

    # Metadata
    text: str
    voice: str
    language: str

    # Timing information
    duration: float
    processing_time: float
    timestamp: datetime

    # Optional fields
    phonemes: list[str] | None = None
    word_timestamps: list[dict[str, Any]] | None = None
    emotion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "audio_data": self.audio_data,
            "audio_format": self.audio_format.value,
            "text": self.text,
            "voice": self.voice,
            "language": self.language,
            "duration": self.duration,
            "processing_time": self.processing_time,
            "timestamp": self.timestamp.isoformat(),
            "phonemes": self.phonemes,
            "word_timestamps": self.word_timestamps,
            "emotion": self.emotion,
        }


class DefaultTTSAdapter:
    """Default implementation of TTS adapter protocols.

    This provides a concrete implementation that can be used as a base
    for TTS adapter implementations or as a standalone adapter.
    """

    def __init__(self, config: TTSConfig):
        """
        Initialize TTS adapter.

        Args:
            config: TTS configuration
        """
        self.config = config
        self._is_initialized = False
        self._is_connected = False

    async def initialize(self) -> bool:
        """
        Initialize the TTS adapter.

        Default implementation sets initialized flag.
        Override this method in subclasses for specific behavior.

        Returns:
            True if initialization successful, False otherwise
        """
        self._is_initialized = True
        logger.info("TTS adapter initialized", extra={"model": self.config.model_name})
        return True

    async def connect(self) -> bool:
        """
        Connect to TTS service.

        Default implementation sets connected flag.
        Override this method in subclasses for specific behavior.

        Returns:
            True if connection successful, False otherwise
        """
        self._is_connected = True
        logger.info("TTS adapter connected", extra={"model": self.config.model_name})
        return True

    async def disconnect(self) -> None:
        """Disconnect from TTS service.

        Default implementation clears connected flag.
        Override this method in subclasses for specific behavior.
        """
        self._is_connected = False
        logger.info("TTS adapter disconnected", extra={"model": self.config.model_name})

    async def synthesize(
        self, text: str, voice: str | None = None, language: str | None = None
    ) -> TTSResult:
        """
        Synthesize text to speech.

        Default implementation returns empty result.
        Override this method in subclasses for specific behavior.

        Args:
            text: Text to synthesize
            voice: Voice to use (optional)
            language: Language to use (optional)

        Returns:
            TTS result containing audio data and metadata
        """
        from datetime import datetime

        return TTSResult(
            audio_data=b"",
            audio_format=AudioFormat.WAV,
            text=text,
            voice=voice or self.config.voice,
            language=language or self.config.language,
            duration=0.0,
            processing_time=0.0,
            timestamp=datetime.now(),
        )

    def synthesize_stream(
        self, text: str, voice: str | None = None, language: str | None = None
    ) -> AsyncGenerator[TTSResult, None]:
        """
        Synthesize text to speech with streaming output.

        Default implementation yields empty results.
        Override this method in subclasses for specific behavior.

        Args:
            text: Text to synthesize
            voice: Voice to use (optional)
            language: Language to use (optional)

        Yields:
            TTS results as they become available
        """

        # Default implementation - override in subclasses
        async def empty_stream() -> AsyncGenerator[TTSResult, None]:
            yield await self.synthesize(text, voice, language)

        return empty_stream()

    async def get_available_voices(self) -> list[dict[str, Any]]:
        """
        Get list of available voices.

        Default implementation returns configured voice.
        Override this method in subclasses for specific behavior.

        Returns:
            List of available voices with metadata
        """
        return [
            {
                "name": self.config.voice,
                "language": self.config.language,
                "gender": "neutral",
                "sample_rate": self.config.sample_rate,
            }
        ]

    async def get_supported_languages(self) -> list[str]:
        """
        Get list of supported languages.

        Default implementation returns configured language.
        Override this method in subclasses for specific behavior.

        Returns:
            List of supported language codes
        """
        return [self.config.language]

    async def get_model_info(self) -> dict[str, Any]:
        """
        Get information about the current model.

        Default implementation returns basic model info.
        Override this method in subclasses for specific behavior.

        Returns:
            Dictionary containing model information
        """
        return {
            "model_name": self.config.model_name,
            "voice": self.config.voice,
            "language": self.config.language,
            "sample_rate": self.config.sample_rate,
        }

    async def get_telemetry(self) -> dict[str, Any]:
        """
        Get telemetry and performance metrics.

        Default implementation returns basic telemetry.
        Override this method in subclasses for specific behavior.

        Returns:
            Dictionary containing telemetry data
        """
        return {
            "is_initialized": self._is_initialized,
            "is_connected": self._is_connected,
            "model_name": self.config.model_name,
        }

    @property
    def is_initialized(self) -> bool:
        """Check if adapter is initialized."""
        return self._is_initialized

    @property
    def is_connected(self) -> bool:
        """Check if adapter is connected."""
        return self._is_connected

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value for this adapter."""
        return getattr(self.config, key, default)

    def set_config(self, key: str, value: Any) -> None:
        """Set a configuration value for this adapter."""
        setattr(self.config, key, value)

    def validate_config(self) -> bool:
        """Validate adapter configuration."""
        return bool(
            self.config.model_name and self.config.voice and self.config.language
        )

    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            await self.disconnect()
            self._is_initialized = False
        except Exception as e:
            # Log error but don't raise
            logger.warning("Error during cleanup: %s", e)
