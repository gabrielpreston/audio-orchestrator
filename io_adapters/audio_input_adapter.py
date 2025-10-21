"""Abstract base class for audio input adapters."""

from abc import ABC, abstractmethod
from typing import AsyncIterator
from audio_pipeline.types import AudioChunk


class AudioInputAdapter(ABC):
    """Abstract base class for audio input adapters."""

    @abstractmethod
    async def start(self) -> None:
        """Start the audio input adapter."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the audio input adapter."""
        pass

    @abstractmethod
    def get_audio_stream(self) -> AsyncIterator[AudioChunk]:
        """Get an async iterator of audio chunks."""
        pass
