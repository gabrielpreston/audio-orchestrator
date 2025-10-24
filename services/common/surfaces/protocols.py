"""Surface system protocols for audio-orchestrator.

This module defines protocol-based interfaces for surface adapters,
replacing Abstract Base Classes with focused, composable protocols.
"""

from typing import Protocol, Any, runtime_checkable
from collections.abc import Callable
from collections.abc import AsyncIterator

from .types import PCMFrame, AudioMetadata, ControlEvent, TelemetryMetrics


@runtime_checkable
class AudioCaptureProtocol(Protocol):
    """Protocol for audio capture operations."""

    async def start_capture(self) -> None: ...
    async def stop_capture(self) -> None: ...
    async def read_audio_frame(self) -> PCMFrame | None: ...


@runtime_checkable
class AudioPlaybackProtocol(Protocol):
    """Protocol for audio playback operations."""

    async def play_audio_chunk(self, frame: PCMFrame) -> None: ...
    async def pause_playback(self) -> None: ...
    async def resume_playback(self) -> None: ...
    async def set_volume(self, volume: float) -> None: ...


@runtime_checkable
class AudioMetadataProtocol(Protocol):
    """Protocol for audio metadata."""

    def get_metadata(self) -> AudioMetadata: ...
    def set_frame_callback(self, callback: Callable[[PCMFrame], None]) -> None: ...


@runtime_checkable
class SurfaceControlProtocol(Protocol):
    """Protocol for surface control events."""

    async def send_control_event(self, event: ControlEvent) -> None: ...
    def get_control_events(self) -> AsyncIterator[ControlEvent]: ...
    async def send_event(
        self, event: ControlEvent
    ) -> None: ...  # Alias for backward compatibility


@runtime_checkable
class SurfaceTelemetryProtocol(Protocol):
    """Protocol for surface telemetry."""

    async def get_telemetry(self) -> dict[str, Any]: ...
    async def get_metrics(self) -> TelemetryMetrics: ...
    @property
    def is_connected(self) -> bool: ...  # Property for backward compatibility
