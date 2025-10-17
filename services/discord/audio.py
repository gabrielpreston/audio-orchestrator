"""Audio pipeline primitives for the Python Discord voice bot."""

from __future__ import annotations

import audioop
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal

import webrtcvad

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


class AudioPipeline:
    """Manages audio accumulation per Discord speaker."""

    def __init__(self, config: AudioConfig) -> None:
        self._config = config
        self._accumulators: dict[int, Accumulator] = {}
        self._logger = get_logger(__name__, service_name="discord")
        frame_ms = config.vad_frame_duration_ms
        if frame_ms not in (10, 20, 30):
            nearest = min((10, 20, 30), key=lambda value: abs(value - frame_ms))
            self._logger.warning(
                "voice.vad_frame_adjusted",
                requested=frame_ms,
                applied=nearest,
            )
            frame_ms = nearest
        self._vad_frame_duration_ms = frame_ms
        aggressiveness = config.vad_aggressiveness
        if aggressiveness < 0 or aggressiveness > 3:
            clamped = min(max(aggressiveness, 0), 3)
            self._logger.warning(
                "voice.vad_aggressiveness_clamped",
                requested=aggressiveness,
                applied=clamped,
            )
            aggressiveness = clamped
        self._target_sample_rate = config.vad_sample_rate_hz
        self._vad: Any = webrtcvad.Vad(aggressiveness)
        self._vad_frame_bytes = int(self._target_sample_rate * frame_ms / 1000) * 2

        self._logger.info(
            "voice.vad_configured",
            aggressiveness=aggressiveness,
            frame_duration_ms=frame_ms,
            target_sample_rate=self._target_sample_rate,
            frame_bytes=self._vad_frame_bytes,
            min_segment_duration=self._config.min_segment_duration_seconds,
            max_segment_duration=self._config.max_segment_duration_seconds,
            silence_timeout=self._config.silence_timeout_seconds,
            aggregation_window=self._config.aggregation_window_seconds,
        )

        # Initialize metrics reporter
        from services.common.audio_metrics import create_audio_metrics_reporter

        self._metrics_reporter = create_audio_metrics_reporter("discord")

    def _allowed(self, user_id: int) -> bool:
        if not self._config.allowlist_user_ids:
            return True
        return user_id in self._config.allowlist_user_ids

    def register_frame(
        self,
        user_id: int,
        pcm: bytes,
        rms: float,
        duration: float,
        sample_rate: int,
    ) -> AudioSegment | None:
        if not self._allowed(user_id):
            self._logger.debug(
                "voice.frame_rejected",
                user_id=user_id,
                reason="allowlist",
            )
            return None

        timestamp = time.monotonic()
        accumulator = self._accumulators.setdefault(
            user_id,
            Accumulator(user_id=user_id, config=self._config),
        )
        accumulator.sequence += 1
        normalized_pcm, adjusted_rms = self._normalize_pcm(
            pcm, target_rms=rms, user_id=user_id
        )
        frame = PCMFrame(
            pcm=normalized_pcm,
            timestamp=timestamp,
            rms=adjusted_rms,
            duration=duration,
            sequence=accumulator.sequence,
            sample_rate=sample_rate,
        )

        is_speech = self._is_speech(frame.pcm, frame.sample_rate)

        # Sample VAD decisions to reduce log verbosity
        if self._should_log_vad_decision(accumulator.sequence):
            self._logger.debug(
                "voice.vad_decision",
                user_id=user_id,
                sequence=accumulator.sequence,
                is_speech=is_speech,
                rms=adjusted_rms,
                frame_bytes=len(normalized_pcm),
                sample_rate=sample_rate,
                raw_pcm_bytes=len(pcm),  # NEW: Show original PCM size
                pcm_is_empty=len(pcm) == 0,  # NEW: Check if PCM is empty
            )

        # Record metrics for monitoring
        self._metrics_reporter.record_frame(is_speech, adjusted_rms)

        if not is_speech:
            accumulator.mark_silence(timestamp)
            decision = accumulator.should_flush(timestamp)
            if decision and decision.action == "flush":
                return self._flush_accumulator(
                    accumulator,
                    timestamp=timestamp,
                    decision=decision,
                    trigger="silence_check",
                )
            return None

        accumulator.append(frame)
        self._logger.debug(
            "voice.frame_buffered",
            user_id=user_id,
            sequence=frame.sequence,
            rms=frame.rms,
            duration=duration,
            sample_rate=sample_rate,
        )
        decision = accumulator.should_flush(timestamp)
        if decision and decision.action == "flush":
            return self._flush_accumulator(
                accumulator,
                timestamp=timestamp,
                decision=decision,
                trigger="speech_check",
            )
        return None

    def force_flush(self) -> list[AudioSegment]:
        segments: list[AudioSegment] = []
        for accumulator in self._accumulators.values():
            segment = self._flush_accumulator(
                accumulator,
                timestamp=time.monotonic(),
                trigger="force_flush",
            )
            if segment:
                segments.append(segment)
        return segments

    def flush_inactive(self) -> list[AudioSegment]:
        """Flush accumulators that have exceeded silence timeout without new frames."""

        segments: list[AudioSegment] = []
        timestamp = time.monotonic()
        aggregation_window = max(self._config.aggregation_window_seconds, 0.0)
        for accumulator in self._accumulators.values():
            decision = accumulator.should_flush(timestamp)
            if not decision:
                continue
            flush = decision.action == "flush"
            decision_reason = decision.reason
            if (
                not flush
                and decision.reason == "min_duration"
                and aggregation_window > 0
                and decision.silence_age >= aggregation_window
            ):
                flush = True
                decision_reason = "aggregation_window"
            if flush:
                segment = self._flush_accumulator(
                    accumulator,
                    timestamp=timestamp,
                    decision=decision,
                    trigger="idle_flush",
                    override_reason=decision_reason,
                )
                if segment:
                    segments.append(segment)
        return segments

    def _flush_accumulator(
        self,
        accumulator: Accumulator,
        *,
        decision: FlushDecision | None = None,
        trigger: str | None = None,
        override_reason: str | None = None,
        timestamp: float | None = None,
    ) -> AudioSegment | None:
        from services.common.correlation import generate_discord_correlation_id

        correlation_id = generate_discord_correlation_id(accumulator.user_id)
        segment = accumulator.pop_segment(correlation_id)
        if not segment:
            return None

        # Bind correlation ID to logger for this segment
        from services.common.logging import bind_correlation_id

        segment_logger = bind_correlation_id(self._logger, segment.correlation_id)

        reason = (
            override_reason
            or (decision.reason if decision else None)
            or trigger
            or "unknown"
        )
        # Count speech vs silence frames for diagnostics
        speech_frames = sum(1 for frame in accumulator.frames if frame.rms > 100)
        silence_frames = len(accumulator.frames) - speech_frames

        segment_logger.info(
            "voice.segment_ready",
            user_id=segment.user_id,
            frames=segment.frame_count,
            duration=segment.duration,
            pcm_bytes=len(segment.pcm),
            sample_rate=segment.sample_rate,
            flush_reason=reason,
            silence_age=decision.silence_age if decision else None,
            total_duration=decision.total_duration if decision else segment.duration,
            flush_trigger=trigger,
            correlation_id=segment.correlation_id,
            speech_frames=speech_frames,  # NEW: Count of speech frames
            silence_frames=silence_frames,  # NEW: Count of silence frames
        )

        # Record segment flush in metrics
        self._metrics_reporter.record_segment_flush(reason, segment.duration)
        return segment

    def _prepare_vad_frame(self, pcm: bytes, sample_rate: int) -> bytes:
        if not pcm:
            return pcm
        if sample_rate != self._target_sample_rate:
            try:
                pcm, _ = audioop.ratecv(
                    pcm, 2, 1, sample_rate, self._target_sample_rate, None
                )
            except Exception as exc:
                self._logger.warning(
                    "voice.vad_resample_failed",
                    error=str(exc),
                    source_rate=sample_rate,
                    target_rate=self._target_sample_rate,
                )
                return b""
        if len(pcm) < self._vad_frame_bytes:
            pcm = pcm.ljust(self._vad_frame_bytes, b"\x00")
        elif len(pcm) > self._vad_frame_bytes:
            pcm = pcm[: self._vad_frame_bytes]
        return pcm

    def _is_speech(self, pcm: bytes, sample_rate: int) -> bool:
        frame = self._prepare_vad_frame(pcm, sample_rate)
        if not frame:
            return False
        try:
            return bool(self._vad.is_speech(frame, self._target_sample_rate))
        except Exception as exc:
            self._logger.warning("voice.vad_error", error=str(exc))
            return False

    def _normalize_pcm(
        self,
        pcm: bytes,
        *,
        target_rms: float = 2000.0,
        user_id: int | None = None,
    ) -> tuple[bytes, float]:
        """Bring audio closer to a target RMS to reduce overly quiet or loud frames using standardized audio processing."""
        from services.common.audio import AudioProcessor

        processor = AudioProcessor("discord")
        processor.set_logger(self._logger)

        # Use standardized normalization with user_id for logging
        # If the provided target_rms is unit-scale (0..1), convert to int16 domain
        if target_rms <= 1.0:
            target_rms = max(1.0, target_rms * 32768.0)

        normalized_pcm, new_rms = processor.normalize_audio(
            pcm, target_rms, 2, user_id=user_id
        )

        return normalized_pcm, new_rms

    def _should_log_vad_decision(self, sequence: int) -> bool:
        """Determine if VAD decision should be logged to reduce verbosity."""
        # Log first 10 decisions, then 1% sampling
        return sequence <= 10 or sequence % 100 == 0


def rms_from_pcm(pcm: bytes) -> float:
    """Compute RMS value for PCM audio using standardized audio processing."""
    from services.common.audio import AudioProcessor

    processor = AudioProcessor("discord")
    return float(processor.calculate_rms(pcm, 2))


__all__ = ["Accumulator", "AudioPipeline", "AudioSegment", "PCMFrame", "rms_from_pcm"]
