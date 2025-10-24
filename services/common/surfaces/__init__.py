"""
Surface abstraction layer for composable audio interfaces.

This module provides the core interfaces and types for implementing
swappable audio surfaces (Discord, WebRTC, Mobile, etc.) in the
voice assistant pipeline.
"""

from .events import (
    BargeInRequestEvent,
    EndpointingEvent,
    ErrorEvent,
    PlaybackControlEvent,
    RouteChangeEvent,
    SessionStateEvent,
    TelemetrySnapshotEvent,
    TranscriptFinalEvent,
    TranscriptPartialEvent,
    VADEndSpeechEvent,
    VADStartSpeechEvent,
    WakeDetectedEvent,
)
from .protocols import (
    AudioCaptureProtocol,
    AudioPlaybackProtocol,
    SurfaceControlProtocol,
    SurfaceTelemetryProtocol,
)
from .types import AudioMetadata, AudioSegment, ControlEvent, PCMFrame


__all__ = [
    # Core protocols
    "AudioCaptureProtocol",
    "AudioPlaybackProtocol",
    "SurfaceControlProtocol",
    "SurfaceTelemetryProtocol",
    # Data types
    "PCMFrame",
    "AudioMetadata",
    "ControlEvent",
    "AudioSegment",
    # Events
    "WakeDetectedEvent",
    "VADStartSpeechEvent",
    "VADEndSpeechEvent",
    "BargeInRequestEvent",
    "PlaybackControlEvent",
    "EndpointingEvent",
    "TranscriptPartialEvent",
    "TranscriptFinalEvent",
    "SessionStateEvent",
    "RouteChangeEvent",
    "TelemetrySnapshotEvent",
    "ErrorEvent",
]
