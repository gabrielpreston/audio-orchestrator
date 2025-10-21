"""
Session broker for managing voice assistant sessions.

This module implements the session broker that manages session lifecycle,
routing, and coordination between different services.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from services.common.logging import get_logger

from .policy_engine import PolicyConfig, PolicyEngine
from .session import (
    Session,
    SessionConfig,
    SessionMetadata,
    SessionRouting,
    SessionState,
    SessionStats,
    SessionType,
)


@dataclass
class BrokerConfig:
    """Session broker configuration."""

    # Session limits
    max_concurrent_sessions: int = 100
    session_timeout_ms: float = 300000.0  # 5 minutes
    cleanup_interval_ms: float = 60000.0  # 1 minute

    # Routing configuration
    default_stt_endpoint: str = "http://stt:8000"
    default_tts_endpoint: str = "http://tts:8000"
    default_orchestrator_endpoint: str = "http://orchestrator:8000"

    # Load balancing
    enable_load_balancing: bool = True
    load_balancer_endpoint: str | None = None

    # Performance settings
    enable_telemetry: bool = True
    telemetry_interval_ms: float = 10000.0  # 10 seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_concurrent_sessions": self.max_concurrent_sessions,
            "session_timeout_ms": self.session_timeout_ms,
            "cleanup_interval_ms": self.cleanup_interval_ms,
            "default_stt_endpoint": self.default_stt_endpoint,
            "default_tts_endpoint": self.default_tts_endpoint,
            "default_orchestrator_endpoint": self.default_orchestrator_endpoint,
            "enable_load_balancing": self.enable_load_balancing,
            "load_balancer_endpoint": self.load_balancer_endpoint,
            "enable_telemetry": self.enable_telemetry,
            "telemetry_interval_ms": self.telemetry_interval_ms,
        }


class SessionBroker:
    """Session broker for managing voice assistant sessions."""

    def __init__(self, config: BrokerConfig | None = None) -> None:
        self.config = config or BrokerConfig()
        self._logger = get_logger(__name__)

        # Session storage
        self._sessions: dict[str, Session] = {}
        self._session_stats = SessionStats()

        # Policy engine
        self._policy_engine = PolicyEngine()

        # Cleanup tracking
        self._last_cleanup = time.time()

        # Telemetry tracking
        self._last_telemetry = time.time()

    async def initialize(self) -> None:
        """Initialize the session broker."""
        self._logger.info("session_broker.initializing")
        # Initialization logic here
        pass

    async def cleanup(self) -> None:
        """Cleanup the session broker."""
        self._logger.info("session_broker.cleaning_up")
        # Cleanup logic here
        pass

    def end_session(self, session_id: str) -> bool:
        """End a session."""
        try:
            if session_id in self._sessions:
                del self._sessions[session_id]
                self._logger.info("session_broker.session_ended", session_id=session_id)
                return True
            return False
        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("session_broker.end_session_failed", error=str(e))
            return False

    def update_session_metadata(self, session_id: str, metadata: dict[str, Any]) -> bool:
        """Update session metadata."""
        try:
            if session_id in self._sessions:
                # Update session metadata directly
                session = self._sessions[session_id]
                for key, value in metadata.items():
                    if hasattr(session.metadata, key):
                        setattr(session.metadata, key, value)
                return True
            return False
        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("session_broker.update_metadata_failed", error=str(e))
            return False

    def get_telemetry(self) -> dict[str, Any]:
        """Get telemetry data."""
        return {
            "active_sessions": len(self._sessions),
            "total_sessions": self._session_stats.total_sessions,
            "completed_sessions": self._session_stats.completed_sessions,
            "current_time": time.time(),
        }

    def create_session(
        self,
        user_id: str,
        surface_id: str,
        session_type: SessionType = SessionType.VOICE,
        surface_metadata: dict[str, Any] | None = None,
        session_config: SessionConfig | None = None,
    ) -> Session:
        """Create a new session."""
        try:
            # Check concurrent session limit
            if len(self._sessions) >= self.config.max_concurrent_sessions:
                self._logger.warning(
                    "session_broker.max_sessions_reached",
                    current_sessions=len(self._sessions),
                    max_sessions=self.config.max_concurrent_sessions,
                )
                raise RuntimeError("Maximum concurrent sessions reached")

            # Create session metadata
            metadata = SessionMetadata(
                user_id=user_id,
                surface_id=surface_id,
                session_type=session_type,
                surface_metadata=surface_metadata or {},
            )

            # Create session routing
            routing = SessionRouting(
                stt_endpoint=self.config.default_stt_endpoint,
                tts_endpoint=self.config.default_tts_endpoint,
                orchestrator_endpoint=self.config.default_orchestrator_endpoint,
            )

            # Create session config
            config = session_config or SessionConfig()

            # Create session
            session = Session(
                session_id=metadata.correlation_id,
                metadata=metadata,
                routing=routing,
                config=config,
                state=SessionState.CREATED,
            )

            # Store session
            self._sessions[session.session_id] = session

            # Update stats
            self._session_stats.total_sessions += 1
            self._session_stats.active_sessions += 1

            self._logger.info(
                "session_broker.session_created",
                session_id=session.session_id,
                user_id=user_id,
                surface_id=surface_id,
                session_type=session_type.value,
            )

            return session

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("session_broker.session_creation_failed", error=str(e))
            raise

    def get_session(self, session_id: str) -> Session | None:
        """Get session by ID."""
        return self._sessions.get(session_id)

    def update_session_state(self, session_id: str, new_state: SessionState) -> bool:
        """Update session state."""
        session = self._sessions.get(session_id)
        if not session:
            self._logger.warning("session_broker.session_not_found", session_id=session_id)
            return False

        try:
            old_state = session.state
            session.set_state(new_state)

            # Update stats based on state change
            if new_state == SessionState.DISCONNECTED:
                self._session_stats.active_sessions -= 1
                self._session_stats.completed_sessions += 1
            elif new_state == SessionState.ERROR:
                self._session_stats.active_sessions -= 1
                self._session_stats.failed_sessions += 1

            self._logger.debug(
                "session_broker.session_state_updated",
                session_id=session_id,
                old_state=old_state.value,
                new_state=new_state.value,
            )

            return True

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("session_broker.session_state_update_failed", error=str(e))
            return False

    def update_session_activity(self, session_id: str, is_audio: bool = False) -> bool:
        """Update session activity."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        try:
            if is_audio:
                session.update_audio_activity()
            else:
                session.update_activity()

            return True

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("session_broker.session_activity_update_failed", error=str(e))
            return False

    def record_session_error(self, session_id: str, error_message: str) -> bool:
        """Record an error for a session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        try:
            session.record_error(error_message)
            self._session_stats.total_errors += 1

            return True

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("session_broker.session_error_record_failed", error=str(e))
            return False

    def get_active_sessions(self) -> list[Session]:
        """Get all active sessions."""
        return [
            session
            for session in self._sessions.values()
            if session.state
            in [
                SessionState.CONNECTED,
                SessionState.LISTENING,
                SessionState.PROCESSING,
                SessionState.RESPONDING,
            ]
        ]

    def get_session_by_user(self, user_id: str) -> list[Session]:
        """Get sessions for a specific user."""
        return [
            session for session in self._sessions.values() if session.metadata.user_id == user_id
        ]

    def get_session_by_surface(self, surface_id: str) -> list[Session]:
        """Get sessions for a specific surface."""
        return [
            session
            for session in self._sessions.values()
            if session.metadata.surface_id == surface_id
        ]

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        expired_sessions = []

        for session_id, session in self._sessions.items():
            if session.is_expired():
                expired_sessions.append(session_id)

        # Remove expired sessions
        for session_id in expired_sessions:
            session = self._sessions.pop(session_id)
            self._session_stats.active_sessions -= 1
            self._session_stats.completed_sessions += 1

            self._logger.info(
                "session_broker.session_expired",
                session_id=session_id,
                duration_ms=session.get_duration_ms(),
            )

        return len(expired_sessions)

    def cleanup_inactive_sessions(self) -> int:
        """Clean up inactive sessions."""
        inactive_sessions = []

        for session_id, session in self._sessions.items():
            # Check if session has been inactive for too long
            if time.time() - session.last_activity_time > self.config.session_timeout_ms / 1000.0:
                inactive_sessions.append(session_id)

        # Remove inactive sessions
        for session_id in inactive_sessions:
            session = self._sessions.pop(session_id)
            self._session_stats.active_sessions -= 1
            self._session_stats.completed_sessions += 1

            self._logger.info(
                "session_broker.session_inactive",
                session_id=session_id,
                inactivity_duration_ms=session.get_activity_duration_ms(),
            )

        return len(inactive_sessions)

    def perform_cleanup(self) -> dict[str, int]:
        """Perform cleanup of expired and inactive sessions."""
        try:
            expired_count = self.cleanup_expired_sessions()
            inactive_count = self.cleanup_inactive_sessions()

            self._last_cleanup = time.time()

            self._logger.debug(
                "session_broker.cleanup_completed",
                expired_sessions=expired_count,
                inactive_sessions=inactive_count,
                total_sessions=len(self._sessions),
            )

            return {
                "expired_sessions": expired_count,
                "inactive_sessions": inactive_count,
                "total_sessions": len(self._sessions),
            }

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("session_broker.cleanup_failed", error=str(e))
            return {
                "expired_sessions": 0,
                "inactive_sessions": 0,
                "total_sessions": 0,
            }

    def get_session_stats(self) -> SessionStats:
        """Get session statistics."""
        # Update error rate
        if self._session_stats.total_sessions > 0:
            self._session_stats.error_rate = (
                self._session_stats.total_errors / self._session_stats.total_sessions
            )

        return self._session_stats

    def get_broker_stats(self) -> dict[str, Any]:
        """Get broker statistics."""
        current_time = time.time()

        return {
            "broker_config": self.config.to_dict(),
            "session_stats": self.get_session_stats().to_dict(),
            "active_sessions": len(self.get_active_sessions()),
            "total_sessions": len(self._sessions),
            "last_cleanup": self._last_cleanup,
            "time_since_cleanup_ms": (current_time - self._last_cleanup) * 1000.0,
            "policy_engine_stats": self._policy_engine.get_performance_stats(),
        }

    def update_policy_config(self, policy_config: PolicyConfig) -> None:
        """Update policy engine configuration."""
        self._policy_engine.update_config(policy_config)
        self._logger.info("session_broker.policy_config_updated")

    def get_policy_engine(self) -> PolicyEngine:
        """Get the policy engine instance."""
        return self._policy_engine

    def should_cleanup(self) -> bool:
        """Check if cleanup should be performed."""
        current_time = time.time()
        return (current_time - self._last_cleanup) > (self.config.cleanup_interval_ms / 1000.0)

    def should_emit_telemetry(self) -> bool:
        """Check if telemetry should be emitted."""
        current_time = time.time()
        return (current_time - self._last_telemetry) > (self.config.telemetry_interval_ms / 1000.0)

    def emit_telemetry(self) -> dict[str, Any]:
        """Emit telemetry data."""
        if not self.config.enable_telemetry:
            return {}

        try:
            telemetry_data = {
                "timestamp": time.time(),
                "broker_stats": self.get_broker_stats(),
                "active_sessions": [
                    {
                        "session_id": session.session_id,
                        "user_id": session.metadata.user_id,
                        "surface_id": session.metadata.surface_id,
                        "state": session.state.value,
                        "duration_ms": session.get_duration_ms(),
                        "is_healthy": session.is_healthy(),
                    }
                    for session in self.get_active_sessions()
                ],
            }

            self._last_telemetry = time.time()

            active_sessions = telemetry_data.get("active_sessions", 0)
            self._logger.debug(
                "session_broker.telemetry_emitted",
                active_sessions=active_sessions,
            )

            return telemetry_data

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("session_broker.telemetry_emission_failed", error=str(e))
            return {"error": str(e)}

    def shutdown(self) -> dict[str, Any]:
        """Shutdown the session broker."""
        try:
            # Clean up all sessions
            cleanup_result = self.perform_cleanup()

            # Final stats
            final_stats = self.get_broker_stats()

            self._logger.info(
                "session_broker.shutdown",
                final_stats=final_stats,
                cleanup_result=cleanup_result,
            )

            return {
                "shutdown_time": time.time(),
                "final_stats": final_stats,
                "cleanup_result": cleanup_result,
            }

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("session_broker.shutdown_failed", error=str(e))
            return {"error": str(e)}
