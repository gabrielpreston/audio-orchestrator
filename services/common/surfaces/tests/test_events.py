"""
Tests for control channel events and schema validation.

This module validates that control events are properly serialized
and that schema validation works correctly.
"""

import json

from services.common.surfaces.events import (
    BargeInRequestEvent,
    EndpointingEvent,
    ErrorEvent,
    PlaybackControlEvent,
    RouteChangeEvent,
    SessionStateEvent,
    TelemetrySnapshotEvent,
    TranscriptFinalEvent,
    TranscriptPartialEvent,
    VADEndSpeechEvent,
    VADStartSpeechEvent,
    WakeDetectedEvent,
)
from services.common.surfaces.schema import (
    get_event_schema,
    get_supported_event_types,
    validate_control_event,
    validate_control_event_json,
)
from services.common.surfaces.types import (
    EndpointingState,
    PlaybackAction,
    SessionAction,
    TelemetryMetrics,
    WordTimestamp,
)


class TestControlEvents:
    """Test control event serialization and validation."""

    def test_wake_detected_event_serialization(self):
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

    def test_vad_start_speech_event_serialization(self):
        """Test VADStartSpeechEvent serialization."""
        event = VADStartSpeechEvent(
            correlation_id="corr123",
            ts_device=1234567890.0,
        )

        data = event.to_dict()
        assert data["event_type"] == "vad.start_speech"
        assert data["correlation_id"] == "corr123"
        assert data["ts_device"] == 1234567890.0

    def test_vad_end_speech_event_serialization(self):
        """Test VADEndSpeechEvent serialization."""
        event = VADEndSpeechEvent(
            correlation_id="corr123",
            ts_device=1234567890.0,
            duration_ms=1500.0,
        )

        data = event.to_dict()
        assert data["event_type"] == "vad.end_speech"
        assert data["correlation_id"] == "corr123"
        assert data["ts_device"] == 1234567890.0
        assert data["duration_ms"] == 1500.0

    def test_barge_in_request_event_serialization(self):
        """Test BargeInRequestEvent serialization."""
        event = BargeInRequestEvent(
            correlation_id="corr123",
            reason="user_interruption",
            ts_device=1234567890.0,
        )

        data = event.to_dict()
        assert data["event_type"] == "barge_in.request"
        assert data["correlation_id"] == "corr123"
        assert data["reason"] == "user_interruption"
        assert data["ts_device"] == 1234567890.0

    def test_session_state_event_serialization(self):
        """Test SessionStateEvent serialization."""
        event = SessionStateEvent(
            correlation_id="corr123",
            action=SessionAction.JOIN,
        )

        data = event.to_dict()
        assert data["event_type"] == "session.state"
        assert data["correlation_id"] == "corr123"
        assert data["action"] == "join"

    def test_route_change_event_serialization(self):
        """Test RouteChangeEvent serialization."""
        event = RouteChangeEvent(
            correlation_id="corr123",
            input="microphone",
            output="speakers",
        )

        data = event.to_dict()
        assert data["event_type"] == "route.change"
        assert data["correlation_id"] == "corr123"
        assert data["input"] == "microphone"
        assert data["output"] == "speakers"

    def test_playback_control_event_serialization(self):
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

    def test_endpointing_event_serialization(self):
        """Test EndpointingEvent serialization."""
        event = EndpointingEvent(
            correlation_id="corr123",
            state=EndpointingState.PROCESSING,
        )

        data = event.to_dict()
        assert data["event_type"] == "endpointing"
        assert data["correlation_id"] == "corr123"
        assert data["state"] == "processing"

    def test_transcript_partial_event_serialization(self):
        """Test TranscriptPartialEvent serialization."""
        event = TranscriptPartialEvent(
            correlation_id="corr123",
            text="hello world",
            confidence=0.9,
            ts_server=1234567890.0,
        )

        data = event.to_dict()
        assert data["event_type"] == "transcript.partial"
        assert data["correlation_id"] == "corr123"
        assert data["text"] == "hello world"
        assert data["confidence"] == 0.9
        assert data["ts_server"] == 1234567890.0

    def test_transcript_final_event_serialization(self):
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

    def test_telemetry_snapshot_event_serialization(self):
        """Test TelemetrySnapshotEvent serialization."""
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

        event = TelemetrySnapshotEvent(
            correlation_id="corr123",
            metrics=metrics,
        )

        data = event.to_dict()
        assert data["event_type"] == "telemetry.snapshot"
        assert data["correlation_id"] == "corr123"
        assert data["rtt_ms"] == 50.0
        assert data["packet_loss_percent"] == 2.0
        assert data["jitter_ms"] == 5.0
        assert data["battery_temp"] == 35.0
        assert data["e2e_latency_ms"] == 200.0
        assert data["barge_in_delay_ms"] == 150.0
        assert data["stt_partial_time_ms"] == 300.0
        assert data["tts_first_byte_ms"] == 100.0

    def test_error_event_serialization(self):
        """Test ErrorEvent serialization."""
        event = ErrorEvent(
            correlation_id="corr123",
            code="AUDIO_ERROR",
            message="Audio device not available",
            recoverable=True,
        )

        data = event.to_dict()
        assert data["event_type"] == "error"
        assert data["correlation_id"] == "corr123"
        assert data["code"] == "AUDIO_ERROR"
        assert data["message"] == "Audio device not available"
        assert data["recoverable"] is True


class TestSchemaValidation:
    """Test schema validation functionality."""

    def test_validate_wake_detected_event(self):
        """Test validation of wake detected event."""
        event_data = {
            "event_type": "wake.detected",
            "timestamp": 1234567890.0,
            "correlation_id": "corr123",
            "confidence": 0.95,
            "ts_device": 1234567890.0,
        }

        assert validate_control_event(event_data) is True

    def test_validate_wake_detected_event_missing_required(self):
        """Test validation fails with missing required field."""
        event_data = {
            "event_type": "wake.detected",
            "timestamp": 1234567890.0,
            "correlation_id": "corr123",
            # Missing confidence
            "ts_device": 1234567890.0,
        }

        assert validate_control_event(event_data) is False

    def test_validate_wake_detected_event_invalid_confidence(self):
        """Test validation fails with invalid confidence value."""
        event_data = {
            "event_type": "wake.detected",
            "timestamp": 1234567890.0,
            "correlation_id": "corr123",
            "confidence": 1.5,  # Invalid: > 1.0
            "ts_device": 1234567890.0,
        }

        assert validate_control_event(event_data) is False

    def test_validate_playback_control_event(self):
        """Test validation of playback control event."""
        event_data = {
            "event_type": "playback.control",
            "timestamp": 1234567890.0,
            "correlation_id": "corr123",
            "action": "pause",
            "reason": "user_interruption",
        }

        assert validate_control_event(event_data) is True

    def test_validate_playback_control_event_invalid_action(self):
        """Test validation fails with invalid action."""
        event_data = {
            "event_type": "playback.control",
            "timestamp": 1234567890.0,
            "correlation_id": "corr123",
            "action": "invalid_action",  # Invalid action
            "reason": "user_interruption",
        }

        assert validate_control_event(event_data) is False

    def test_validate_transcript_final_event(self):
        """Test validation of transcript final event."""
        event_data = {
            "event_type": "transcript.final",
            "timestamp": 1234567890.0,
            "correlation_id": "corr123",
            "text": "hello world",
            "words": [
                {
                    "word": "hello",
                    "start": 0.0,
                    "end": 0.5,
                    "confidence": 0.9,
                },
                {
                    "word": "world",
                    "start": 0.5,
                    "end": 1.0,
                    "confidence": 0.8,
                },
            ],
        }

        assert validate_control_event(event_data) is True

    def test_validate_transcript_final_event_invalid_word_timestamp(self):
        """Test validation fails with invalid word timestamp."""
        event_data = {
            "event_type": "transcript.final",
            "timestamp": 1234567890.0,
            "correlation_id": "corr123",
            "text": "hello world",
            "words": [
                {
                    "word": "hello",
                    "start": -0.1,  # Invalid: negative start time
                    "end": 0.5,
                    "confidence": 0.9,
                },
            ],
        }

        assert validate_control_event(event_data) is False

    def test_validate_json_string(self):
        """Test validation of JSON string."""
        event_json = json.dumps(
            {
                "event_type": "wake.detected",
                "timestamp": 1234567890.0,
                "correlation_id": "corr123",
                "confidence": 0.95,
                "ts_device": 1234567890.0,
            }
        )

        assert validate_control_event_json(event_json) is True

    def test_validate_json_string_invalid(self):
        """Test validation fails with invalid JSON."""
        event_json = "invalid json"

        assert validate_control_event_json(event_json) is False

    def test_get_event_schema(self):
        """Test getting event schema."""
        schema = get_event_schema("wake.detected")

        assert schema is not None
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema

    def test_get_event_schema_unknown(self):
        """Test getting schema for unknown event type."""
        schema = get_event_schema("unknown.event")

        assert schema is None

    def test_get_supported_event_types(self):
        """Test getting supported event types."""
        event_types = get_supported_event_types()

        assert "wake.detected" in event_types
        assert "vad.start_speech" in event_types
        assert "vad.end_speech" in event_types
        assert "barge_in.request" in event_types
        assert "session.state" in event_types
        assert "route.change" in event_types
        assert "playback.control" in event_types
        assert "endpointing" in event_types
        assert "transcript.partial" in event_types
        assert "transcript.final" in event_types
        assert "telemetry.snapshot" in event_types
        assert "error" in event_types
