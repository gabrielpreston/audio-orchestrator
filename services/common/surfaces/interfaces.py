"""
Core interfaces for surface adapters.

This module defines the abstract base classes that all surface adapters
must implement to participate in the composable audio architecture.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from typing import Any, Protocol

from .types import AudioMetadata, PCMFrame, TelemetryMetrics


class AudioSource(Protocol):
    """Protocol for audio capture from surfaces."""

    @abstractmethod
    async def start_capture(self) -> None:
        """Start audio capture."""

    @abstractmethod
    async def stop_capture(self) -> None:
        """Stop audio capture."""

    @abstractmethod
    async def get_audio_frames(self) -> AsyncIterator[PCMFrame]:
        """Get audio frames as they arrive."""

    @abstractmethod
    def get_metadata(self) -> AudioMetadata:
        """Get current audio metadata."""

    @abstractmethod
    def set_frame_callback(self, callback: Callable[[PCMFrame], None]) -> None:
        """Set callback for incoming audio frames."""


class AudioSink(Protocol):
    """Protocol for audio playback to surfaces."""

    @abstractmethod
    async def play_audio(self, audio_data: bytes, metadata: AudioMetadata) -> None:
        """Play audio data."""

    @abstractmethod
    async def pause_playback(self) -> None:
        """Pause current playback."""

    @abstractmethod
    async def resume_playback(self) -> None:
        """Resume paused playback."""

    @abstractmethod
    async def stop_playback(self) -> None:
        """Stop current playback."""

    @abstractmethod
    def is_playing(self) -> bool:
        """Check if currently playing audio."""


class ControlChannel(Protocol):
    """Protocol for bidirectional control communication."""

    @abstractmethod
    async def send_event(self, event: Any) -> None:
        """Send control event."""

    @abstractmethod
    async def receive_events(self) -> AsyncIterator[Any]:
        """Receive control events."""

    @abstractmethod
    def set_event_handler(
        self, event_type: str, handler: Callable[[Any], None]
    ) -> None:
        """Set handler for specific event type."""

    @abstractmethod
    async def close(self) -> None:
        """Close control channel."""


class SurfaceLifecycle(Protocol):
    """Protocol for surface connection lifecycle."""

    @abstractmethod
    async def prepare(self) -> None:
        """Prepare surface for connection."""

    @abstractmethod
    async def connect(self) -> None:
        """Connect to surface."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from surface."""

    @abstractmethod
    async def publish(self, data: Any) -> None:
        """Publish data to surface."""

    @abstractmethod
    async def subscribe(self, callback: Callable[[Any], None]) -> None:
        """Subscribe to surface events."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if surface is connected."""


class SurfaceAdapter(ABC):
    """Base class for surface adapters combining all interfaces."""

    def __init__(self, surface_id: str, config: dict[str, Any]) -> None:
        self.surface_id = surface_id
        self.config = config
        self._audio_source: AudioSource | None = None
        self._audio_sink: AudioSink | None = None
        self._control_channel: ControlChannel | None = None
        self._lifecycle: SurfaceLifecycle | None = None

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the surface adapter."""

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up resources."""

    @property
    def audio_source(self) -> AudioSource:
        """Get audio source interface."""
        if self._audio_source is None:
            raise RuntimeError("Audio source not initialized")
        return self._audio_source

    @property
    def audio_sink(self) -> AudioSink:
        """Get audio sink interface."""
        if self._audio_sink is None:
            raise RuntimeError("Audio sink not initialized")
        return self._audio_sink

    @property
    def control_channel(self) -> ControlChannel:
        """Get control channel interface."""
        if self._control_channel is None:
            raise RuntimeError("Control channel not initialized")
        return self._control_channel

    @property
    def lifecycle(self) -> SurfaceLifecycle:
        """Get lifecycle interface."""
        if self._lifecycle is None:
            raise RuntimeError("Lifecycle not initialized")
        return self._lifecycle


class TelemetryProvider(Protocol):
    """Protocol for telemetry data collection."""

    @abstractmethod
    def get_metrics(self) -> TelemetryMetrics:
        """Get current telemetry metrics."""

    @abstractmethod
    def record_latency(self, operation: str, latency_ms: float) -> None:
        """Record operation latency."""

    @abstractmethod
    def record_error(self, error_code: str, message: str) -> None:
        """Record error occurrence."""
