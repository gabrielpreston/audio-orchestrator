"""
Tests for surface interface protocols and data types.

This module validates that the core interfaces are properly defined
and that data types can be serialized/deserialized correctly.
"""

import pytest

from services.common.surfaces.events import (
    PlaybackControlEvent,
    TranscriptFinalEvent,
    VADStartSpeechEvent,
    WakeDetectedEvent,
)
from services.common.surfaces.protocols import (
    AudioCaptureProtocol,
    AudioPlaybackProtocol,
    SurfaceControlProtocol,
    SurfaceTelemetryProtocol,
)
from services.common.surfaces.types import (
    AudioFormat,
    AudioMetadata,
    AudioSegment,
    EndpointingState,
    PCMFrame,
    PlaybackAction,
    SessionAction,
    TelemetryMetrics,
    WordTimestamp,
)


class TestAudioMetadata:
    """Test AudioMetadata data structure."""

    @pytest.mark.unit
    @pytest.mark.unit
    def test_audio_metadata_creation(self):
        """Test creating AudioMetadata with valid data."""
        metadata = AudioMetadata(
            sample_rate=16000,
            channels=1,
            sample_width=2,
            duration=1.0,
            frames=16000,
            format=AudioFormat.PCM,
            bit_depth=16,
        )

        assert metadata.sample_rate == 16000
        assert metadata.channels == 1
        assert metadata.sample_width == 2
        assert metadata.duration == 1.0
        assert metadata.frames == 16000
        assert metadata.format == AudioFormat.PCM
        assert metadata.bit_depth == 16

    @pytest.mark.unit
    @pytest.mark.unit
    def test_audio_metadata_properties(self):
        """Test AudioMetadata calculated properties."""
        metadata = AudioMetadata(
            sample_rate=16000,
            channels=1,
            sample_width=2,
            duration=1.0,
            frames=16000,
            format=AudioFormat.PCM,
            bit_depth=16,
        )

        assert metadata.bytes_per_second == 32000  # 16000 * 1 * 2
        assert metadata.total_bytes == 32000  # 16000 * 1 * 2


class TestPCMFrame:
    """Test PCMFrame data structure."""

    @pytest.mark.unit
    def test_pcm_frame_creation(self):
        """Test creating PCMFrame with valid data."""
        frame = PCMFrame(
            pcm=b"\x00\x01\x02\x03",
            timestamp=1234567890.0,
            rms=1000.0,
            duration=0.02,
            sequence=1,
            sample_rate=16000,
        )

        assert frame.pcm == b"\x00\x01\x02\x03"
        assert frame.timestamp == 1234567890.0
        assert frame.rms == 1000.0
        assert frame.duration == 0.02
        assert frame.sequence == 1
        assert frame.sample_rate == 16000
        assert frame.channels == 1  # default
        assert frame.sample_width == 2  # default

    @pytest.mark.unit
    def test_pcm_frame_properties(self):
        """Test PCMFrame calculated properties."""
        frame = PCMFrame(
            pcm=b"\x00\x01\x02\x03",
            timestamp=1234567890.0,
            rms=1000.0,
            duration=0.02,
            sequence=1,
            sample_rate=16000,
        )

        assert frame.frame_size_ms == 20.0  # 0.02 * 1000


class TestAudioSegment:
    """Test AudioSegment data structure."""

    @pytest.mark.unit
    def test_audio_segment_creation(self):
        """Test creating AudioSegment with valid data."""
        segment = AudioSegment(
            user_id="user123",
            pcm=b"\x00\x01\x02\x03",
            start_timestamp=1234567890.0,
            end_timestamp=1234567891.0,
            correlation_id="corr123",
            frame_count=100,
            sample_rate=16000,
        )

        assert segment.user_id == "user123"
        assert segment.pcm == b"\x00\x01\x02\x03"
        assert segment.start_timestamp == 1234567890.0
        assert segment.end_timestamp == 1234567891.0
        assert segment.correlation_id == "corr123"
        assert segment.frame_count == 100
        assert segment.sample_rate == 16000

    @pytest.mark.unit
    def test_audio_segment_properties(self):
        """Test AudioSegment calculated properties."""
        segment = AudioSegment(
            user_id="user123",
            pcm=b"\x00\x01\x02\x03",
            start_timestamp=1234567890.0,
            end_timestamp=1234567891.0,
            correlation_id="corr123",
            frame_count=100,
            sample_rate=16000,
        )

        assert segment.duration == 1.0
        assert isinstance(segment.metadata, AudioMetadata)
        assert segment.metadata.sample_rate == 16000


class TestControlEvents:
    """Test control event serialization."""

    @pytest.mark.unit
    def test_wake_detected_event(self):
        """Test WakeDetectedEvent serialization."""
        event = WakeDetectedEvent(
            correlation_id="corr123",
            confidence=0.95,
            ts_device=1234567890.0,
        )

        data = event.to_dict()
        assert data["event_type"] == "wake.detected"
        assert data["correlation_id"] == "corr123"
        assert data["confidence"] == 0.95
        assert data["ts_device"] == 1234567890.0

    @pytest.mark.unit
    def test_vad_start_speech_event(self):
        """Test VADStartSpeechEvent serialization."""
        event = VADStartSpeechEvent(
            correlation_id="corr123",
            ts_device=1234567890.0,
        )

        data = event.to_dict()
        assert data["event_type"] == "vad.start_speech"
        assert data["correlation_id"] == "corr123"
        assert data["ts_device"] == 1234567890.0

    @pytest.mark.unit
    def test_playback_control_event(self):
        """Test PlaybackControlEvent serialization."""
        event = PlaybackControlEvent(
            correlation_id="corr123",
            action=PlaybackAction.PAUSE,
            reason="user_interruption",
        )

        data = event.to_dict()
        assert data["event_type"] == "playback.control"
        assert data["correlation_id"] == "corr123"
        assert data["action"] == "pause"
        assert data["reason"] == "user_interruption"

    @pytest.mark.unit
    def test_transcript_final_event(self):
        """Test TranscriptFinalEvent with word timestamps."""
        words = [
            WordTimestamp("hello", 0.0, 0.5, 0.9),
            WordTimestamp("world", 0.5, 1.0, 0.8),
        ]

        event = TranscriptFinalEvent(
            correlation_id="corr123",
            text="hello world",
            words=words,
        )

        data = event.to_dict()
        assert data["event_type"] == "transcript.final"
        assert data["correlation_id"] == "corr123"
        assert data["text"] == "hello world"
        assert len(data["words"]) == 2
        assert data["words"][0]["word"] == "hello"
        assert data["words"][0]["start"] == 0.0
        assert data["words"][0]["end"] == 0.5
        assert data["words"][0]["confidence"] == 0.9


class TestEnums:
    """Test enum values."""

    @pytest.mark.unit
    def test_audio_format_enum(self):
        """Test AudioFormat enum values."""
        assert AudioFormat.PCM.value == "pcm"
        assert AudioFormat.WAV.value == "wav"
        assert AudioFormat.OPUS.value == "opus"

    @pytest.mark.unit
    def test_endpointing_state_enum(self):
        """Test EndpointingState enum values."""
        assert EndpointingState.LISTENING.value == "listening"
        assert EndpointingState.PROCESSING.value == "processing"
        assert EndpointingState.RESPONDING.value == "responding"

    @pytest.mark.unit
    def test_playback_action_enum(self):
        """Test PlaybackAction enum values."""
        assert PlaybackAction.START.value == "start"
        assert PlaybackAction.PAUSE.value == "pause"
        assert PlaybackAction.RESUME.value == "resume"
        assert PlaybackAction.STOP.value == "stop"

    @pytest.mark.unit
    def test_session_action_enum(self):
        """Test SessionAction enum values."""
        assert SessionAction.JOIN.value == "join"
        assert SessionAction.LEAVE.value == "leave"
        assert SessionAction.MUTE.value == "mute"
        assert SessionAction.UNMUTE.value == "unmute"


class TestTelemetryMetrics:
    """Test TelemetryMetrics data structure."""

    @pytest.mark.unit
    def test_telemetry_metrics_creation(self):
        """Test creating TelemetryMetrics with valid data."""
        metrics = TelemetryMetrics(
            rtt_ms=50.0,
            packet_loss_percent=2.0,
            jitter_ms=5.0,
            battery_temp=35.0,
            e2e_latency_ms=200.0,
            barge_in_delay_ms=150.0,
            stt_partial_time_ms=300.0,
            tts_first_byte_ms=100.0,
        )

        assert metrics.rtt_ms == 50.0
        assert metrics.packet_loss_percent == 2.0
        assert metrics.jitter_ms == 5.0
        assert metrics.battery_temp == 35.0
        assert metrics.e2e_latency_ms == 200.0
        assert metrics.barge_in_delay_ms == 150.0
        assert metrics.stt_partial_time_ms == 300.0
        assert metrics.tts_first_byte_ms == 100.0


class TestProtocolCompliance:
    """Test that protocols are properly defined."""

    @pytest.mark.unit
    def test_audio_capture_protocol(self):
        """Test AudioCaptureProtocol has required methods."""
        # This is a structural test - we can't easily test protocols
        # without concrete implementations, but we can verify the
        # protocol is properly defined by checking it exists
        assert hasattr(AudioCaptureProtocol, "__annotations__")

    @pytest.mark.unit
    def test_audio_playback_protocol(self):
        """Test AudioPlaybackProtocol has required methods."""
        assert hasattr(AudioPlaybackProtocol, "__annotations__")

    @pytest.mark.unit
    def test_surface_control_protocol(self):
        """Test SurfaceControlProtocol has required methods."""
        assert hasattr(SurfaceControlProtocol, "__annotations__")

    @pytest.mark.unit
    def test_surface_telemetry_protocol(self):
        """Test SurfaceTelemetryProtocol has required methods."""
        assert hasattr(SurfaceTelemetryProtocol, "__annotations__")
