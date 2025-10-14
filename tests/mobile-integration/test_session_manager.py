"""
Tests for session manager functionality.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock
from services.livekit.session_manager import SessionManager, MobileSession
from services.common.audio_contracts import (
    ControlMessage,
    MessageType,
    WakeDetectedMessage,
    VADStartSpeechMessage,
    VADEndSpeechMessage,
    BargeInRequestMessage,
    SessionStateMessage,
    RouteChangeMessage,
    PlaybackControlMessage,
    EndpointingMessage,
    ErrorMessage,
    SessionState,
    EndpointingState,
    PlaybackAction,
    AudioRoute,
    AudioInput,
)


class TestMobileSession:
    """Test MobileSession functionality."""
    
    @pytest.fixture
    def mock_room(self):
        """Create a mock LiveKit room."""
        room = Mock()
        room.name = "test-room"
        return room
    
    @pytest.fixture
    def mock_participant(self):
        """Create a mock remote participant."""
        participant = Mock()
        participant.identity = "test-user"
        participant.sid = "test-sid"
        return participant
    
    @pytest.fixture
    def session(self, mock_room, mock_participant):
        """Create a MobileSession instance for testing."""
        return MobileSession(mock_room, mock_participant, "test-123")
    
    def test_session_creation(self, session, mock_room, mock_participant):
        """Test session creation."""
        assert session.room == mock_room
        assert session.participant == mock_participant
        assert session.correlation_id == "test-123"
        assert session.state == SessionState.IDLE
        assert session.endpointing_state == EndpointingState.LISTENING
        assert session.start_time > 0
        assert session.last_activity > 0
        assert session.audio_route == AudioRoute.SPEAKER
        assert session.audio_input == AudioInput.BUILT_IN
        assert session.is_muted is False
        assert session.wake_armed is True
        assert session.last_wake_time == 0.0
        assert session.speech_start_time == 0.0
        assert session.speech_duration == 0.0
        assert session.barge_in_enabled is True
        assert session.is_responding is False
        assert session.response_paused is False
        assert session.pause_start_time == 0.0
        assert session.max_pause_duration == 10.0
        assert session.audio_frames == []
        assert session.current_transcript == ""
        assert session.transcript_history == []
        assert session.stats["frames_processed"] == 0
        assert session.stats["transcripts_processed"] == 0
        assert session.stats["barge_ins"] == 0
        assert session.stats["errors"] == 0
        assert session.stats["rtt_ms"] == 0.0
        assert session.stats["packet_loss_percent"] == 0.0
        assert session.stats["jitter_ms"] == 0.0
    
    def test_update_activity(self, session):
        """Test updating last activity timestamp."""
        original_time = session.last_activity
        time.sleep(0.01)  # Small delay
        session.update_activity()
        assert session.last_activity > original_time
    
    def test_is_expired(self, session):
        """Test session expiration check."""
        # Session should not be expired immediately
        assert not session.is_expired(30)
        
        # Mock an old session
        session.start_time = time.time() - (31 * 60)  # 31 minutes ago
        assert session.is_expired(30)
    
    def test_can_barge_in(self, session):
        """Test barge-in capability check."""
        # Should not be able to barge in when not responding
        assert not session.can_barge_in()
        
        # Should be able to barge in when responding and not paused
        session.is_responding = True
        assert session.can_barge_in()
        
        # Should not be able to barge in when paused
        session.response_paused = True
        assert not session.can_barge_in()
        
        # Should not be able to barge in when barge-in disabled
        session.response_paused = False
        session.barge_in_enabled = False
        assert not session.can_barge_in()


class TestSessionManager:
    """Test SessionManager functionality."""
    
    @pytest.fixture
    def manager(self):
        """Create a SessionManager instance for testing."""
        return SessionManager(max_sessions=10)
    
    @pytest.fixture
    def mock_room(self):
        """Create a mock LiveKit room."""
        room = Mock()
        room.name = "test-room"
        return room
    
    @pytest.fixture
    def mock_participant(self):
        """Create a mock remote participant."""
        participant = Mock()
        participant.identity = "test-user"
        participant.sid = "test-sid"
        return participant
    
    @pytest.mark.asyncio
    async def test_start_stop(self, manager):
        """Test starting and stopping the session manager."""
        await manager.start()
        assert manager._cleanup_task is not None
        
        await manager.stop()
        assert manager._cleanup_task is None
    
    @pytest.mark.asyncio
    async def test_create_session(self, manager, mock_room, mock_participant):
        """Test creating a session."""
        session = await manager.create_session(mock_room, mock_participant, "test-123")
        
        assert session is not None
        assert session.correlation_id == "test-123"
        assert "test-123" in manager._sessions
        assert "test-123" in manager._room_sessions["test-room"]
    
    @pytest.mark.asyncio
    async def test_create_session_max_limit(self, manager, mock_room, mock_participant):
        """Test creating sessions when at max limit."""
        # Fill up the session manager
        for i in range(10):
            participant = Mock()
            participant.identity = f"user-{i}"
            participant.sid = f"sid-{i}"
            await manager.create_session(mock_room, participant, f"session-{i}")
        
        # Create one more session (should remove oldest)
        participant = Mock()
        participant.identity = "user-10"
        participant.sid = "sid-10"
        session = await manager.create_session(mock_room, participant, "session-10")
        
        assert session is not None
        assert len(manager._sessions) == 10
        assert "session-0" not in manager._sessions  # Oldest should be removed
        assert "session-10" in manager._sessions
    
    @pytest.mark.asyncio
    async def test_get_session(self, manager, mock_room, mock_participant):
        """Test getting a session."""
        session = await manager.create_session(mock_room, mock_participant, "test-123")
        
        retrieved_session = await manager.get_session("test-123")
        assert retrieved_session == session
        
        # Test non-existent session
        non_existent = await manager.get_session("non-existent")
        assert non_existent is None
    
    @pytest.mark.asyncio
    async def test_remove_session(self, manager, mock_room, mock_participant):
        """Test removing a session."""
        session = await manager.create_session(mock_room, mock_participant, "test-123")
        
        result = await manager.remove_session("test-123")
        assert result is True
        assert "test-123" not in manager._sessions
        assert "test-123" not in manager._room_sessions["test-room"]
        
        # Test removing non-existent session
        result = await manager.remove_session("non-existent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_room_sessions(self, manager, mock_room, mock_participant):
        """Test getting sessions for a room."""
        # Create multiple sessions
        sessions = []
        for i in range(3):
            participant = Mock()
            participant.identity = f"user-{i}"
            participant.sid = f"sid-{i}"
            session = await manager.create_session(mock_room, participant, f"session-{i}")
            sessions.append(session)
        
        room_sessions = await manager.get_room_sessions("test-room")
        assert len(room_sessions) == 3
        assert all(s in sessions for s in room_sessions)
    
    @pytest.mark.asyncio
    async def test_handle_control_message_wake_detected(self, manager, mock_room, mock_participant):
        """Test handling wake detected message."""
        session = await manager.create_session(mock_room, mock_participant, "test-123")
        
        message = WakeDetectedMessage("test-123", 0.8)
        response = await manager.handle_control_message(session, message)
        
        assert response is not None
        assert response.message_type == MessageType.ENDPOINTING
        assert session.state == SessionState.LIVE_LISTEN
        assert session.endpointing_state == EndpointingState.LISTENING
    
    @pytest.mark.asyncio
    async def test_handle_control_message_vad_start_speech(self, manager, mock_room, mock_participant):
        """Test handling VAD start speech message."""
        session = await manager.create_session(mock_room, mock_participant, "test-123")
        
        message = VADStartSpeechMessage("test-123")
        response = await manager.handle_control_message(session, message)
        
        assert session.speech_start_time > 0
        assert session.state == SessionState.LIVE_LISTEN
        assert session.endpointing_state == EndpointingState.LISTENING
    
    @pytest.mark.asyncio
    async def test_handle_control_message_vad_end_speech(self, manager, mock_room, mock_participant):
        """Test handling VAD end speech message."""
        session = await manager.create_session(mock_room, mock_participant, "test-123")
        
        message = VADEndSpeechMessage("test-123", 1500)
        response = await manager.handle_control_message(session, message)
        
        assert session.speech_duration == 1.5
        assert session.state == SessionState.PROCESSING
        assert session.endpointing_state == EndpointingState.PROCESSING
        assert response.message_type == MessageType.ENDPOINTING
    
    @pytest.mark.asyncio
    async def test_handle_control_message_barge_in_request(self, manager, mock_room, mock_participant):
        """Test handling barge-in request message."""
        session = await manager.create_session(mock_room, mock_participant, "test-123")
        session.is_responding = True  # Enable barge-in
        
        message = BargeInRequestMessage("test-123", "user_speaking")
        response = await manager.handle_control_message(session, message)
        
        assert response is not None
        assert response.message_type == MessageType.PLAYBACK_CONTROL
        assert response.payload["action"] == PlaybackAction.PAUSE.value
        assert session.response_paused is True
        assert session.stats["barge_ins"] == 1
    
    @pytest.mark.asyncio
    async def test_handle_control_message_session_state(self, manager, mock_room, mock_participant):
        """Test handling session state message."""
        session = await manager.create_session(mock_room, mock_participant, "test-123")
        
        # Test mute action
        message = SessionStateMessage("test-123", "mute")
        response = await manager.handle_control_message(session, message)
        
        assert session.is_muted is True
        assert response is None
        
        # Test unmute action
        message = SessionStateMessage("test-123", "unmute")
        response = await manager.handle_control_message(session, message)
        
        assert session.is_muted is False
        
        # Test leave action
        message = SessionStateMessage("test-123", "leave")
        response = await manager.handle_control_message(session, message)
        
        assert session.state == SessionState.TEARDOWN
        assert response is None
    
    @pytest.mark.asyncio
    async def test_handle_control_message_route_change(self, manager, mock_room, mock_participant):
        """Test handling route change message."""
        session = await manager.create_session(mock_room, mock_participant, "test-123")
        
        message = RouteChangeMessage("test-123", "earpiece", "bluetooth")
        response = await manager.handle_control_message(session, message)
        
        assert session.audio_route == AudioRoute.EARPIECE
        assert session.audio_input == AudioInput.BLUETOOTH
        assert response is None
    
    @pytest.mark.asyncio
    async def test_handle_control_message_unknown_type(self, manager, mock_room, mock_participant):
        """Test handling unknown message type."""
        session = await manager.create_session(mock_room, mock_participant, "test-123")
        
        # Create a message with unknown type
        message = ControlMessage(
            message_type=MessageType.ERROR,  # This is not a client->agent message
            timestamp=time.time(),
            correlation_id="test-123",
            payload={}
        )
        
        response = await manager.handle_control_message(session, message)
        
        assert response is None
    
    @pytest.mark.asyncio
    async def test_handle_control_message_error(self, manager, mock_room, mock_participant):
        """Test handling message processing error."""
        session = await manager.create_session(mock_room, mock_participant, "test-123")
        
        # Mock a message that will cause an error
        message = Mock()
        message.message_type = Mock()
        message.message_type.value = "invalid_type"
        message.correlation_id = "test-123"
        message.payload = {}
        
        response = await manager.handle_control_message(session, message)
        
        assert response is not None
        assert response.message_type == MessageType.ERROR
        assert response.payload["code"] == "MESSAGE_HANDLING_ERROR"
        assert session.stats["errors"] == 1
    
    @pytest.mark.asyncio
    async def test_cleanup_session(self, manager, mock_room, mock_participant):
        """Test cleaning up a session."""
        session = await manager.create_session(mock_room, mock_participant, "test-123")
        
        await manager._cleanup_session(session)
        
        assert session.state == SessionState.TEARDOWN
    
    @pytest.mark.asyncio
    async def test_cleanup_loop(self, manager):
        """Test the cleanup loop."""
        # Start the manager
        await manager.start()
        
        # Create some sessions
        for i in range(3):
            room = Mock()
            room.name = f"room-{i}"
            participant = Mock()
            participant.identity = f"user-{i}"
            participant.sid = f"sid-{i}"
            session = await manager.create_session(room, participant, f"session-{i}")
            
            # Make one session expired
            if i == 0:
                session.start_time = time.time() - (31 * 60)  # 31 minutes ago
        
        # Wait for cleanup loop to run
        await asyncio.sleep(0.1)
        
        # Stop the manager
        await manager.stop()
        
        # Check that expired session was removed
        assert "session-0" not in manager._sessions
        assert "session-1" in manager._sessions
        assert "session-2" in manager._sessions


if __name__ == "__main__":
    pytest.main([__file__])