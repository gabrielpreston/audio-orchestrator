"""Core type definitions for the adapter framework.

This module defines the fundamental data structures used throughout the adapter system,
including audio chunks, metadata, and configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from services.common.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AudioMetadata:
    """Metadata for audio data.
    
    Contains information about audio format, quality, and processing details.
    """
    sample_rate: int
    channels: int
    sample_width: int
    duration: float
    frames: int
    format: str
    bit_depth: int
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self) -> None:
        """Validate metadata after initialization."""
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if self.channels <= 0:
            raise ValueError("channels must be positive")
        if self.sample_width <= 0:
            raise ValueError("sample_width must be positive")
        if self.duration < 0:
            raise ValueError("duration must be non-negative")
        if self.frames < 0:
            raise ValueError("frames must be non-negative")
        if self.bit_depth <= 0:
            raise ValueError("bit_depth must be positive")


@dataclass
class AudioChunk:
    """A chunk of audio data with metadata.
    
    Represents a discrete piece of audio data that can be processed
    by the audio pipeline.
    """
    data: bytes
    metadata: AudioMetadata
    correlation_id: str
    sequence_number: int
    is_silence: bool = False
    volume_level: float = 0.0
    
    def __post_init__(self) -> None:
        """Validate audio chunk after initialization."""
        if not self.data:
            raise ValueError("data cannot be empty")
        if not self.correlation_id:
            raise ValueError("correlation_id cannot be empty")
        if self.sequence_number < 0:
            raise ValueError("sequence_number must be non-negative")
        if not 0.0 <= self.volume_level <= 1.0:
            raise ValueError("volume_level must be between 0.0 and 1.0")
    
    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        return self.metadata.duration
    
    @property
    def size_bytes(self) -> int:
        """Get size in bytes."""
        return len(self.data)
    
    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the audio chunk."""
        return {
            "correlation_id": self.correlation_id,
            "sequence_number": self.sequence_number,
            "duration_seconds": self.duration_seconds,
            "size_bytes": self.size_bytes,
            "sample_rate": self.metadata.sample_rate,
            "channels": self.metadata.channels,
            "is_silence": self.is_silence,
            "volume_level": self.volume_level,
            "format": self.metadata.format,
        }


@dataclass
class AdapterConfig:
    """Configuration for an adapter.
    
    Contains adapter-specific settings and parameters.
    """
    adapter_type: str
    name: str
    enabled: bool = True
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.adapter_type:
            raise ValueError("adapter_type cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")
        if not isinstance(self.parameters, dict):
            raise ValueError("parameters must be a dictionary")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a configuration parameter."""
        return self.parameters.get(key, default)
    
    def set_parameter(self, key: str, value: Any) -> None:
        """Set a configuration parameter."""
        self.parameters[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value."""
        return self.metadata.get(key, default)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata value."""
        self.metadata[key] = value
