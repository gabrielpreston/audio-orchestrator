"""
Tests for mobile integration audio contracts and interfaces.
"""

import pytest
import time
from datetime import datetime
from services.common.audio_contracts import (
    AudioFrame,
    AudioSegment,
    WordTiming,
    MessageType,
    ControlMessage,
    WakeDetectedMessage,
    VADStartSpeechMessage,
    VADEndSpeechMessage,
    BargeInRequestMessage,
    SessionStateMessage,
    RouteChangeMessage,
    PlaybackControlMessage,
    EndpointingMessage,
    TranscriptPartialMessage,
    TranscriptFinalMessage,
    ErrorMessage,
    TelemetrySnapshotMessage,
    SessionState,
    EndpointingState,
    PlaybackAction,
    AudioRoute,
    AudioInput,
    STTAdapter,
    TTSAdapter,
)


class TestAudioFrame:
    """Test AudioFrame functionality."""
    
    def test_audio_frame_creation(self):
        """Test creating an audio frame."""
        pcm_data = b'\x00\x01\x02\x03' * 80  # 320 bytes for 20ms at 16kHz
        timestamp = time.time()
        
        frame = AudioFrame(
            pcm_data=pcm_data,
            timestamp=timestamp,
            sequence_number=1,
            is_speech=True,
            confidence=0.8
        )
        
        assert frame.pcm_data == pcm_data
        assert frame.timestamp == timestamp
        assert frame.sequence_number == 1
        assert frame.is_speech is True
        assert frame.confidence == 0.8
        assert frame.sample_rate == 16000
        assert frame.channels == 1
        assert frame.sample_width == 2
        assert frame.bit_depth == 16
        assert frame.frame_duration_ms == 20
        assert frame.samples_per_frame == 320
        assert frame.expected_bytes == 640
    
    def test_audio_frame_properties(self):
        """Test audio frame property calculations."""
        frame = AudioFrame(
            pcm_data=b'\x00' * 640,  # 320 samples * 2 bytes
            timestamp=time.time()
        )
        
        assert frame.samples_per_frame == 320
        assert frame.expected_bytes == 640


class TestAudioSegment:
    """Test AudioSegment functionality."""
    
    def test_audio_segment_creation(self):
        """Test creating an audio segment."""
        frames = [
            AudioFrame(pcm_data=b'\x00' * 640, timestamp=time.time()),
            AudioFrame(pcm_data=b'\x01' * 640, timestamp=time.time() + 0.02),
        ]
        
        words = [
            WordTiming(word="hello", start_time=0.0, end_time=0.5, confidence=0.9),
            WordTiming(word="world", start_time=0.5, end_time=1.0, confidence=0.8),
        ]
        
        segment = AudioSegment(
            audio_frames=frames,
            transcript="hello world",
            words=words,
            start_time=0.0,
            end_time=1.0,
            confidence=0.85,
            is_final=True
        )
        
        assert segment.audio_frames == frames
        assert segment.transcript == "hello world"
        assert segment.words == words
        assert segment.start_time == 0.0
        assert segment.end_time == 1.0
        assert segment.confidence == 0.85
        assert segment.is_final is True
        assert segment.duration_ms == 1000


class TestControlMessages:
    """Test control message functionality."""
    
    def test_wake_detected_message(self):
        """Test wake detected message creation."""
        correlation_id = "test_123"
        confidence = 0.8
        
        message = WakeDetectedMessage(correlation_id, confidence)
        
        assert message.message_type == MessageType.WAKE_DETECTED
        assert message.correlation_id == correlation_id
        assert message.payload["confidence"] == confidence
        assert isinstance(message.timestamp, float)
    
    def test_vad_start_speech_message(self):
        """Test VAD start speech message creation."""
        correlation_id = "test_123"
        
        message = VADStartSpeechMessage(correlation_id)
        
        assert message.message_type == MessageType.VAD_START_SPEECH
        assert message.correlation_id == correlation_id
        assert message.payload == {}
    
    def test_vad_end_speech_message(self):
        """Test VAD end speech message creation."""
        correlation_id = "test_123"
        duration_ms = 1500
        
        message = VADEndSpeechMessage(correlation_id, duration_ms)
        
        assert message.message_type == MessageType.VAD_END_SPEECH
        assert message.correlation_id == correlation_id
        assert message.payload["duration_ms"] == duration_ms
    
    def test_barge_in_request_message(self):
        """Test barge-in request message creation."""
        correlation_id = "test_123"
        reason = "user_speaking"
        
        message = BargeInRequestMessage(correlation_id, reason)
        
        assert message.message_type == MessageType.BARGE_IN_REQUEST
        assert message.correlation_id == correlation_id
        assert message.payload["reason"] == reason
    
    def test_session_state_message(self):
        """Test session state message creation."""
        correlation_id = "test_123"
        action = "mute"
        
        message = SessionStateMessage(correlation_id, action)
        
        assert message.message_type == MessageType.SESSION_STATE
        assert message.correlation_id == correlation_id
        assert message.payload["action"] == action
    
    def test_route_change_message(self):
        """Test route change message creation."""
        correlation_id = "test_123"
        output = "speaker"
        input_source = "built_in"
        
        message = RouteChangeMessage(correlation_id, output, input_source)
        
        assert message.message_type == MessageType.ROUTE_CHANGE
        assert message.correlation_id == correlation_id
        assert message.payload["output"] == output
        assert message.payload["input"] == input_source
    
    def test_playback_control_message(self):
        """Test playback control message creation."""
        correlation_id = "test_123"
        action = "pause"
        reason = "user_speaking"
        
        message = PlaybackControlMessage(correlation_id, action, reason)
        
        assert message.message_type == MessageType.PLAYBACK_CONTROL
        assert message.correlation_id == correlation_id
        assert message.payload["action"] == action
        assert message.payload["reason"] == reason
    
    def test_endpointing_message(self):
        """Test endpointing message creation."""
        correlation_id = "test_123"
        state = "processing"
        
        message = EndpointingMessage(correlation_id, state)
        
        assert message.message_type == MessageType.ENDPOINTING
        assert message.correlation_id == correlation_id
        assert message.payload["state"] == state
    
    def test_transcript_partial_message(self):
        """Test partial transcript message creation."""
        correlation_id = "test_123"
        text = "hello world"
        confidence = 0.8
        
        message = TranscriptPartialMessage(correlation_id, text, confidence)
        
        assert message.message_type == MessageType.TRANSCRIPT_PARTIAL
        assert message.correlation_id == correlation_id
        assert message.payload["text"] == text
        assert message.payload["confidence"] == confidence
    
    def test_transcript_final_message(self):
        """Test final transcript message creation."""
        correlation_id = "test_123"
        text = "hello world"
        words = [
            WordTiming(word="hello", start_time=0.0, end_time=0.5, confidence=0.9),
            WordTiming(word="world", start_time=0.5, end_time=1.0, confidence=0.8),
        ]
        
        message = TranscriptFinalMessage(correlation_id, text, words)
        
        assert message.message_type == MessageType.TRANSCRIPT_FINAL
        assert message.correlation_id == correlation_id
        assert message.payload["text"] == text
        assert len(message.payload["words"]) == 2
        assert message.payload["words"][0]["word"] == "hello"
        assert message.payload["words"][1]["word"] == "world"
    
    def test_error_message(self):
        """Test error message creation."""
        correlation_id = "test_123"
        code = "CONNECTION_ERROR"
        message_text = "Failed to connect"
        recoverable = True
        
        message = ErrorMessage(correlation_id, code, message_text, recoverable)
        
        assert message.message_type == MessageType.ERROR
        assert message.correlation_id == correlation_id
        assert message.payload["code"] == code
        assert message.payload["message"] == message_text
        assert message.payload["recoverable"] == recoverable
    
    def test_telemetry_snapshot_message(self):
        """Test telemetry snapshot message creation."""
        correlation_id = "test_123"
        rtt_ms = 150.5
        pl_percent = 2.1
        jitter_ms = 25.3
        
        message = TelemetrySnapshotMessage(correlation_id, rtt_ms, pl_percent, jitter_ms)
        
        assert message.message_type == MessageType.TELEMETRY_SNAPSHOT
        assert message.correlation_id == correlation_id
        assert message.payload["rtt_ms"] == rtt_ms
        assert message.payload["pl_percent"] == pl_percent
        assert message.payload["jitter_ms"] == jitter_ms
    
    def test_message_to_dict(self):
        """Test message serialization to dictionary."""
        correlation_id = "test_123"
        message = WakeDetectedMessage(correlation_id, 0.8)
        
        data = message.to_dict()
        
        assert data["type"] == "wake.detected"
        assert data["correlation_id"] == correlation_id
        assert data["payload"]["confidence"] == 0.8
        assert isinstance(data["timestamp"], float)


class TestEnums:
    """Test enum functionality."""
    
    def test_session_state_enum(self):
        """Test SessionState enum values."""
        assert SessionState.IDLE.value == "idle"
        assert SessionState.ARMING.value == "arming"
        assert SessionState.LIVE_LISTEN.value == "live_listen"
        assert SessionState.PROCESSING.value == "processing"
        assert SessionState.RESPONDING.value == "responding"
        assert SessionState.TEARDOWN.value == "teardown"
    
    def test_endpointing_state_enum(self):
        """Test EndpointingState enum values."""
        assert EndpointingState.LISTENING.value == "listening"
        assert EndpointingState.PROCESSING.value == "processing"
        assert EndpointingState.RESPONDING.value == "responding"
    
    def test_playback_action_enum(self):
        """Test PlaybackAction enum values."""
        assert PlaybackAction.PAUSE.value == "pause"
        assert PlaybackAction.RESUME.value == "resume"
        assert PlaybackAction.STOP.value == "stop"
    
    def test_audio_route_enum(self):
        """Test AudioRoute enum values."""
        assert AudioRoute.SPEAKER.value == "speaker"
        assert AudioRoute.EARPIECE.value == "earpiece"
        assert AudioRoute.BLUETOOTH.value == "bt"
    
    def test_audio_input_enum(self):
        """Test AudioInput enum values."""
        assert AudioInput.BUILT_IN.value == "built_in"
        assert AudioInput.BLUETOOTH.value == "bt"


class TestAdapters:
    """Test adapter interfaces."""
    
    def test_stt_adapter_interface(self):
        """Test STTAdapter interface methods."""
        # This is a mock implementation for testing
        class MockSTTAdapter(STTAdapter):
            async def start_stream(self, correlation_id: str) -> str:
                return f"stream_{correlation_id}"
            
            async def process_audio_frame(self, stream_id: str, frame: AudioFrame) -> AudioSegment:
                return AudioSegment(
                    audio_frames=[frame],
                    transcript="test",
                    words=[],
                    start_time=0.0,
                    end_time=0.02,
                    confidence=0.8
                )
            
            async def flush_stream(self, stream_id: str) -> AudioSegment:
                return AudioSegment(
                    audio_frames=[],
                    transcript="final test",
                    words=[],
                    start_time=0.0,
                    end_time=0.0,
                    confidence=0.9
                )
            
            async def stop_stream(self, stream_id: str) -> None:
                pass
        
        adapter = MockSTTAdapter()
        assert adapter is not None
    
    def test_tts_adapter_interface(self):
        """Test TTSAdapter interface methods."""
        # This is a mock implementation for testing
        class MockTTSAdapter(TTSAdapter):
            async def synthesize_text(self, text: str, voice: str = "default", correlation_id: str = "") -> bytes:
                return b"audio_data"
            
            async def start_stream(self, correlation_id: str) -> str:
                return f"stream_{correlation_id}"
            
            async def add_text_chunk(self, stream_id: str, text: str) -> None:
                pass
            
            async def get_audio_chunk(self, stream_id: str) -> bytes:
                return b"audio_chunk"
            
            async def pause_stream(self, stream_id: str) -> None:
                pass
            
            async def resume_stream(self, stream_id: str) -> None:
                pass
            
            async def stop_stream(self, stream_id: str) -> None:
                pass
        
        adapter = MockTTSAdapter()
        assert adapter is not None


class TestConstants:
    """Test configuration constants."""
    
    def test_audio_constants(self):
        """Test audio processing constants."""
        from services.common.audio_contracts import (
            CANONICAL_SAMPLE_RATE,
            CANONICAL_FRAME_MS,
            CANONICAL_CHANNELS,
            CANONICAL_SAMPLE_WIDTH,
            CANONICAL_BIT_DEPTH,
            OPUS_SAMPLE_RATE,
            OPUS_FRAME_MS,
            OPUS_CHANNELS,
        )
        
        assert CANONICAL_SAMPLE_RATE == 16000
        assert CANONICAL_FRAME_MS == 20
        assert CANONICAL_CHANNELS == 1
        assert CANONICAL_SAMPLE_WIDTH == 2
        assert CANONICAL_BIT_DEPTH == 16
        assert OPUS_SAMPLE_RATE == 48000
        assert OPUS_FRAME_MS == 20
        assert OPUS_CHANNELS == 1
    
    def test_latency_constants(self):
        """Test latency target constants."""
        from services.common.audio_contracts import (
            TARGET_RTT_MEDIAN,
            TARGET_RTT_P95,
            TARGET_BARGE_IN_PAUSE,
        )
        
        assert TARGET_RTT_MEDIAN == 400
        assert TARGET_RTT_P95 == 650
        assert TARGET_BARGE_IN_PAUSE == 250
    
    def test_quality_constants(self):
        """Test quality target constants."""
        from services.common.audio_contracts import (
            MAX_PACKET_LOSS_PERCENT,
            MAX_JITTER_MS,
            TARGET_UPTIME_PERCENT,
        )
        
        assert MAX_PACKET_LOSS_PERCENT == 10
        assert MAX_JITTER_MS == 80
        assert TARGET_UPTIME_PERCENT == 99.9
    
    def test_timeout_constants(self):
        """Test timeout constants."""
        from services.common.audio_contracts import (
            MAX_SESSION_DURATION_MINUTES,
            WAKE_COOLDOWN_MS,
            VAD_TIMEOUT_MS,
            ENDPOINTING_TIMEOUT_MS,
        )
        
        assert MAX_SESSION_DURATION_MINUTES == 30
        assert WAKE_COOLDOWN_MS == 1000
        assert VAD_TIMEOUT_MS == 2000
        assert ENDPOINTING_TIMEOUT_MS == 5000


if __name__ == "__main__":
    pytest.main([__file__])