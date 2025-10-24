"""
Core interfaces for surface adapters.

This module defines protocol-based interfaces that all surface adapters
must implement to participate in the composable audio architecture.
"""

from __future__ import annotations

from typing import Any, Protocol

from .types import TelemetryMetrics
from .protocols import (
    AudioCaptureProtocol,
    AudioPlaybackProtocol,
    AudioMetadataProtocol,
    SurfaceControlProtocol,
    SurfaceTelemetryProtocol,
)


class SurfaceAdapter:
    """Protocol-based surface adapter combining all interfaces."""

    def __init__(self, surface_id: str, config: dict[str, Any]) -> None:
        self.surface_id = surface_id
        self.config = config
        self._audio_capture: AudioCaptureProtocol | None = None
        self._audio_playback: AudioPlaybackProtocol | None = None
        self._audio_metadata: AudioMetadataProtocol | None = None
        self._control: SurfaceControlProtocol | None = None
        self._telemetry: SurfaceTelemetryProtocol | None = None

    async def initialize(self) -> None:
        """Initialize the surface adapter."""
        # Default implementation - override in subclasses
        pass

    async def cleanup(self) -> None:
        """Clean up resources."""
        # Default implementation - override in subclasses
        pass

    @property
    def audio_capture(self) -> AudioCaptureProtocol:
        """Get audio capture interface."""
        if self._audio_capture is None:
            raise RuntimeError("Audio capture not initialized")
        return self._audio_capture

    @property
    def audio_playback(self) -> AudioPlaybackProtocol:
        """Get audio playback interface."""
        if self._audio_playback is None:
            raise RuntimeError("Audio playback not initialized")
        return self._audio_playback

    @property
    def audio_metadata(self) -> AudioMetadataProtocol:
        """Get audio metadata interface."""
        if self._audio_metadata is None:
            raise RuntimeError("Audio metadata not initialized")
        return self._audio_metadata

    @property
    def control(self) -> SurfaceControlProtocol:
        """Get control interface."""
        if self._control is None:
            raise RuntimeError("Control not initialized")
        return self._control

    @property
    def telemetry(self) -> SurfaceTelemetryProtocol:
        """Get telemetry interface."""
        if self._telemetry is None:
            raise RuntimeError("Telemetry not initialized")
        return self._telemetry


class TelemetryProvider(Protocol):
    """Protocol for telemetry data collection."""

    def get_metrics(self) -> TelemetryMetrics: ...
    def record_latency(self, operation: str, latency_ms: float) -> None: ...
    def record_error(self, error_code: str, message: str) -> None: ...
