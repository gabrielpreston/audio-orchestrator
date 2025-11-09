"""Audio types for the Python Discord voice bot.

This module contains only the essential data types used throughout the Discord service.
Audio processing logic has been moved to the audio_processor service.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Literal

from .config import AudioConfig


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


@dataclass(slots=True)
class FlushDecision:
    """Represents a decision about whether to flush an accumulator."""

    action: Literal["flush", "hold"]
    reason: str
    total_duration: float
    silence_age: float


@dataclass(slots=True)
class Accumulator:
    """Collects PCM frames for a specific speaker."""

    user_id: int
    config: AudioConfig
    frames: deque[PCMFrame] = field(default_factory=deque)
    active: bool = False
    last_activity: float = field(default_factory=time.monotonic)
    sequence: int = 0
    silence_started_at: float | None = None
    sample_rate: int = 0

    def append(self, frame: PCMFrame) -> None:
        self.frames.append(frame)
        self.last_activity = frame.timestamp
        self.active = True
        self.silence_started_at = None
        self.sample_rate = frame.sample_rate

    def mark_silence(self, timestamp: float) -> bool:
        """Register silence without resetting the voice activity timer."""
        new_silence = False
        if not self.frames:
            # No active segment yet; keep last_activity aligned with recent silence.
            self.last_activity = timestamp
        elif self.silence_started_at is None:
            self.silence_started_at = timestamp
            new_silence = True
        # When frames exist we intentionally avoid mutating last_activity
        # so silence can trigger flushes.
        return new_silence

    def should_flush(self, timestamp: float) -> FlushDecision | None:
        if not self.frames:
            return None
        start = self.frames[0].timestamp
        end = self.frames[-1].timestamp + self.frames[-1].duration
        total_duration = end - start
        silence_age = timestamp - self.last_activity
        if total_duration >= self.config.max_segment_duration_seconds:
            return FlushDecision("flush", "max_duration", total_duration, silence_age)
        if silence_age >= self.config.silence_timeout_seconds:
            if total_duration >= self.config.min_segment_duration_seconds:
                return FlushDecision(
                    "flush", "silence_timeout", total_duration, silence_age
                )
            return FlushDecision("hold", "min_duration", total_duration, silence_age)
        return None

    def pop_segment(self, correlation_id: str) -> AudioSegment | None:
        if not self.frames:
            return None
        start = self.frames[0].timestamp
        end = self.frames[-1].timestamp + self.frames[-1].duration
        pcm = b"".join(frame.pcm for frame in self.frames)

        # Validate accumulated PCM before creating segment
        if not pcm or len(pcm) == 0:
            self.frames.clear()
            return None

        # Check minimum size (at least 1 frame: channels * sample_width)
        # Assuming 16-bit mono (1 channel * 2 bytes)
        min_size = 1 * 2
        if len(pcm) < min_size:
            self.frames.clear()
            return None

        # Validate PCM has audio content (not all zeros)
        # NOTE: rms_from_pcm is defined in this file (line 127), no import needed
        accumulated_rms = rms_from_pcm(pcm)
        min_segment_rms = getattr(
            self.config, "min_segment_rms_threshold", 5.0
        )  # AudioConfig is passed directly

        if accumulated_rms < min_segment_rms:
            # All silence - don't create segment
            self.frames.clear()
            return None

        segment = AudioSegment(
            user_id=self.user_id,
            pcm=pcm,
            start_timestamp=start,
            end_timestamp=end,
            correlation_id=correlation_id,
            frame_count=len(self.frames),
            sample_rate=self.sample_rate or self.config.input_sample_rate_hz,
        )
        self.frames.clear()
        self.active = False
        self.silence_started_at = None
        return segment


def rms_from_pcm(pcm: bytes) -> float:
    """Compute RMS value for PCM audio in int16 domain (0-32767).

    Returns RMS in int16 domain for threshold comparisons.
    This fixes the bug where normalized RMS (0-1) was compared against
    int16 domain thresholds (e.g., 5.0, 10.0).

    Args:
        pcm: PCM audio data bytes (16-bit)

    Returns:
        RMS value in int16 domain (0-32767)
    """
    from services.common.audio import calculate_rms_int16

    return calculate_rms_int16(pcm, sample_width=2)


__all__ = ["Accumulator", "AudioSegment", "PCMFrame", "rms_from_pcm"]
