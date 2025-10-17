"""
Session management for voice assistant interactions.

This module defines the Session data structure and related functionality
for managing voice assistant sessions across different surfaces.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


class SessionState(Enum):
    """Session state enumeration."""

    CREATED = "created"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class SessionType(Enum):
    """Session type enumeration."""

    VOICE = "voice"
    TEXT = "text"
    MIXED = "mixed"


@dataclass
class SessionMetadata:
    """Session metadata information."""

    user_id: str
    surface_id: str
    session_type: SessionType
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Surface-specific metadata
    surface_metadata: dict[str, Any] = field(default_factory=dict)

    # Performance tracking
    total_audio_duration_ms: float = 0.0
    total_processing_time_ms: float = 0.0
    total_response_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "surface_id": self.surface_id,
            "session_type": self.session_type.value,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "correlation_id": self.correlation_id,
            "surface_metadata": self.surface_metadata,
            "total_audio_duration_ms": self.total_audio_duration_ms,
            "total_processing_time_ms": self.total_processing_time_ms,
            "total_response_time_ms": self.total_response_time_ms,
        }


@dataclass
class SessionRouting:
    """Session routing information."""

    # Service endpoints
    stt_endpoint: str
    tts_endpoint: str
    orchestrator_endpoint: str

    # Routing configuration
    priority: int = 0  # Higher priority = more important
    timeout_ms: float = 30000.0  # 30 seconds default timeout

    # Load balancing
    load_balancer: str | None = None
    region: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stt_endpoint": self.stt_endpoint,
            "tts_endpoint": self.tts_endpoint,
            "orchestrator_endpoint": self.orchestrator_endpoint,
            "priority": self.priority,
            "timeout_ms": self.timeout_ms,
            "load_balancer": self.load_balancer,
            "region": self.region,
        }


@dataclass
class SessionConfig:
    """Session configuration."""

    # Session limits
    max_duration_ms: float = 300000.0  # 5 minutes
    max_audio_duration_ms: float = 60000.0  # 1 minute
    max_silence_ms: float = 10000.0  # 10 seconds

    # Quality settings
    audio_quality: str = "high"  # low, medium, high
    response_quality: str = "balanced"  # fast, balanced, accurate

    # Feature flags
    enable_barge_in: bool = True
    enable_wake_detection: bool = True
    enable_telemetry: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_duration_ms": self.max_duration_ms,
            "max_audio_duration_ms": self.max_audio_duration_ms,
            "max_silence_ms": self.max_silence_ms,
            "audio_quality": self.audio_quality,
            "response_quality": self.response_quality,
            "enable_barge_in": self.enable_barge_in,
            "enable_wake_detection": self.enable_wake_detection,
            "enable_telemetry": self.enable_telemetry,
        }


@dataclass
class Session:
    """Voice assistant session."""

    session_id: str
    metadata: SessionMetadata
    routing: SessionRouting
    config: SessionConfig
    state: SessionState = SessionState.CREATED

    # Session tracking
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # Activity tracking
    last_audio_time: float = field(default_factory=time.time)
    last_activity_time: float = field(default_factory=time.time)

    # Error tracking
    error_count: int = 0
    last_error: str | None = None
    last_error_time: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "metadata": self.metadata.to_dict(),
            "routing": self.routing.to_dict(),
            "config": self.config.to_dict(),
            "state": self.state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_audio_time": self.last_audio_time,
            "last_activity_time": self.last_activity_time,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time,
        }

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity_time = time.time()
        self.metadata.last_activity = self.last_activity_time
        self.updated_at = self.last_activity_time

    def update_audio_activity(self) -> None:
        """Update audio activity timestamp."""
        self.last_audio_time = time.time()
        self.update_activity()

    def set_state(self, new_state: SessionState) -> None:
        """Set session state."""
        old_state = self.state
        self.state = new_state
        self.updated_at = time.time()

        logger.debug(
            "session.state_changed",
            session_id=self.session_id,
            old_state=old_state.value,
            new_state=new_state.value,
        )

    def record_error(self, error_message: str) -> None:
        """Record an error."""
        self.error_count += 1
        self.last_error = error_message
        self.last_error_time = time.time()
        self.updated_at = time.time()

        logger.warning(
            "session.error_recorded",
            session_id=self.session_id,
            error_message=error_message,
            error_count=self.error_count,
        )

    def is_expired(self) -> bool:
        """Check if session has expired."""
        current_time = time.time()

        # Check max duration
        if current_time - self.created_at > self.config.max_duration_ms / 1000.0:
            return True

        # Check max silence
        if current_time - self.last_audio_time > self.config.max_silence_ms / 1000.0:
            return True

        return False

    def is_healthy(self) -> bool:
        """Check if session is healthy."""
        # Check error count
        if self.error_count > 10:  # Arbitrary threshold
            return False

        # Check if expired
        if self.is_expired():
            return False

        # Check state
        if self.state == SessionState.ERROR:
            return False

        return True

    def get_duration_ms(self) -> float:
        """Get session duration in milliseconds."""
        return (time.time() - self.created_at) * 1000.0

    def get_silence_duration_ms(self) -> float:
        """Get silence duration in milliseconds."""
        return (time.time() - self.last_audio_time) * 1000.0

    def get_activity_duration_ms(self) -> float:
        """Get time since last activity in milliseconds."""
        return (time.time() - self.last_activity_time) * 1000.0


@dataclass
class SessionStats:
    """Session statistics."""

    total_sessions: int = 0
    active_sessions: int = 0
    completed_sessions: int = 0
    failed_sessions: int = 0

    # Performance metrics
    avg_duration_ms: float = 0.0
    avg_processing_time_ms: float = 0.0
    avg_response_time_ms: float = 0.0

    # Error metrics
    total_errors: int = 0
    error_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_sessions": self.total_sessions,
            "active_sessions": self.active_sessions,
            "completed_sessions": self.completed_sessions,
            "failed_sessions": self.failed_sessions,
            "avg_duration_ms": self.avg_duration_ms,
            "avg_processing_time_ms": self.avg_processing_time_ms,
            "avg_response_time_ms": self.avg_response_time_ms,
            "total_errors": self.total_errors,
            "error_rate": self.error_rate,
        }
