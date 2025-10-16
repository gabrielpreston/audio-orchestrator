"""
Surface configuration for adapter discovery and setup.

This module defines configuration structures for surface adapters
and their connection parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


class SurfaceType(Enum):
    """Surface type enumeration."""

    DISCORD = "discord"
    WEB = "web"
    MOBILE = "mobile"
    WEBRTC = "webrtc"
    LIVEKIT = "livekit"


class SurfaceStatus(Enum):
    """Surface status enumeration."""

    AVAILABLE = "available"
    BUSY = "busy"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


@dataclass
class SurfaceCapabilities:
    """Surface capabilities configuration."""

    # Audio capabilities
    supports_audio_input: bool = True
    supports_audio_output: bool = True
    supports_stereo: bool = False
    max_sample_rate: int = 48000
    min_sample_rate: int = 8000

    # Control capabilities
    supports_wake_detection: bool = True
    supports_vad: bool = True
    supports_barge_in: bool = True
    supports_playback_control: bool = True

    # Protocol capabilities
    supports_opus: bool = True
    supports_pcm: bool = True
    supports_webrtc: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "supports_audio_input": self.supports_audio_input,
            "supports_audio_output": self.supports_audio_output,
            "supports_stereo": self.supports_stereo,
            "max_sample_rate": self.max_sample_rate,
            "min_sample_rate": self.min_sample_rate,
            "supports_wake_detection": self.supports_wake_detection,
            "supports_vad": self.supports_vad,
            "supports_barge_in": self.supports_barge_in,
            "supports_playback_control": self.supports_playback_control,
            "supports_opus": self.supports_opus,
            "supports_pcm": self.supports_pcm,
            "supports_webrtc": self.supports_webrtc,
        }


@dataclass
class SurfaceConnection:
    """Surface connection configuration."""

    # Connection details
    host: str
    port: int
    protocol: str = "http"  # http, https, ws, wss

    # Authentication
    auth_token: str | None = None
    auth_type: str = "bearer"  # bearer, basic, api_key

    # Connection settings
    timeout_ms: float = 30000.0
    retry_count: int = 3
    retry_delay_ms: float = 1000.0

    # SSL/TLS settings
    verify_ssl: bool = True
    ssl_cert_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol,
            "auth_token": self.auth_token,
            "auth_type": self.auth_type,
            "timeout_ms": self.timeout_ms,
            "retry_count": self.retry_count,
            "retry_delay_ms": self.retry_delay_ms,
            "verify_ssl": self.verify_ssl,
            "ssl_cert_path": self.ssl_cert_path,
        }


@dataclass
class SurfaceConfig:
    """Surface configuration."""

    # Basic info
    surface_id: str
    surface_type: SurfaceType
    display_name: str
    description: str = ""

    # Status and availability
    status: SurfaceStatus = SurfaceStatus.AVAILABLE
    priority: int = 0  # Higher priority = more important

    # Capabilities
    capabilities: SurfaceCapabilities = field(default_factory=SurfaceCapabilities)

    # Connection
    connection: SurfaceConnection | None = None

    # Configuration
    config: dict[str, Any] = field(default_factory=dict)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "surface_id": self.surface_id,
            "surface_type": self.surface_type.value,
            "display_name": self.display_name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority,
            "capabilities": self.capabilities.to_dict(),
            "connection": self.connection.to_dict() if self.connection else None,
            "config": self.config,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SurfaceConfig:
        """Create SurfaceConfig from dictionary."""
        config = cls(
            surface_id=data["surface_id"],
            surface_type=SurfaceType(data["surface_type"]),
            display_name=data["display_name"],
            description=data.get("description", ""),
            status=SurfaceStatus(data.get("status", "available")),
            priority=data.get("priority", 0),
            config=data.get("config", {}),
            metadata=data.get("metadata", {}),
        )

        # Set capabilities
        if "capabilities" in data:
            caps_data = data["capabilities"]
            config.capabilities = SurfaceCapabilities(
                supports_audio_input=caps_data.get("supports_audio_input", True),
                supports_audio_output=caps_data.get("supports_audio_output", True),
                supports_stereo=caps_data.get("supports_stereo", False),
                max_sample_rate=caps_data.get("max_sample_rate", 48000),
                min_sample_rate=caps_data.get("min_sample_rate", 8000),
                supports_wake_detection=caps_data.get("supports_wake_detection", True),
                supports_vad=caps_data.get("supports_vad", True),
                supports_barge_in=caps_data.get("supports_barge_in", True),
                supports_playback_control=caps_data.get(
                    "supports_playback_control", True
                ),
                supports_opus=caps_data.get("supports_opus", True),
                supports_pcm=caps_data.get("supports_pcm", True),
                supports_webrtc=caps_data.get("supports_webrtc", False),
            )

        # Set connection
        if "connection" in data and data["connection"]:
            conn_data = data["connection"]
            config.connection = SurfaceConnection(
                host=conn_data["host"],
                port=conn_data["port"],
                protocol=conn_data.get("protocol", "http"),
                auth_token=conn_data.get("auth_token"),
                auth_type=conn_data.get("auth_type", "bearer"),
                timeout_ms=conn_data.get("timeout_ms", 30000.0),
                retry_count=conn_data.get("retry_count", 3),
                retry_delay_ms=conn_data.get("retry_delay_ms", 1000.0),
                verify_ssl=conn_data.get("verify_ssl", True),
                ssl_cert_path=conn_data.get("ssl_cert_path"),
            )

        return config

    def is_available(self) -> bool:
        """Check if surface is available."""
        return self.status == SurfaceStatus.AVAILABLE

    def is_healthy(self) -> bool:
        """Check if surface is healthy."""
        return self.status not in [SurfaceStatus.UNAVAILABLE, SurfaceStatus.ERROR]

    def supports_feature(self, feature: str) -> bool:
        """Check if surface supports a specific feature."""
        feature_map = {
            "audio_input": self.capabilities.supports_audio_input,
            "audio_output": self.capabilities.supports_audio_output,
            "stereo": self.capabilities.supports_stereo,
            "wake_detection": self.capabilities.supports_wake_detection,
            "vad": self.capabilities.supports_vad,
            "barge_in": self.capabilities.supports_barge_in,
            "playback_control": self.capabilities.supports_playback_control,
            "opus": self.capabilities.supports_opus,
            "pcm": self.capabilities.supports_pcm,
            "webrtc": self.capabilities.supports_webrtc,
        }

        return feature_map.get(feature, False)

    def get_connection_url(self) -> str | None:
        """Get connection URL for the surface."""
        if not self.connection:
            return None

        return f"{self.connection.protocol}://{self.connection.host}:{self.connection.port}"

    def validate(self) -> list[str]:
        """Validate surface configuration."""
        errors = []

        # Check required fields
        if not self.surface_id:
            errors.append("Surface ID is required")

        if not self.display_name:
            errors.append("Display name is required")

        # Check connection if provided
        if self.connection:
            if not self.connection.host:
                errors.append("Connection host is required")

            if self.connection.port <= 0 or self.connection.port > 65535:
                errors.append("Connection port must be between 1 and 65535")

            if self.connection.timeout_ms <= 0:
                errors.append("Connection timeout must be positive")

            if self.connection.retry_count < 0:
                errors.append("Retry count must be non-negative")

            if self.connection.retry_delay_ms < 0:
                errors.append("Retry delay must be non-negative")

        # Check capabilities
        if self.capabilities.max_sample_rate < self.capabilities.min_sample_rate:
            errors.append("Max sample rate must be >= min sample rate")

        if self.capabilities.min_sample_rate <= 0:
            errors.append("Min sample rate must be positive")

        return errors
