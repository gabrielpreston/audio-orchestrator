"""Core type definitions for the audio pipeline framework.

This module defines the fundamental data structures used throughout the audio pipeline,
including processed segments, processing configuration, and pipeline state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


class ProcessingStatus(Enum):
    """Status of audio processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AudioFormat(Enum):
    """Supported audio formats."""
    PCM = "pcm"
    WAV = "wav"
    MP3 = "mp3"
    OPUS = "opus"
    FLAC = "flac"


@dataclass
class ProcessingConfig:
    """Configuration for audio processing pipeline.
    
    Contains settings for audio processing, wake detection, and pipeline behavior.
    """
    # Audio processing settings
    target_sample_rate: int = 16000
    target_channels: int = 1
    target_format: AudioFormat = AudioFormat.PCM
    
    # Wake detection settings
    wake_phrases: list[str] = field(default_factory=lambda: ["hey assistant", "computer"])
    wake_confidence_threshold: float = 0.8
    wake_detection_enabled: bool = True
    
    # Processing settings
    max_segment_duration: float = 30.0  # seconds
    min_segment_duration: float = 0.5   # seconds
    silence_threshold: float = 0.01
    silence_duration: float = 2.0  # seconds
    
    # Pipeline settings
    enable_audio_enhancement: bool = True
    enable_noise_reduction: bool = True
    enable_volume_normalization: bool = True
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.target_sample_rate <= 0:
            raise ValueError("target_sample_rate must be positive")
        if self.target_channels <= 0:
            raise ValueError("target_channels must be positive")
        if not 0.0 <= self.wake_confidence_threshold <= 1.0:
            raise ValueError("wake_confidence_threshold must be between 0.0 and 1.0")
        if self.max_segment_duration <= 0:
            raise ValueError("max_segment_duration must be positive")
        if self.min_segment_duration <= 0:
            raise ValueError("min_segment_duration must be positive")
        if self.min_segment_duration >= self.max_segment_duration:
            raise ValueError("min_segment_duration must be less than max_segment_duration")
        if not 0.0 <= self.silence_threshold <= 1.0:
            raise ValueError("silence_threshold must be between 0.0 and 1.0")
        if self.silence_duration <= 0:
            raise ValueError("silence_duration must be positive")


@dataclass
class ProcessedSegment:
    """A processed audio segment with metadata.
    
    Represents a processed piece of audio data that has been through
    the audio pipeline processing stages.
    """
    # Core data
    audio_data: bytes
    correlation_id: str
    session_id: str
    
    # Processing metadata
    original_format: AudioFormat
    processed_format: AudioFormat
    sample_rate: int
    channels: int
    duration: float
    
    # Processing status
    status: ProcessingStatus
    processing_time: float  # seconds
    
    # Wake detection results
    wake_detected: bool = False
    wake_phrase: str | None = None
    wake_confidence: float = 0.0
    
    # Audio quality metrics
    volume_level: float = 0.0
    noise_level: float = 0.0
    clarity_score: float = 0.0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    processed_at: datetime = field(default_factory=datetime.now)
    
    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Validate processed segment after initialization."""
        if not self.audio_data:
            raise ValueError("audio_data cannot be empty")
        if not self.correlation_id:
            raise ValueError("correlation_id cannot be empty")
        if not self.session_id:
            raise ValueError("session_id cannot be empty")
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if self.channels <= 0:
            raise ValueError("channels must be positive")
        if self.duration <= 0:
            raise ValueError("duration must be positive")
        if self.processing_time < 0:
            raise ValueError("processing_time must be non-negative")
        if not 0.0 <= self.wake_confidence <= 1.0:
            raise ValueError("wake_confidence must be between 0.0 and 1.0")
        if not 0.0 <= self.volume_level <= 1.0:
            raise ValueError("volume_level must be between 0.0 and 1.0")
        if not 0.0 <= self.noise_level <= 1.0:
            raise ValueError("noise_level must be between 0.0 and 1.0")
        if not 0.0 <= self.clarity_score <= 1.0:
            raise ValueError("clarity_score must be between 0.0 and 1.0")
    
    @property
    def size_bytes(self) -> int:
        """Get size in bytes."""
        return len(self.audio_data)
    
    @property
    def is_high_quality(self) -> bool:
        """Check if the segment meets high quality standards."""
        return (
            self.clarity_score >= 0.7 and
            self.noise_level <= 0.3 and
            self.volume_level >= 0.1
        )
    
    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the processed segment."""
        return {
            "correlation_id": self.correlation_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "duration": self.duration,
            "size_bytes": self.size_bytes,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "wake_detected": self.wake_detected,
            "wake_phrase": self.wake_phrase,
            "wake_confidence": self.wake_confidence,
            "volume_level": self.volume_level,
            "noise_level": self.noise_level,
            "clarity_score": self.clarity_score,
            "is_high_quality": self.is_high_quality,
            "processing_time": self.processing_time,
            "created_at": self.created_at.isoformat(),
            "processed_at": self.processed_at.isoformat(),
        }
