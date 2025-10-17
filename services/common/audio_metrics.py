"""
Audio pipeline metrics and health monitoring for voice services.

This module provides centralized metrics collection for audio processing
pipelines, enabling observability and performance monitoring.
"""

import time
from dataclasses import dataclass, field
from typing import Any

from services.common.logging import get_logger


@dataclass
class AudioPipelineMetrics:
    """Metrics collector for audio processing pipelines."""

    # Frame processing metrics
    speech_frames: int = 0
    silence_frames: int = 0
    total_frames: int = 0

    # Segment processing metrics
    segments_flushed: int = 0
    segments_dropped: int = 0

    # Audio quality metrics
    avg_rms: float = 0.0
    max_rms: float = 0.0
    min_rms: float = float("inf")

    # Performance metrics
    vad_processing_time: float = 0.0
    normalization_time: float = 0.0

    # Timestamps
    start_time: float = field(default_factory=time.monotonic)
    last_stats_time: float = field(default_factory=time.monotonic)

    def record_frame(
        self, is_speech: bool, rms: float, processing_time: float = 0.0
    ) -> None:
        """Record a processed audio frame."""
        self.total_frames += 1
        if is_speech:
            self.speech_frames += 1
        else:
            self.silence_frames += 1

        # Update RMS statistics
        self.avg_rms = (
            self.avg_rms * (self.total_frames - 1) + rms
        ) / self.total_frames
        self.max_rms = max(self.max_rms, rms)
        self.min_rms = min(self.min_rms, rms)

        # Update processing time
        self.vad_processing_time += processing_time

    def record_segment_flush(self, reason: str, duration: float) -> None:
        """Record a segment flush event."""
        self.segments_flushed += 1
        # Store reason and duration for potential future use
        _ = reason, duration

    def record_segment_drop(self, reason: str) -> None:
        """Record a dropped segment."""
        self.segments_dropped += 1
        # Store reason for potential future use
        _ = reason

    def record_normalization(self, processing_time: float) -> None:
        """Record audio normalization processing time."""
        self.normalization_time += processing_time

    def get_stats(self) -> dict[str, Any]:
        """Get current metrics as dictionary."""
        now = time.monotonic()
        uptime = now - self.start_time

        return {
            "uptime_seconds": uptime,
            "total_frames": self.total_frames,
            "speech_frames": self.speech_frames,
            "silence_frames": self.silence_frames,
            "speech_ratio": self.speech_frames / max(self.total_frames, 1),
            "segments_flushed": self.segments_flushed,
            "segments_dropped": self.segments_dropped,
            "avg_rms": self.avg_rms,
            "max_rms": self.max_rms,
            "min_rms": self.min_rms if self.min_rms != float("inf") else 0.0,
            "avg_vad_time_ms": (self.vad_processing_time / max(self.total_frames, 1))
            * 1000,
            "avg_normalization_time_ms": (
                self.normalization_time / max(self.total_frames, 1)
            )
            * 1000,
            "frames_per_second": self.total_frames / max(uptime, 0.001),
        }

    def should_report_stats(self, interval_seconds: float = 30.0) -> bool:
        """Check if it's time to report statistics."""
        now = time.monotonic()
        if now - self.last_stats_time >= interval_seconds:
            self.last_stats_time = now
            return True
        return False

    def reset(self) -> None:
        """Reset all metrics to initial state."""
        self.speech_frames = 0
        self.silence_frames = 0
        self.total_frames = 0
        self.segments_flushed = 0
        self.segments_dropped = 0
        self.avg_rms = 0.0
        self.max_rms = 0.0
        self.min_rms = float("inf")
        self.vad_processing_time = 0.0
        self.normalization_time = 0.0
        self.start_time = time.monotonic()
        self.last_stats_time = time.monotonic()


class AudioMetricsReporter:
    """Reports audio pipeline metrics to logs."""

    def __init__(self, service_name: str, correlation_id: str | None = None):
        self.service_name = service_name
        self.correlation_id = correlation_id
        self.logger = get_logger(
            __name__, service_name=service_name, correlation_id=correlation_id
        )
        self.metrics = AudioPipelineMetrics()

    def record_frame(
        self, is_speech: bool, rms: float, processing_time: float = 0.0
    ) -> None:
        """Record a processed frame and check if stats should be reported."""
        self.metrics.record_frame(is_speech, rms, processing_time)

        if self.metrics.should_report_stats():
            self._report_stats()

    def record_segment_flush(self, reason: str, duration: float) -> None:
        """Record a segment flush."""
        self.metrics.record_segment_flush(reason, duration)
        self.logger.info(
            "voice.segment_flushed",
            reason=reason,
            duration=duration,
            total_segments=self.metrics.segments_flushed,
        )

    def record_segment_drop(self, reason: str) -> None:
        """Record a dropped segment."""
        self.metrics.record_segment_drop(reason)
        self.logger.warning(
            "voice.segment_dropped",
            reason=reason,
            total_dropped=self.metrics.segments_dropped,
        )

    def record_normalization(self, processing_time: float) -> None:
        """Record normalization processing time."""
        self.metrics.record_normalization(processing_time)

    def _report_stats(self) -> None:
        """Report current statistics."""
        stats = self.metrics.get_stats()
        self.logger.info("voice.pipeline_stats", **stats)

    def get_current_stats(self) -> dict[str, Any]:
        """Get current metrics without logging."""
        return self.metrics.get_stats()

    def reset_metrics(self) -> None:
        """Reset metrics and log the reset."""
        self.metrics.reset()
        self.logger.info("voice.metrics_reset")


def create_audio_metrics_reporter(
    service_name: str, correlation_id: str | None = None
) -> AudioMetricsReporter:
    """Create an audio metrics reporter for a service."""
    return AudioMetricsReporter(service_name, correlation_id)


__all__ = [
    "AudioPipelineMetrics",
    "AudioMetricsReporter",
    "create_audio_metrics_reporter",
]
