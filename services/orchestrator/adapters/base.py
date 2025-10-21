"""Abstract base classes for audio adapters.

This module defines the core interfaces that all audio adapters must implement,
providing a consistent contract for audio input and output operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from services.common.logging import get_logger

from .types import AdapterConfig, AudioChunk, AudioMetadata

logger = get_logger(__name__)


class AudioInputAdapter(ABC):
    """Abstract base class for audio input adapters.
    
    This defines the interface that all audio input adapters must implement.
    Input adapters are responsible for capturing audio from various sources.
    """
    
    def __init__(self, config: AdapterConfig) -> None:
        """Initialize the audio input adapter.
        
        Args:
            config: Adapter configuration
        """
        self.config = config
        self._logger = get_logger(self.__class__.__name__)
        self._is_capturing = False
        self._logger.info(
            "Audio input adapter initialized",
            extra={
                "adapter_type": self.config.adapter_type,
                "adapter_name": self.config.name,
                "enabled": self.config.enabled
            }
        )
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique adapter identifier."""
        pass
    
    @property
    def is_capturing(self) -> bool:
        """Check if the adapter is currently capturing audio."""
        return self._is_capturing
    
    @abstractmethod
    async def start_capture(self) -> None:
        """Start capturing audio from the input source.
        
        This should begin the audio capture process and set up any necessary
        connections or resources.
        
        Raises:
            AdapterError: If capture cannot be started
        """
        pass
    
    @abstractmethod
    async def stop_capture(self) -> None:
        """Stop capturing audio from the input source.
        
        This should clean up any resources and connections used for capture.
        """
        pass
    
    @abstractmethod
    async def get_audio_stream(self) -> AsyncIterator[AudioChunk]:
        """Get an async iterator of audio chunks.
        
        This should yield audio chunks as they become available from the input source.
        
        Yields:
            AudioChunk: Audio data with metadata
            
        Raises:
            AdapterError: If stream cannot be established
        """
        pass
    
    async def get_capabilities(self) -> dict[str, Any]:
        """Get adapter capabilities.
        
        Returns:
            Dictionary describing adapter capabilities
        """
        return {
            "adapter_type": self.config.adapter_type,
            "name": self.name,
            "can_capture": True,
            "supports_streaming": True
        }
    
    async def health_check(self) -> dict[str, Any]:
        """Perform a health check for this adapter.
        
        Returns:
            Health check results
        """
        return {
            "adapter_name": self.name,
            "adapter_type": self.config.adapter_type,
            "is_capturing": self._is_capturing,
            "enabled": self.config.enabled,
            "status": "healthy" if self.config.enabled else "disabled"
        }
    
    def __str__(self) -> str:
        """String representation of the adapter."""
        return f"{self.__class__.__name__}(name={self.name})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the adapter."""
        return f"{self.__class__.__name__}(name={self.name}, config={self.config})"


class AudioOutputAdapter(ABC):
    """Abstract base class for audio output adapters.
    
    This defines the interface that all audio output adapters must implement.
    Output adapters are responsible for playing audio to various destinations.
    """
    
    def __init__(self, config: AdapterConfig) -> None:
        """Initialize the audio output adapter.
        
        Args:
            config: Adapter configuration
        """
        self.config = config
        self._logger = get_logger(self.__class__.__name__)
        self._is_playing = False
        self._logger.info(
            "Audio output adapter initialized",
            extra={
                "adapter_type": self.config.adapter_type,
                "adapter_name": self.config.name,
                "enabled": self.config.enabled
            }
        )
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique adapter identifier."""
        pass
    
    @property
    def is_playing(self) -> bool:
        """Check if the adapter is currently playing audio."""
        return self._is_playing
    
    @abstractmethod
    async def start_playback(self) -> None:
        """Start audio playback.
        
        This should initialize the audio output system and prepare for playback.
        
        Raises:
            AdapterError: If playback cannot be started
        """
        pass
    
    @abstractmethod
    async def stop_playback(self) -> None:
        """Stop audio playback.
        
        This should clean up any resources used for playback.
        """
        pass
    
    @abstractmethod
    async def play_audio(self, audio_chunk: AudioChunk) -> None:
        """Play an audio chunk.
        
        Args:
            audio_chunk: Audio data to play
            
        Raises:
            AdapterError: If audio cannot be played
        """
        pass
    
    @abstractmethod
    async def play_audio_stream(self, audio_stream: AsyncIterator[AudioChunk]) -> None:
        """Play a stream of audio chunks.
        
        Args:
            audio_stream: Async iterator of audio chunks to play
            
        Raises:
            AdapterError: If stream cannot be played
        """
        pass
    
    async def get_capabilities(self) -> dict[str, Any]:
        """Get adapter capabilities.
        
        Returns:
            Dictionary describing adapter capabilities
        """
        return {
            "adapter_type": self.config.adapter_type,
            "name": self.name,
            "can_play": True,
            "supports_streaming": True
        }
    
    async def health_check(self) -> dict[str, Any]:
        """Perform a health check for this adapter.
        
        Returns:
            Health check results
        """
        return {
            "adapter_name": self.name,
            "adapter_type": self.config.adapter_type,
            "is_playing": self._is_playing,
            "enabled": self.config.enabled,
            "status": "healthy" if self.config.enabled else "disabled"
        }
    
    def __str__(self) -> str:
        """String representation of the adapter."""
        return f"{self.__class__.__name__}(name={self.name})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the adapter."""
        return f"{self.__class__.__name__}(name={self.name}, config={self.config})"
