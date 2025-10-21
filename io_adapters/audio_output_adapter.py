"""Abstract base class for audio output adapters."""

from abc import ABC, abstractmethod
from typing import AsyncIterator
from audio_pipeline.types import AudioChunk


class AudioOutputAdapter(ABC):
    """Abstract base class for audio output adapters."""

    @abstractmethod
    async def play_audio(self, audio_stream: AsyncIterator[AudioChunk]) -> None:
        """Play audio from the given stream."""
        pass
