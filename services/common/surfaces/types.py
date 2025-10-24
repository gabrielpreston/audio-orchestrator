"""
Core data types for surface abstraction layer.

This module defines the fundamental data structures used across
all surface adapters for consistent audio processing and event handling.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AudioFormat(Enum):
    """Supported audio formats."""

    PCM = "pcm"
    WAV = "wav"
    OPUS = "opus"


class EndpointingState(Enum):
    """Endpointing state machine values."""

    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"


class PlaybackAction(Enum):
    """Playback control actions."""

    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"


class SessionAction(Enum):
    """Session lifecycle actions."""

    JOIN = "join"
    LEAVE = "leave"
    MUTE = "mute"
    UNMUTE = "unmute"


@dataclass(slots=True)
class PCMFrame:
    """Represents a single PCM audio frame with metadata."""

    pcm: bytes
    timestamp: float
    rms: float
    duration: float
    sequence: int
    sample_rate: int
    channels: int = 1
    sample_width: int = 2  # 16-bit

    @property
    def frame_size_ms(self) -> float:
        """Frame duration in milliseconds."""
        return self.duration * 1000.0


@dataclass(slots=True)
class AudioMetadata:
    """Standardized audio metadata structure."""

    sample_rate: int
    channels: int
    sample_width: int  # bytes per sample
    duration: float  # seconds
    frames: int
    format: AudioFormat
    bit_depth: int  # bits per sample

    @property
    def bytes_per_second(self) -> int:
        """Calculate bytes per second."""
        return self.sample_rate * self.channels * self.sample_width

    @property
    def total_bytes(self) -> int:
        """Calculate total audio data bytes."""
        return self.frames * self.channels * self.sample_width


@dataclass(slots=True)
class AudioSegment:
    """Aggregated audio data suitable for STT submission."""

    user_id: str
    pcm: bytes
    start_timestamp: float
    end_timestamp: float
    correlation_id: str
    frame_count: int
    sample_rate: int
    channels: int = 1
    sample_width: int = 2

    @property
    def duration(self) -> float:
        """Segment duration in seconds."""
        return max(0.0, self.end_timestamp - self.start_timestamp)

    @property
    def metadata(self) -> AudioMetadata:
        """Generate AudioMetadata for this segment."""
        return AudioMetadata(
            sample_rate=self.sample_rate,
            channels=self.channels,
            sample_width=self.sample_width,
            duration=self.duration,
            frames=self.frame_count,
            format=AudioFormat.PCM,
            bit_depth=self.sample_width * 8,
        )


@dataclass(slots=True)
class ControlEvent:
    """Base class for all control channel events."""

    event_type: str
    timestamp: float = field(default_factory=time.time)
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        """Allow indexing for backward compatibility."""
        if key == "event_type":
            return self.event_type
        elif key == "timestamp":
            return self.timestamp
        elif key == "correlation_id":
            return self.correlation_id
        elif key == "metadata":
            return self.metadata
        else:
            raise KeyError(f"Unknown key: {key}")

    def __contains__(self, key: str) -> bool:
        """Check if key exists for backward compatibility."""
        return key in ["event_type", "timestamp", "correlation_id", "metadata"]

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class WordTimestamp:
    """Word-level timing information."""

    word: str
    start: float
    end: float
    confidence: float = 1.0


@dataclass(slots=True)
class TelemetryMetrics:
    """Telemetry metrics for session monitoring."""

    rtt_ms: float
    packet_loss_percent: float
    jitter_ms: float
    battery_temp: float | None = None
    e2e_latency_ms: float | None = None
    barge_in_delay_ms: float | None = None
    stt_partial_time_ms: float | None = None
    tts_first_byte_ms: float | None = None
