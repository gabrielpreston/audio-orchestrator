"""Data types for audio processor service."""

from dataclasses import dataclass


@dataclass(slots=True)
class PCMFrame:
    """Represents a single PCM audio frame."""

    pcm: bytes
    timestamp: float
    rms: float
    duration: float
    sequence: int
    sample_rate: int


@dataclass(slots=True)
class AudioSegment:
    """Aggregated audio data suitable for STT submission."""

    user_id: int
    pcm: bytes
    start_timestamp: float
    end_timestamp: float
    correlation_id: str
    frame_count: int
    sample_rate: int

    @property
    def duration(self) -> float:
        return max(0.0, self.end_timestamp - self.start_timestamp)
