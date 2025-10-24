"""
Speech-to-Text (STT) adapter interface.

This module defines protocol-based interfaces for STT adapters, allowing different
STT services to be used interchangeably in the voice pipeline.
"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .types import AudioFormat, AudioMetadata


logger = logging.getLogger(__name__)


@dataclass
class STTConfig:
    """Configuration for STT adapter."""

    # Model configuration
    model_name: str = "base"
    model_size: str = "base"
    language: str = "en"

    # Processing configuration
    enable_vad: bool = True
    enable_punctuation: bool = True
    enable_diarization: bool = False

    # Performance configuration
    batch_size: int = 1
    max_audio_length: float = 30.0  # seconds
    min_audio_length: float = 0.1  # seconds

    # Quality configuration
    temperature: float = 0.0
    beam_size: int = 5
    patience: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_name": self.model_name,
            "model_size": self.model_size,
            "language": self.language,
            "enable_vad": self.enable_vad,
            "enable_punctuation": self.enable_punctuation,
            "enable_diarization": self.enable_diarization,
            "batch_size": self.batch_size,
            "max_audio_length": self.max_audio_length,
            "min_audio_length": self.min_audio_length,
            "temperature": self.temperature,
            "beam_size": self.beam_size,
            "patience": self.patience,
        }


@dataclass
class STTResult:
    """Result from STT processing."""

    # Transcript content
    text: str
    confidence: float
    language: str

    # Timing information
    start_time: float
    end_time: float
    duration: float

    # Metadata
    model_name: str
    processing_time: float
    timestamp: datetime

    # Optional fields
    words: list[dict[str, Any]] | None = None
    segments: list[dict[str, Any]] | None = None
    speaker_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "confidence": self.confidence,
            "language": self.language,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "model_name": self.model_name,
            "processing_time": self.processing_time,
            "timestamp": self.timestamp.isoformat(),
            "words": self.words,
            "segments": self.segments,
            "speaker_id": self.speaker_id,
        }


class DefaultSTTAdapter:
    """Default implementation of STT adapter protocols.

    This provides a concrete implementation that can be used as a base
    for STT adapter implementations or as a standalone adapter.
    """

    def __init__(self, config: STTConfig):
        """
        Initialize STT adapter.

        Args:
            config: STT configuration
        """
        self.config = config
        self._is_initialized = False
        self._is_connected = False

    async def initialize(self) -> bool:
        """
        Initialize the STT adapter.

        Default implementation sets initialized flag.
        Override this method in subclasses for specific behavior.

        Returns:
            True if initialization successful, False otherwise
        """
        self._is_initialized = True
        logger.info("STT adapter initialized", extra={"model": self.config.model_name})
        return True

    async def connect(self) -> bool:
        """
        Connect to STT service.

        Default implementation sets connected flag.
        Override this method in subclasses for specific behavior.

        Returns:
            True if connection successful, False otherwise
        """
        self._is_connected = True
        logger.info("STT adapter connected", extra={"model": self.config.model_name})
        return True

    async def disconnect(self) -> None:
        """Disconnect from STT service.

        Default implementation clears connected flag.
        Override this method in subclasses for specific behavior.
        """
        self._is_connected = False
        logger.info("STT adapter disconnected", extra={"model": self.config.model_name})

    async def transcribe(
        self,
        audio_data: bytes,
        audio_format: AudioFormat,
        metadata: AudioMetadata | None = None,
    ) -> STTResult:
        """
        Transcribe audio data to text.

        Default implementation returns empty result.
        Override this method in subclasses for specific behavior.

        Args:
            audio_data: Raw audio data
            audio_format: Audio format information
            metadata: Optional audio metadata

        Returns:
            STT result containing transcript and metadata
        """
        from datetime import datetime

        return STTResult(
            text="",
            confidence=0.0,
            language=self.config.language,
            start_time=0.0,
            end_time=0.0,
            duration=0.0,
            model_name=self.config.model_name,
            processing_time=0.0,
            timestamp=datetime.now(),
        )

    def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        audio_format: AudioFormat,
        metadata: AudioMetadata | None = None,
    ) -> AsyncGenerator[STTResult, None]:
        """
        Transcribe streaming audio data.

        Default implementation yields empty results.
        Override this method in subclasses for specific behavior.

        Args:
            audio_stream: Async generator of audio data chunks
            audio_format: Audio format information
            metadata: Optional audio metadata

        Yields:
            STT results as they become available
        """

        # Default implementation - override in subclasses
        async def empty_stream() -> AsyncGenerator[STTResult, None]:
            yield await self.transcribe(b"", audio_format, metadata)

        return empty_stream()

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
            "model_size": self.config.model_size,
            "language": self.config.language,
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
        return bool(self.config.model_name and self.config.language)

    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            await self.disconnect()
            self._is_initialized = False
        except Exception as e:
            # Log error but don't raise
            logger.warning("Error during cleanup: %s", e)
