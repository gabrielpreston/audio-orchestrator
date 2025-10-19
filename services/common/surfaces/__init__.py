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
from .interfaces import AudioSink, AudioSource, ControlChannel, SurfaceLifecycle
from .types import AudioMetadata, AudioSegment, ControlEvent, PCMFrame


__all__ = [
    # Core interfaces
    "AudioSource",
    "AudioSink",
    "ControlChannel",
    "SurfaceLifecycle",
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
