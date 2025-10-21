"""
Core interfaces for surface adapters.

This module defines the abstract base classes that all surface adapters
must implement to participate in the composable audio architecture.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Protocol

from .types import AudioMetadata, PCMFrame, TelemetryMetrics


class AudioSource(ABC):
    """Abstract base class for audio capture from surfaces."""

    @abstractmethod
    async def start_capture(self) -> None:
        """Start audio capture."""

    @abstractmethod
    async def stop_capture(self) -> None:
        """Stop audio capture."""

    @abstractmethod
    async def read_audio_frame(self) -> PCMFrame | None:
        """Read a single audio frame."""

    @abstractmethod
    def get_metadata(self) -> AudioMetadata:
        """Get current audio metadata."""

    @abstractmethod
    def set_frame_callback(self, callback: Callable[[PCMFrame], None]) -> None:
        """Set callback for incoming audio frames."""


class AudioSink(ABC):
    """Abstract base class for audio playback to surfaces."""

    @abstractmethod
    async def play_audio_chunk(self, frame: PCMFrame) -> None:
        """Play audio frame."""

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


class ControlChannel(ABC):
    """Abstract base class for bidirectional control communication."""

    @abstractmethod
    async def send_event(self, event: Any) -> None:
        """Send control event."""

    @abstractmethod
    async def receive_event(self) -> Any | None:
        """Receive a single control event."""

    @abstractmethod
    def register_event_handler(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """Set handler for specific event type."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect control channel."""


class SurfaceLifecycle(ABC):
    """Abstract base class for surface connection lifecycle."""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to surface. Returns success status."""

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from surface. Returns success status."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if surface is connected."""

    @abstractmethod
    async def get_telemetry(self) -> dict[str, Any]:
        """Get telemetry data."""


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
