"""
Tests for session broker functionality.

This module validates that the session broker correctly manages
session lifecycle, routing, and coordination.
"""

import time

import pytest

from services.orchestrator.policy_config import PolicyConfig
from services.orchestrator.session import SessionConfig, SessionState, SessionType
from services.orchestrator.session_broker import BrokerConfig, SessionBroker


class TestBrokerConfig:
    """Test BrokerConfig data structure."""

    def test_broker_config_creation(self):
        """Test creating BrokerConfig with defaults."""
        config = BrokerConfig()

        assert config.max_concurrent_sessions == 100
        assert config.session_timeout_ms == 300000.0
        assert config.cleanup_interval_ms == 60000.0
        assert config.enable_telemetry is True

    def test_broker_config_to_dict(self):
        """Test converting BrokerConfig to dictionary."""
        config = BrokerConfig()
        data = config.to_dict()

        assert "max_concurrent_sessions" in data
        assert "session_timeout_ms" in data
        assert "cleanup_interval_ms" in data
        assert "enable_telemetry" in data


class TestSessionBroker:
    """Test SessionBroker functionality."""

    def test_session_broker_creation(self):
        """Test creating SessionBroker with default config."""
        broker = SessionBroker()

        assert broker.config is not None
        assert len(broker._sessions) == 0
        assert broker._session_stats.total_sessions == 0

    def test_session_broker_creation_custom_config(self):
        """Test creating SessionBroker with custom config."""
        config = BrokerConfig()
        config.max_concurrent_sessions = 50

        broker = SessionBroker(config)

        assert broker.config.max_concurrent_sessions == 50

    def test_create_session(self):
        """Test creating a new session."""
        broker = SessionBroker()

        session = broker.create_session(
            user_id="user123",
            surface_id="discord",
            session_type=SessionType.VOICE,
        )

        assert session is not None
        assert session.metadata.user_id == "user123"
        assert session.metadata.surface_id == "discord"
        assert session.metadata.session_type == SessionType.VOICE
        assert session.state == SessionState.CREATED
        assert session.session_id in broker._sessions
        assert broker._session_stats.total_sessions == 1
        assert broker._session_stats.active_sessions == 1

    def test_create_session_with_metadata(self):
        """Test creating session with surface metadata."""
        broker = SessionBroker()

        surface_metadata = {"channel_id": "123456", "guild_id": "789012"}

        session = broker.create_session(
            user_id="user123",
            surface_id="discord",
            surface_metadata=surface_metadata,
        )

        assert session.metadata.surface_metadata == surface_metadata

    def test_create_session_with_custom_config(self):
        """Test creating session with custom session config."""
        broker = SessionBroker()

        session_config = SessionConfig()
        session_config.max_duration_ms = 600000.0  # 10 minutes

        session = broker.create_session(
            user_id="user123",
            surface_id="discord",
            session_config=session_config,
        )

        assert session.config.max_duration_ms == 600000.0

    def test_create_session_max_concurrent(self):
        """Test creating session when max concurrent reached."""
        config = BrokerConfig()
        config.max_concurrent_sessions = 1

        broker = SessionBroker(config)

        # Create first session
        session1 = broker.create_session("user1", "discord")
        assert session1 is not None

        # Try to create second session (should fail)
        with pytest.raises(RuntimeError, match="Maximum concurrent sessions reached"):
            broker.create_session("user2", "discord")

    def test_get_session(self):
        """Test getting session by ID."""
        broker = SessionBroker()

        session = broker.create_session("user123", "discord")
        session_id = session.session_id

        retrieved_session = broker.get_session(session_id)
        assert retrieved_session is not None
        assert retrieved_session.session_id == session_id

        # Test non-existent session
        non_existent = broker.get_session("non-existent")
        assert non_existent is None

    def test_update_session_state(self):
        """Test updating session state."""
        broker = SessionBroker()

        session = broker.create_session("user123", "discord")
        session_id = session.session_id

        # Update state
        success = broker.update_session_state(session_id, SessionState.CONNECTED)
        assert success is True

        # Verify state change
        updated_session = broker.get_session(session_id)
        assert updated_session.state == SessionState.CONNECTED

        # Test with non-existent session
        success = broker.update_session_state("non-existent", SessionState.CONNECTED)
        assert success is False

    def test_update_session_activity(self):
        """Test updating session activity."""
        broker = SessionBroker()

        session = broker.create_session("user123", "discord")
        session_id = session.session_id

        # Update activity
        success = broker.update_session_activity(session_id, is_audio=True)
        assert success is True

        # Verify activity update
        updated_session = broker.get_session(session_id)
        assert updated_session.last_audio_time > 0

        # Test with non-existent session
        success = broker.update_session_activity("non-existent")
        assert success is False

    def test_record_session_error(self):
        """Test recording session error."""
        broker = SessionBroker()

        session = broker.create_session("user123", "discord")
        session_id = session.session_id

        # Record error
        success = broker.record_session_error(session_id, "Test error")
        assert success is True

        # Verify error recording
        updated_session = broker.get_session(session_id)
        assert updated_session.error_count == 1
        assert updated_session.last_error == "Test error"
        assert broker._session_stats.total_errors == 1

        # Test with non-existent session
        success = broker.record_session_error("non-existent", "Test error")
        assert success is False

    def test_get_active_sessions(self):
        """Test getting active sessions."""
        broker = SessionBroker()

        # Create sessions with different states
        session1 = broker.create_session("user1", "discord")
        session2 = broker.create_session("user2", "discord")
        session3 = broker.create_session("user3", "discord")

        # Update states
        broker.update_session_state(session1.session_id, SessionState.CONNECTED)
        broker.update_session_state(session2.session_id, SessionState.LISTENING)
        broker.update_session_state(session3.session_id, SessionState.DISCONNECTED)

        # Get active sessions
        active_sessions = broker.get_active_sessions()

        # Should include CONNECTED and LISTENING, but not DISCONNECTED
        assert len(active_sessions) == 2
        session_ids = [s.session_id for s in active_sessions]
        assert session1.session_id in session_ids
        assert session2.session_id in session_ids
        assert session3.session_id not in session_ids

    def test_get_session_by_user(self):
        """Test getting sessions by user ID."""
        broker = SessionBroker()

        # Create sessions for different users
        session1 = broker.create_session("user1", "discord")
        session2 = broker.create_session("user2", "discord")
        session3 = broker.create_session("user1", "discord")

        # Get sessions for user1
        user1_sessions = broker.get_session_by_user("user1")
        assert len(user1_sessions) == 2
        assert session1.session_id in [s.session_id for s in user1_sessions]
        assert session3.session_id in [s.session_id for s in user1_sessions]

        # Get sessions for user2
        user2_sessions = broker.get_session_by_user("user2")
        assert len(user2_sessions) == 1
        assert session2.session_id in [s.session_id for s in user2_sessions]

    def test_get_session_by_surface(self):
        """Test getting sessions by surface ID."""
        broker = SessionBroker()

        # Create sessions for different surfaces
        session1 = broker.create_session("user1", "discord")
        session2 = broker.create_session("user2", "web")
        session3 = broker.create_session("user3", "discord")

        # Get sessions for discord surface
        discord_sessions = broker.get_session_by_surface("discord")
        assert len(discord_sessions) == 2
        assert session1.session_id in [s.session_id for s in discord_sessions]
        assert session3.session_id in [s.session_id for s in discord_sessions]

        # Get sessions for web surface
        web_sessions = broker.get_session_by_surface("web")
        assert len(web_sessions) == 1
        assert session2.session_id in [s.session_id for s in web_sessions]

    def test_cleanup_expired_sessions(self):
        """Test cleaning up expired sessions."""
        broker = SessionBroker()

        # Create session with short expiration
        session_config = SessionConfig()
        session_config.max_duration_ms = 100.0  # 100ms

        session = broker.create_session(
            "user123", "discord", session_config=session_config
        )
        session_id = session.session_id

        # Wait for expiration
        time.sleep(0.2)

        # Cleanup expired sessions
        expired_count = broker.cleanup_expired_sessions()

        assert expired_count == 1
        assert session_id not in broker._sessions
        assert broker._session_stats.active_sessions == 0
        assert broker._session_stats.completed_sessions == 1

    def test_cleanup_inactive_sessions(self):
        """Test cleaning up inactive sessions."""
        config = BrokerConfig()
        config.session_timeout_ms = 100.0  # 100ms

        broker = SessionBroker(config)

        session = broker.create_session("user123", "discord")
        session_id = session.session_id

        # Wait for inactivity timeout
        time.sleep(0.2)

        # Cleanup inactive sessions
        inactive_count = broker.cleanup_inactive_sessions()

        assert inactive_count == 1
        assert session_id not in broker._sessions
        assert broker._session_stats.active_sessions == 0
        assert broker._session_stats.completed_sessions == 1

    def test_perform_cleanup(self):
        """Test performing cleanup."""
        config = BrokerConfig()
        config.session_timeout_ms = 100.0  # 100ms

        broker = SessionBroker(config)

        # Create session
        broker.create_session("user123", "discord")

        # Wait for inactivity timeout
        time.sleep(0.2)

        # Perform cleanup
        cleanup_result = broker.perform_cleanup()

        assert "expired_sessions" in cleanup_result
        assert "inactive_sessions" in cleanup_result
        assert "total_sessions" in cleanup_result
        assert cleanup_result["inactive_sessions"] == 1
        assert cleanup_result["total_sessions"] == 0

    def test_get_session_stats(self):
        """Test getting session statistics."""
        broker = SessionBroker()

        # Create some sessions
        session1 = broker.create_session("user1", "discord")
        session2 = broker.create_session("user2", "discord")

        # Update states
        broker.update_session_state(session1.session_id, SessionState.CONNECTED)
        broker.update_session_state(session2.session_id, SessionState.DISCONNECTED)

        # Get stats
        stats = broker.get_session_stats()

        assert stats.total_sessions == 2
        assert stats.active_sessions == 1
        assert stats.completed_sessions == 1
        assert stats.failed_sessions == 0

    def test_get_broker_stats(self):
        """Test getting broker statistics."""
        broker = SessionBroker()

        # Create session
        broker.create_session("user123", "discord")

        # Get broker stats
        stats = broker.get_broker_stats()

        assert "broker_config" in stats
        assert "session_stats" in stats
        assert "active_sessions" in stats
        assert "total_sessions" in stats
        assert "last_cleanup" in stats
        assert "time_since_cleanup_ms" in stats
        assert "policy_engine_stats" in stats

    def test_update_policy_config(self):
        """Test updating policy configuration."""
        broker = SessionBroker()

        policy_config = PolicyConfig()
        policy_config.vad.enabled = False

        broker.update_policy_config(policy_config)

        # Verify policy engine was updated
        policy_engine = broker.get_policy_engine()
        assert policy_engine.config.vad.enabled is False

    def test_should_cleanup(self):
        """Test cleanup timing check."""
        config = BrokerConfig()
        config.cleanup_interval_ms = 100.0  # 100ms

        broker = SessionBroker(config)

        # Initially should not need cleanup
        assert broker.should_cleanup() is False

        # Wait for cleanup interval
        time.sleep(0.2)

        # Now should need cleanup
        assert broker.should_cleanup() is True

    def test_should_emit_telemetry(self):
        """Test telemetry timing check."""
        config = BrokerConfig()
        config.telemetry_interval_ms = 100.0  # 100ms

        broker = SessionBroker(config)

        # Initially should not need telemetry
        assert broker.should_emit_telemetry() is False

        # Wait for telemetry interval
        time.sleep(0.2)

        # Now should need telemetry
        assert broker.should_emit_telemetry() is True

    def test_emit_telemetry(self):
        """Test emitting telemetry data."""
        broker = SessionBroker()

        # Create session
        broker.create_session("user123", "discord")

        # Emit telemetry
        telemetry = broker.emit_telemetry()

        assert "timestamp" in telemetry
        assert "broker_stats" in telemetry
        assert "active_sessions" in telemetry
        assert len(telemetry["active_sessions"]) == 1

    def test_emit_telemetry_disabled(self):
        """Test telemetry when disabled."""
        config = BrokerConfig()
        config.enable_telemetry = False

        broker = SessionBroker(config)

        # Emit telemetry
        telemetry = broker.emit_telemetry()

        assert telemetry == {}

    def test_shutdown(self):
        """Test broker shutdown."""
        broker = SessionBroker()

        # Create session
        broker.create_session("user123", "discord")

        # Shutdown
        shutdown_result = broker.shutdown()

        assert "shutdown_time" in shutdown_result
        assert "final_stats" in shutdown_result
        assert "cleanup_result" in shutdown_result
