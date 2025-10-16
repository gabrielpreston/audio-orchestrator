"""
Speech-to-Text (STT) adapter interface.

This module defines the interface for STT adapters, allowing different
STT services to be used interchangeably in the voice pipeline.
"""

import logging
from abc import ABC, abstractmethod
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


class STTAdapter(ABC):
    """Abstract base class for STT adapters."""

    def __init__(self, config: STTConfig):
        """
        Initialize STT adapter.

        Args:
            config: STT configuration
        """
        self.config = config
        self._is_initialized = False
        self._is_connected = False

    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the STT adapter.

        Returns:
            True if initialization successful, False otherwise
        """

    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to STT service.

        Returns:
            True if connection successful, False otherwise
        """

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from STT service."""

    @abstractmethod
    async def transcribe(
        self,
        audio_data: bytes,
        audio_format: AudioFormat,
        metadata: AudioMetadata | None = None,
    ) -> STTResult:
        """
        Transcribe audio data to text.

        Args:
            audio_data: Raw audio data
            audio_format: Audio format information
            metadata: Optional audio metadata

        Returns:
            STT result containing transcript and metadata
        """

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        audio_format: AudioFormat,
        metadata: AudioMetadata | None = None,
    ) -> AsyncGenerator[STTResult, None]:
        """
        Transcribe streaming audio data.

        Args:
            audio_stream: Async generator of audio data chunks
            audio_format: Audio format information
            metadata: Optional audio metadata

        Yields:
            STT results as they become available
        """

    @abstractmethod
    async def get_supported_languages(self) -> list[str]:
        """
        Get list of supported languages.

        Returns:
            List of supported language codes
        """

    @abstractmethod
    async def get_model_info(self) -> dict[str, Any]:
        """
        Get information about the current model.

        Returns:
            Dictionary containing model information
        """

    @abstractmethod
    async def get_telemetry(self) -> dict[str, Any]:
        """
        Get telemetry and performance metrics.

        Returns:
            Dictionary containing telemetry data
        """

    def is_initialized(self) -> bool:
        """Check if adapter is initialized."""
        return self._is_initialized

    def is_connected(self) -> bool:
        """Check if adapter is connected."""
        return self._is_connected

    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            await self.disconnect()
            self._is_initialized = False
        except Exception as e:
            # Log error but don't raise
            logger.warning("Error during cleanup: %s", e)
