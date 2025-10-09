"""Audio pipeline primitives for the Python Discord voice bot."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Literal, Optional

import numpy as np

from services.common.logging import get_logger

from .config import AudioConfig


@dataclass(slots=True)
class PCMFrame:
    """Represents a single PCM audio frame."""

    pcm: bytes
    timestamp: float
    rms: float
    duration: float
    sequence: int


@dataclass(slots=True)
class AudioSegment:
    """Aggregated audio data suitable for STT submission."""

    user_id: int
    pcm: bytes
    start_timestamp: float
    end_timestamp: float
    correlation_id: str
    frame_count: int

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
    frames: Deque[PCMFrame] = field(default_factory=deque)
    active: bool = False
    last_activity: float = field(default_factory=time.monotonic)
    sequence: int = 0
    silence_started_at: Optional[float] = None

    def append(self, frame: PCMFrame) -> None:
        self.frames.append(frame)
        self.last_activity = frame.timestamp
        self.active = True
        self.silence_started_at = None

    def mark_silence(self, timestamp: float) -> bool:
        """Register silence without resetting the voice activity timer."""
        new_silence = False
        if not self.frames:
            # No active segment yet; keep last_activity aligned with recent silence.
            self.last_activity = timestamp
        else:
            if self.silence_started_at is None:
                self.silence_started_at = timestamp
                new_silence = True
        # When frames exist we intentionally avoid mutating last_activity so silence can trigger flushes.
        return new_silence

    def should_flush(self, timestamp: float) -> Optional[FlushDecision]:
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
                return FlushDecision("flush", "silence_timeout", total_duration, silence_age)
            return FlushDecision("hold", "min_duration", total_duration, silence_age)
        return None

    def pop_segment(self, correlation_id: str) -> Optional[AudioSegment]:
        if not self.frames:
            return None
        start = self.frames[0].timestamp
        end = self.frames[-1].timestamp + self.frames[-1].duration
        pcm = b"".join(frame.pcm for frame in self.frames)
        segment = AudioSegment(
            user_id=self.user_id,
            pcm=pcm,
            start_timestamp=start,
            end_timestamp=end,
            correlation_id=correlation_id,
            frame_count=len(self.frames),
        )
        self.frames.clear()
        self.active = False
        self.silence_started_at = None
        return segment


class AudioPipeline:
    """Manages audio accumulation per Discord speaker."""

    def __init__(self, config: AudioConfig) -> None:
        self._config = config
        self._accumulators: Dict[int, Accumulator] = {}
        self._logger = get_logger(__name__, service_name="discord")

    def _allowed(self, user_id: int) -> bool:
        if not self._config.allowlist_user_ids:
            return True
        return user_id in self._config.allowlist_user_ids

    def register_frame(self, user_id: int, pcm: bytes, rms: float, duration: float) -> Optional[AudioSegment]:
        if not self._allowed(user_id):
            self._logger.debug(
                "voice.frame_rejected",
                extra={"user_id": user_id, "reason": "allowlist"},
            )
            return None

        timestamp = time.monotonic()
        accumulator = self._accumulators.setdefault(user_id, Accumulator(user_id=user_id, config=self._config))
        accumulator.sequence += 1
        frame = PCMFrame(pcm=pcm, timestamp=timestamp, rms=rms, duration=duration, sequence=accumulator.sequence)

        if rms < self._config.vad_threshold:
            accumulator.mark_silence(timestamp)
            decision = accumulator.should_flush(timestamp)
            if decision and decision.action == "flush":
                return self._flush_accumulator(accumulator, timestamp=timestamp)
            return None

        accumulator.append(frame)
        self._logger.debug(
            "voice.frame_buffered",
            extra={
                "user_id": user_id,
                "sequence": frame.sequence,
                "rms": rms,
                "duration": duration,
                "threshold": self._config.vad_threshold,
            },
        )
        decision = accumulator.should_flush(timestamp)
        if decision and decision.action == "flush":
            return self._flush_accumulator(accumulator, timestamp=timestamp)
        return None

    def force_flush(self) -> List[AudioSegment]:
        segments: List[AudioSegment] = []
        for accumulator in self._accumulators.values():
            segment = self._flush_accumulator(accumulator, timestamp=time.monotonic())
            if segment:
                segments.append(segment)
        return segments

    def _flush_accumulator(self, accumulator: Accumulator, *, timestamp: float) -> Optional[AudioSegment]:
        correlation_id = f"discord-{accumulator.user_id}-{int(time.time() * 1000)}"
        segment = accumulator.pop_segment(correlation_id)
        if not segment:
            return None
        self._logger.info(
            "voice.segment_ready",
            extra={
                "user_id": segment.user_id,
                "correlation_id": segment.correlation_id,
                "frames": segment.frame_count,
                "duration": segment.duration,
                "pcm_bytes": len(segment.pcm),
            },
        )
        return segment


def rms_from_pcm(pcm: bytes) -> float:
    """Compute RMS value for PCM audio."""

    if not pcm:
        return 0.0
    array = np.frombuffer(pcm, dtype=np.int16)
    if array.size == 0:
        return 0.0
    mean_square = float(np.mean(np.square(array.astype(np.float32))))
    return float(np.sqrt(mean_square))


__all__ = ["AudioPipeline", "PCMFrame", "AudioSegment", "Accumulator", "rms_from_pcm"]
