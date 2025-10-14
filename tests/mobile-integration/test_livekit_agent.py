"""
Tests for LiveKit agent service.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from services.livekit.livekit_agent import MobileVoiceAgent
from services.livekit.config import LiveKitConfig
from services.common.audio_contracts import AudioFrame, ControlMessage, MessageType


class TestMobileVoiceAgent:
    """Test MobileVoiceAgent functionality."""
    
    @pytest.fixture
    def agent(self):
        """Create a MobileVoiceAgent instance for testing."""
        with patch('services.livekit.livekit_agent.configure_logging'):
            return MobileVoiceAgent()
    
    @pytest.fixture
    def mock_room(self):
        """Create a mock LiveKit room."""
        room = Mock()
        room.name = "test-room"
        room.localParticipant = Mock()
        room.remote_participants = {}
        room.connect = AsyncMock()
        room.disconnect = AsyncMock()
        return room
    
    @pytest.fixture
    def mock_participant(self):
        """Create a mock remote participant."""
        participant = Mock()
        participant.identity = "test-user"
        participant.sid = "test-sid"
        return participant
    
    def test_agent_initialization(self, agent):
        """Test agent initialization."""
        assert agent is not None
        assert agent.audio_processor is not None
        assert agent.stt_adapter is not None
        assert agent.tts_adapter is not None
        assert agent.session_manager is not None
        assert agent.is_running is False
        assert agent.room is None
    
    @pytest.mark.asyncio
    async def test_start(self, agent):
        """Test agent start."""
        with patch.object(agent.session_manager, 'start', new_callable=AsyncMock) as mock_start:
            await agent.start()
            
            assert agent.is_running is True
            mock_start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop(self, agent):
        """Test agent stop."""
        agent.is_running = True
        agent.room = Mock()
        agent.room.disconnect = AsyncMock()
        
        with patch.object(agent.session_manager, 'stop', new_callable=AsyncMock) as mock_stop:
            await agent.stop()
            
            assert agent.is_running is False
            mock_stop.assert_called_once()
            agent.room.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_join_room(self, agent, mock_room):
        """Test joining a room."""
        agent.room = mock_room
        token = "test-token"
        
        await agent.join_room("test-room", token)
        
        mock_room.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_join_room_not_started(self, agent):
        """Test joining a room when agent not started."""
        with pytest.raises(RuntimeError, match="Agent not started"):
            await agent.join_room("test-room", "test-token")
    
    @pytest.mark.asyncio
    async def test_handle_participant_connected(self, agent, mock_room, mock_participant):
        """Test handling participant connection."""
        agent.room = mock_room
        
        with patch.object(agent.session_manager, 'create_session', new_callable=AsyncMock) as mock_create:
            await agent._handle_participant_connected(mock_participant)
            
            mock_create.assert_called_once_with(mock_room, mock_participant, mock_create.call_args[0][2])
    
    @pytest.mark.asyncio
    async def test_handle_participant_disconnected(self, agent, mock_room, mock_participant):
        """Test handling participant disconnection."""
        agent.room = mock_room
        
        with patch.object(agent.session_manager, 'get_room_sessions', new_callable=AsyncMock) as mock_get_sessions, \
             patch.object(agent.session_manager, 'remove_session', new_callable=AsyncMock) as mock_remove:
            
            # Mock session with matching participant SID
            mock_session = Mock()
            mock_session.participant.sid = "test-sid"
            mock_get_sessions.return_value = [mock_session]
            
            await agent._handle_participant_disconnected(mock_participant)
            
            mock_get_sessions.assert_called_once_with("test-room")
            mock_remove.assert_called_once_with(mock_session.correlation_id)
    
    @pytest.mark.asyncio
    async def test_handle_data_received(self, agent, mock_room, mock_participant):
        """Test handling data channel messages."""
        agent.room = mock_room
        
        # Mock data packet
        data_packet = Mock()
        data_packet.data = b'{"type": "wake.detected", "timestamp": 1234567890, "correlation_id": "test-123", "payload": {"confidence": 0.8}}'
        data_packet.participant = mock_participant
        
        with patch.object(agent.session_manager, 'get_room_sessions', new_callable=AsyncMock) as mock_get_sessions, \
             patch.object(agent.session_manager, 'handle_control_message', new_callable=AsyncMock) as mock_handle:
            
            # Mock session
            mock_session = Mock()
            mock_session.participant.sid = "test-sid"
            mock_get_sessions.return_value = [mock_session]
            mock_handle.return_value = None
            
            # Mock data channel
            agent.data_channel = Mock()
            agent.data_channel.send = AsyncMock()
            
            await agent._handle_data_received(data_packet)
            
            mock_get_sessions.assert_called_once_with("test-room")
            mock_handle.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_audio_track(self, agent, mock_room, mock_participant):
        """Test handling audio track."""
        agent.room = mock_room
        
        # Mock audio track
        audio_track = Mock()
        audio_track.kind = "audio"
        audio_track.data = b"audio_data"
        
        with patch.object(agent.session_manager, 'get_room_sessions', new_callable=AsyncMock) as mock_get_sessions, \
             patch.object(agent.stt_adapter, 'start_stream', new_callable=AsyncMock) as mock_start_stream, \
             patch.object(agent.stt_adapter, 'process_audio_frame', new_callable=AsyncMock) as mock_process_frame, \
             patch.object(agent.stt_adapter, 'flush_stream', new_callable=AsyncMock) as mock_flush_stream, \
             patch.object(agent.stt_adapter, 'stop_stream', new_callable=AsyncMock) as mock_stop_stream, \
             patch.object(agent.audio_processor, 'decode_opus_to_pcm', new_callable=AsyncMock) as mock_decode, \
             patch.object(agent.audio_processor, 'resample_audio') as mock_resample, \
             patch.object(agent.audio_processor, 'create_audio_frame') as mock_create_frame:
            
            # Mock session
            mock_session = Mock()
            mock_session.participant.sid = "test-sid"
            mock_session.correlation_id = "test-123"
            mock_get_sessions.return_value = [mock_session]
            
            # Mock audio processing
            mock_decode.return_value = b"pcm_data"
            mock_resample.return_value = b"resampled_data"
            mock_create_frame.return_value = AudioFrame(
                pcm_data=b"resampled_data",
                timestamp=1234567890,
                sequence_number=0
            )
            
            # Mock async iterator for audio track
            async def mock_audio_iterator():
                yield audio_track
            
            audio_track.__aiter__ = lambda: mock_audio_iterator()
            
            await agent._handle_audio_track(audio_track, mock_participant)
            
            mock_get_sessions.assert_called_once_with("test-room")
            mock_start_stream.assert_called_once_with("test-123")
            mock_stop_stream.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_transcript(self, agent):
        """Test processing transcript segment."""
        # Mock session
        mock_session = Mock()
        mock_session.correlation_id = "test-123"
        mock_session.state = "idle"
        mock_session.endpointing_state = "listening"
        
        # Mock audio segment
        mock_segment = Mock()
        mock_segment.transcript = "hello world"
        mock_segment.is_final = True
        mock_segment.words = []
        mock_segment.confidence = 0.8
        
        # Mock data channel
        agent.data_channel = Mock()
        agent.data_channel.send = AsyncMock()
        
        with patch.object(agent, '_call_orchestrator', new_callable=AsyncMock) as mock_call_orchestrator:
            await agent._process_transcript(mock_session, mock_segment)
            
            # Check that data channel was used to send messages
            assert agent.data_channel.send.call_count >= 2  # At least transcript and endpointing messages
            mock_call_orchestrator.assert_called_once_with(mock_session, mock_segment)
    
    @pytest.mark.asyncio
    async def test_call_orchestrator(self, agent):
        """Test calling orchestrator service."""
        # Mock session
        mock_session = Mock()
        mock_session.correlation_id = "test-123"
        mock_session.state = "idle"
        mock_session.endpointing_state = "listening"
        mock_session.is_responding = False
        
        # Mock audio segment
        mock_segment = Mock()
        mock_segment.transcript = "hello world"
        
        # Mock data channel
        agent.data_channel = Mock()
        agent.data_channel.send = AsyncMock()
        
        with patch('httpx.AsyncClient') as mock_client:
            # Mock HTTP response
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.aiter_lines = AsyncMock(return_value=[
                'data: {"choices": [{"delta": {"content": "Hello"}}]}',
                'data: {"choices": [{"delta": {"content": " world"}}]}',
                'data: [DONE]'
            ])
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            with patch.object(agent.tts_adapter, 'start_stream', new_callable=AsyncMock) as mock_start_stream, \
                 patch.object(agent.tts_adapter, 'add_text_chunk', new_callable=AsyncMock) as mock_add_chunk, \
                 patch.object(agent.tts_adapter, 'stop_stream', new_callable=AsyncMock) as mock_stop_stream, \
                 patch.object(agent, '_send_audio_chunks', new_callable=AsyncMock) as mock_send_chunks:
                
                mock_start_stream.return_value = "tts_stream_123"
                
                await agent._call_orchestrator(mock_session, mock_segment)
                
                mock_start_stream.assert_called_once_with("test-123")
                assert mock_add_chunk.call_count == 2  # "Hello" and " world"
                mock_stop_stream.assert_called_once_with("tts_stream_123")
                mock_send_chunks.assert_called()
    
    @pytest.mark.asyncio
    async def test_send_audio_chunks(self, agent):
        """Test sending audio chunks."""
        # Mock session
        mock_session = Mock()
        mock_session.correlation_id = "test-123"
        
        with patch.object(agent.tts_adapter, 'get_audio_chunk', new_callable=AsyncMock) as mock_get_chunk:
            # Mock audio chunks
            mock_get_chunk.side_effect = [b"chunk1", b"chunk2", None]  # None to stop loop
            
            await agent._send_audio_chunks(mock_session, "tts_stream_123")
            
            assert mock_get_chunk.call_count == 3  # 2 chunks + 1 None


class TestLiveKitConfig:
    """Test LiveKit configuration."""
    
    def test_config_creation(self):
        """Test creating LiveKit configuration."""
        config = LiveKitConfig(
            livekit_url="wss://test.com",
            livekit_api_key="test-key",
            livekit_api_secret="test-secret"
        )
        
        assert config.livekit_url == "wss://test.com"
        assert config.livekit_api_key == "test-key"
        assert config.livekit_api_secret == "test-secret"
        assert config.service_name == "livekit-agent"
        assert config.port == 8080
        assert config.host == "0.0.0.0"
    
    def test_config_defaults(self):
        """Test configuration defaults."""
        config = LiveKitConfig(
            livekit_url="wss://test.com",
            livekit_api_key="test-key",
            livekit_api_secret="test-secret"
        )
        
        assert config.canonical_sample_rate == 16000
        assert config.canonical_frame_ms == 20
        assert config.opus_sample_rate == 48000
        assert config.max_session_duration_minutes == 30
        assert config.wake_cooldown_ms == 1000
        assert config.vad_timeout_ms == 2000
        assert config.endpointing_timeout_ms == 5000
        assert config.barge_in_enabled is True
        assert config.barge_in_pause_delay_ms == 250
        assert config.max_pause_duration_ms == 10000
        assert config.target_rtt_median_ms == 400
        assert config.target_rtt_p95_ms == 650
        assert config.max_packet_loss_percent == 10.0
        assert config.max_jitter_ms == 80.0
        assert config.log_level == "info"
        assert config.log_json is True
        assert config.debug_save is False
        assert config.auth_token == "changeme"
        assert config.stt_timeout == 45
        assert config.tts_timeout == 30
        assert config.orchestrator_timeout == 60
        assert config.max_retries == 3
        assert config.retry_delay_ms == 1000
        assert config.telemetry_interval_ms == 5000
        assert config.metrics_enabled is True


if __name__ == "__main__":
    pytest.main([__file__])