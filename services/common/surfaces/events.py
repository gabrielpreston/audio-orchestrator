"""
Control channel events for surface communication.

This module defines all event types used in the bidirectional
control channel between audio surfaces and the voice pipeline.
"""

# ruff: noqa: UP008
# mypy: ignore-errors

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import (
    ControlEvent,
    EndpointingState,
    PlaybackAction,
    SessionAction,
    TelemetryMetrics,
    WordTimestamp,
)

# Connection Events


@dataclass(slots=True)
class ConnectionEvent(ControlEvent):
    """Connection lifecycle event."""

    event_type: str = "connection.established"
    surface_id: str = ""
    timestamp: float = 0.0
    connection_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        base = super(ConnectionEvent, self).to_dict()
        base.update(
            {
                "surface_id": self.surface_id,
                "timestamp": self.timestamp,
                "connection_params": self.connection_params,
            }
        )
        return dict(base)


# Client → Agent Events


@dataclass(slots=True)
class WakeDetectedEvent(ControlEvent):
    """Wake phrase detected event."""

    event_type: str = "wake.detected"
    confidence: float = 1.0
    ts_device: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        base = super(WakeDetectedEvent, self).to_dict()
        base.update(
            {
                "confidence": self.confidence,
                "ts_device": self.ts_device,
            }
        )
        return dict(base)


@dataclass(slots=True)
class VADStartSpeechEvent(ControlEvent):
    """Voice activity detection - speech started."""

    event_type: str = "vad.start_speech"
    ts_device: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        base = super(VADStartSpeechEvent, self).to_dict()
        base.update(
            {
                "ts_device": self.ts_device,
            }
        )
        return dict(base)


@dataclass(slots=True)
class VADEndSpeechEvent(ControlEvent):
    """Voice activity detection - speech ended."""

    event_type: str = "vad.end_speech"
    ts_device: float = 0.0
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        base = super(VADStartSpeechEvent, self).to_dict()
        base.update(
            {
                "ts_device": self.ts_device,
                "duration_ms": self.duration_ms,
            }
        )
        return dict(base)


@dataclass(slots=True)
class BargeInRequestEvent(ControlEvent):
    """User interrupted playback to speak."""

    event_type: str = "barge_in.request"
    reason: str = "user_speech"
    ts_device: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        base = super(VADStartSpeechEvent, self).to_dict()
        base.update(
            {
                "reason": self.reason,
                "ts_device": self.ts_device,
            }
        )
        return dict(base)


@dataclass(slots=True)
class SessionStateEvent(ControlEvent):
    """Session state change event."""

    event_type: str = "session.state"
    action: SessionAction = SessionAction.JOIN

    def to_dict(self) -> dict[str, Any]:
        base = super(VADStartSpeechEvent, self).to_dict()
        base.update(
            {
                "action": self.action.value,
            }
        )
        return dict(base)


@dataclass(slots=True)
class RouteChangeEvent(ControlEvent):
    """Audio route change event."""

    event_type: str = "route.change"
    input: str = ""
    output: str = ""

    def to_dict(self) -> dict[str, Any]:
        base = super(VADStartSpeechEvent, self).to_dict()
        base.update(
            {
                "input": self.input,
                "output": self.output,
            }
        )
        return dict(base)


# Agent → Client Events


@dataclass(slots=True)
class PlaybackControlEvent(ControlEvent):
    """Playback control command."""

    event_type: str = "playback.control"
    action: PlaybackAction = PlaybackAction.START
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        base = super(PlaybackControlEvent, self).to_dict()
        base.update(
            {
                "action": self.action.value,
                "reason": self.reason,
            }
        )
        return dict(base)


@dataclass(slots=True)
class EndpointingEvent(ControlEvent):
    """Endpointing state change."""

    event_type: str = "endpointing"
    state: EndpointingState = EndpointingState.LISTENING

    def to_dict(self) -> dict[str, Any]:
        base = super(VADStartSpeechEvent, self).to_dict()
        base.update(
            {
                "state": self.state.value,
            }
        )
        return dict(base)


@dataclass(slots=True)
class TranscriptPartialEvent(ControlEvent):
    """Partial transcript from STT."""

    event_type: str = "transcript.partial"
    text: str = ""
    confidence: float = 1.0
    ts_server: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        base = super(VADStartSpeechEvent, self).to_dict()
        base.update(
            {
                "text": self.text,
                "confidence": self.confidence,
                "ts_server": self.ts_server,
            }
        )
        return dict(base)


@dataclass(slots=True)
class TranscriptFinalEvent(ControlEvent):
    """Final transcript from STT."""

    event_type: str = "transcript.final"
    text: str = ""
    words: list[WordTimestamp] = field(default_factory=list)

    def __post_init__(self) -> None:
        pass

    def to_dict(self) -> dict[str, Any]:
        base = super(TranscriptFinalEvent, self).to_dict()
        base.update(
            {
                "text": self.text,
                "words": [
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "confidence": w.confidence,
                    }
                    for w in self.words
                ],
            }
        )
        return dict(base)


@dataclass(slots=True)
class TelemetrySnapshotEvent(ControlEvent):
    """Telemetry metrics snapshot."""

    event_type: str = "telemetry.snapshot"
    metrics: TelemetryMetrics = field(
        default_factory=lambda: TelemetryMetrics(
            rtt_ms=0.0,
            packet_loss_percent=0.0,
            jitter_ms=0.0,
        )
    )

    def __post_init__(self) -> None:
        pass

    def to_dict(self) -> dict[str, Any]:
        base = super(VADStartSpeechEvent, self).to_dict()
        base.update(
            {
                "rtt_ms": self.metrics.rtt_ms,
                "packet_loss_percent": self.metrics.packet_loss_percent,
                "jitter_ms": self.metrics.jitter_ms,
                "battery_temp": self.metrics.battery_temp,
                "e2e_latency_ms": self.metrics.e2e_latency_ms,
                "barge_in_delay_ms": self.metrics.barge_in_delay_ms,
                "stt_partial_time_ms": self.metrics.stt_partial_time_ms,
                "tts_first_byte_ms": self.metrics.tts_first_byte_ms,
            }
        )
        return dict(base)


@dataclass(slots=True)
class ErrorEvent(ControlEvent):
    """Error event with recovery information."""

    event_type: str = "error"
    code: str = ""
    message: str = ""
    recoverable: bool = True

    def to_dict(self) -> dict[str, Any]:
        base = super(VADStartSpeechEvent, self).to_dict()
        base.update(
            {
                "code": self.code,
                "message": self.message,
                "recoverable": self.recoverable,
            }
        )
        return dict(base)
