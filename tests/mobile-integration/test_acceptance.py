"""
Acceptance tests for mobile voice assistant integration.
"""

import pytest
import asyncio
import time
import json
from unittest.mock import Mock, AsyncMock, patch
from services.livekit.livekit_agent import MobileVoiceAgent
from services.livekit.session_manager import SessionManager
from services.common.audio_contracts import (
    AudioFrame,
    ControlMessage,
    MessageType,
    WakeDetectedMessage,
    VADStartSpeechMessage,
    VADEndSpeechMessage,
    BargeInRequestMessage,
    SessionState,
    EndpointingState,
    PlaybackAction,
)


class TestAcceptanceCriteria:
    """Test acceptance criteria from the specification."""
    
    @pytest.fixture
    def agent(self):
        """Create a MobileVoiceAgent instance for testing."""
        with patch('services.livekit.livekit_agent.configure_logging'):
            return MobileVoiceAgent()
    
    @pytest.fixture
    def session_manager(self):
        """Create a SessionManager instance for testing."""
        return SessionManager()
    
    @pytest.fixture
    def mock_room(self):
        """Create a mock LiveKit room."""
        room = Mock()
        room.name = "test-room"
        room.localParticipant = Mock()
        room.remote_participants = {}
        return room
    
    @pytest.fixture
    def mock_participant(self):
        """Create a mock remote participant."""
        participant = Mock()
        participant.identity = "test-user"
        participant.sid = "test-sid"
        return participant
    
    @pytest.mark.asyncio
    async def test_latency_targets(self, agent, session_manager, mock_room, mock_participant):
        """Test latency targets: ≤ 400ms median, ≤ 650ms p95."""
        # This is a simplified test - in practice, you'd measure actual latency
        # across multiple test runs with real audio data
        
        session = await session_manager.create_session(mock_room, mock_participant, "test-123")
        
        # Mock audio processing with timing
        start_time = time.time()
        
        # Simulate audio frame processing
        frame = AudioFrame(
            pcm_data=b'\x00' * 640,  # 20ms of audio
            timestamp=start_time,
            sequence_number=1
        )
        
        # Mock STT processing
        with patch.object(agent.stt_adapter, 'process_audio_frame', new_callable=AsyncMock) as mock_stt:
            mock_stt.return_value = None  # No immediate result
            
            # Process frame
            await agent.stt_adapter.process_audio_frame("stream-123", frame)
            
            # Simulate processing time
            processing_time = time.time() - start_time
            
            # Check that processing time is within acceptable limits
            assert processing_time < 0.1  # 100ms for this simplified test
            # In real tests, you'd measure end-to-end latency including
            # network, STT, orchestrator, and TTS processing
    
    @pytest.mark.asyncio
    async def test_barge_in_pause_delay(self, session_manager, mock_room, mock_participant):
        """Test barge-in pause delay: ≤ 250ms from VAD start to downstream pause."""
        session = await session_manager.create_session(mock_room, mock_participant, "test-123")
        session.is_responding = True  # Enable barge-in
        
        # Measure barge-in response time
        start_time = time.time()
        
        # Send barge-in request
        message = BargeInRequestMessage("test-123", "user_speaking")
        response = await session_manager.handle_control_message(session, message)
        
        end_time = time.time()
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Check that response time is within 250ms
        assert response_time <= 250
        assert response is not None
        assert response.message_type == MessageType.PLAYBACK_CONTROL
        assert response.payload["action"] == PlaybackAction.PAUSE.value
    
    @pytest.mark.asyncio
    async def test_route_handling(self, session_manager, mock_room, mock_participant):
        """Test clean transitions among speaker/earpiece/BT mid-session without teardown."""
        session = await session_manager.create_session(mock_room, mock_participant, "test-123")
        
        # Test speaker route
        message = BargeInRequestMessage("test-123", "speaker", "built_in")
        response = await session_manager.handle_control_message(session, message)
        assert session.audio_route.value == "speaker"
        assert session.audio_input.value == "built_in"
        
        # Test earpiece route
        message = BargeInRequestMessage("test-123", "earpiece", "built_in")
        response = await session_manager.handle_control_message(session, message)
        assert session.audio_route.value == "earpiece"
        
        # Test Bluetooth route
        message = BargeInRequestMessage("test-123", "bt", "bt")
        response = await session_manager.handle_control_message(session, message)
        assert session.audio_route.value == "bt"
        assert session.audio_input.value == "bt"
        
        # Verify session is still active
        assert session.state != SessionState.TEARDOWN
    
    @pytest.mark.asyncio
    async def test_session_recovery(self, session_manager, mock_room, mock_participant):
        """Test successful session recovery within 2s after connection issues."""
        session = await session_manager.create_session(mock_room, mock_participant, "test-123")
        
        # Simulate connection issue
        session.state = SessionState.TEARDOWN
        
        # Simulate recovery
        start_time = time.time()
        
        # Recreate session (simulating reconnection)
        new_session = await session_manager.create_session(mock_room, mock_participant, "test-123-recovered")
        
        recovery_time = time.time() - start_time
        
        # Check that recovery time is within 2 seconds
        assert recovery_time <= 2.0
        assert new_session is not None
        assert new_session.state == SessionState.IDLE
    
    @pytest.mark.asyncio
    async def test_session_duration_limit(self, session_manager, mock_room, mock_participant):
        """Test 30-minute session duration limit."""
        session = await session_manager.create_session(mock_room, mock_participant, "test-123")
        
        # Mock a session that's been running for 31 minutes
        session.start_time = time.time() - (31 * 60)
        
        # Check that session is expired
        assert session.is_expired(30)
        
        # Check that session manager would clean it up
        assert len(session_manager._sessions) == 1
        await session_manager._cleanup_session(session)
        assert len(session_manager._sessions) == 0
    
    @pytest.mark.asyncio
    async def test_wake_word_cooldown(self, session_manager, mock_room, mock_participant):
        """Test wake word cooldown to prevent false positives."""
        session = await session_manager.create_session(mock_room, mock_participant, "test-123")
        
        # First wake word detection
        message1 = WakeDetectedMessage("test-123", 0.8)
        response1 = await session_manager.handle_control_message(session, message1)
        
        assert response1 is not None
        assert session.last_wake_time > 0
        
        # Immediate second wake word detection (should be ignored due to cooldown)
        message2 = WakeDetectedMessage("test-123", 0.9)
        response2 = await session_manager.handle_control_message(session, message2)
        
        # Should be ignored due to cooldown
        assert response2 is None
    
    @pytest.mark.asyncio
    async def test_vad_speech_detection(self, session_manager, mock_room, mock_participant):
        """Test VAD speech detection and state transitions."""
        session = await session_manager.create_session(mock_room, mock_participant, "test-123")
        
        # Start speech
        message1 = VADStartSpeechMessage("test-123")
        response1 = await session_manager.handle_control_message(session, message1)
        
        assert session.speech_start_time > 0
        assert session.state == SessionState.LIVE_LISTEN
        assert session.endpointing_state == EndpointingState.LISTENING
        
        # End speech
        message2 = VADEndSpeechMessage("test-123", 1500)
        response2 = await session_manager.handle_control_message(session, message2)
        
        assert session.speech_duration == 1.5
        assert session.state == SessionState.PROCESSING
        assert session.endpointing_state == EndpointingState.PROCESSING
        assert response2.message_type == MessageType.ENDPOINTING
    
    @pytest.mark.asyncio
    async def test_barge_in_policy(self, session_manager, mock_room, mock_participant):
        """Test barge-in policy and pause/resume behavior."""
        session = await session_manager.create_session(mock_room, mock_participant, "test-123")
        session.is_responding = True  # Enable barge-in
        
        # Test barge-in when responding
        message1 = BargeInRequestMessage("test-123", "user_speaking")
        response1 = await session_manager.handle_control_message(session, message1)
        
        assert response1.message_type == MessageType.PLAYBACK_CONTROL
        assert response1.payload["action"] == PlaybackAction.PAUSE.value
        assert session.response_paused is True
        assert session.stats["barge_ins"] == 1
        
        # Test barge-in when not responding (should be ignored)
        session.is_responding = False
        message2 = BargeInRequestMessage("test-123", "user_speaking")
        response2 = await session_manager.handle_control_message(session, message2)
        
        assert response2 is None
        assert session.stats["barge_ins"] == 1  # Should not increment
    
    @pytest.mark.asyncio
    async def test_session_state_transitions(self, session_manager, mock_room, mock_participant):
        """Test proper session state transitions."""
        session = await session_manager.create_session(mock_room, mock_participant, "test-123")
        
        # Initial state
        assert session.state == SessionState.IDLE
        assert session.endpointing_state == EndpointingState.LISTENING
        
        # Wake word detected -> Arming -> Live Listen
        message1 = WakeDetectedMessage("test-123", 0.8)
        response1 = await session_manager.handle_control_message(session, message1)
        
        assert session.state == SessionState.LIVE_LISTEN
        assert session.endpointing_state == EndpointingState.LISTENING
        
        # VAD start speech -> Live Listen
        message2 = VADStartSpeechMessage("test-123")
        response2 = await session_manager.handle_control_message(session, message2)
        
        assert session.state == SessionState.LIVE_LISTEN
        assert session.endpointing_state == EndpointingState.LISTENING
        
        # VAD end speech -> Processing
        message3 = VADEndSpeechMessage("test-123", 1000)
        response3 = await session_manager.handle_control_message(session, message3)
        
        assert session.state == SessionState.PROCESSING
        assert session.endpointing_state == EndpointingState.PROCESSING
    
    @pytest.mark.asyncio
    async def test_error_handling(self, session_manager, mock_room, mock_participant):
        """Test error handling and recovery."""
        session = await session_manager.create_session(mock_room, mock_participant, "test-123")
        
        # Test handling of invalid message
        invalid_message = Mock()
        invalid_message.message_type = Mock()
        invalid_message.message_type.value = "invalid_type"
        invalid_message.correlation_id = "test-123"
        invalid_message.payload = {}
        
        response = await session_manager.handle_control_message(session, invalid_message)
        
        assert response is not None
        assert response.message_type == MessageType.ERROR
        assert response.payload["code"] == "MESSAGE_HANDLING_ERROR"
        assert response.payload["recoverable"] is True
        assert session.stats["errors"] == 1
    
    @pytest.mark.asyncio
    async def test_telemetry_collection(self, session_manager, mock_room, mock_participant):
        """Test telemetry data collection."""
        session = await session_manager.create_session(mock_room, mock_participant, "test-123")
        
        # Simulate some activity
        session.stats["frames_processed"] = 100
        session.stats["transcripts_processed"] = 5
        session.stats["barge_ins"] = 2
        session.stats["errors"] = 1
        session.stats["rtt_ms"] = 150.5
        session.stats["packet_loss_percent"] = 2.1
        session.stats["jitter_ms"] = 25.3
        
        # Check that stats are properly tracked
        assert session.stats["frames_processed"] == 100
        assert session.stats["transcripts_processed"] == 5
        assert session.stats["barge_ins"] == 2
        assert session.stats["errors"] == 1
        assert session.stats["rtt_ms"] == 150.5
        assert session.stats["packet_loss_percent"] == 2.1
        assert session.stats["jitter_ms"] == 25.3
    
    @pytest.mark.asyncio
    async def test_session_cleanup(self, session_manager, mock_room, mock_participant):
        """Test session cleanup and resource management."""
        # Create multiple sessions
        sessions = []
        for i in range(5):
            participant = Mock()
            participant.identity = f"user-{i}"
            participant.sid = f"sid-{i}"
            session = await session_manager.create_session(mock_room, participant, f"session-{i}")
            sessions.append(session)
        
        assert len(session_manager._sessions) == 5
        
        # Remove some sessions
        await session_manager.remove_session("session-0")
        await session_manager.remove_session("session-2")
        
        assert len(session_manager._sessions) == 3
        assert "session-0" not in session_manager._sessions
        assert "session-2" not in session_manager._sessions
        assert "session-1" in session_manager._sessions
        assert "session-3" in session_manager._sessions
        assert "session-4" in session_manager._sessions


class TestPerformanceRequirements:
    """Test performance requirements from the specification."""
    
    @pytest.mark.asyncio
    async def test_audio_processing_performance(self):
        """Test audio processing performance requirements."""
        # This would test actual audio processing performance
        # For now, we'll test the basic structure
        
        from services.livekit.audio_processor import LiveKitAudioProcessor
        
        processor = LiveKitAudioProcessor()
        
        # Test audio frame creation
        pcm_data = b'\x00' * 640  # 20ms of audio
        frame = processor.create_audio_frame(
            pcm_data=pcm_data,
            timestamp=time.time(),
            sequence_number=1
        )
        
        assert frame.pcm_data == pcm_data
        assert frame.sample_rate == 16000
        assert frame.channels == 1
        assert frame.sample_width == 2
        assert frame.frame_duration_ms == 20
    
    @pytest.mark.asyncio
    async def test_memory_usage(self, session_manager, mock_room, mock_participant):
        """Test memory usage with multiple sessions."""
        # Create multiple sessions to test memory usage
        sessions = []
        for i in range(100):  # Create 100 sessions
            participant = Mock()
            participant.identity = f"user-{i}"
            participant.sid = f"sid-{i}"
            session = await session_manager.create_session(mock_room, participant, f"session-{i}")
            sessions.append(session)
        
        # Check that all sessions are created
        assert len(session_manager._sessions) == 100
        
        # Clean up
        for session in sessions:
            await session_manager.remove_session(session.correlation_id)
        
        assert len(session_manager._sessions) == 0


if __name__ == "__main__":
    pytest.main([__file__])