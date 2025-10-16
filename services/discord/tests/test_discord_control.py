"""
Tests for Discord control channel adapter.

This module validates that the Discord control channel correctly implements
the ControlChannel interface and handles control events properly.
"""

from unittest.mock import Mock

import pytest

from services.common.surfaces.types import (
    EndpointingState,
    PlaybackAction,
    SessionAction,
    TelemetryMetrics,
    WordTimestamp,
)
from services.discord.adapters.discord_control import DiscordControlChannel


class TestDiscordControlChannel:
    """Test DiscordControlChannel functionality."""

    def test_discord_control_channel_creation(self):
        """Test creating DiscordControlChannel with basic parameters."""
        control = DiscordControlChannel(
            guild_id=123456789,
            channel_id=987654321,
        )

        assert control.guild_id == 123456789
        assert control.channel_id == 987654321
        assert control.user_id is None
        assert not control._is_connected
        assert control._total_events_sent == 0
        assert control._total_events_received == 0

    def test_discord_control_channel_creation_with_user(self):
        """Test creating DiscordControlChannel with user ID."""
        control = DiscordControlChannel(
            guild_id=123456789,
            channel_id=987654321,
            user_id=555666777,
        )

        assert control.guild_id == 123456789
        assert control.channel_id == 987654321
        assert control.user_id == 555666777

    def test_get_surface_id(self):
        """Test getting surface ID."""
        control = DiscordControlChannel(123456789, 987654321)
        surface_id = control.get_surface_id()

        assert surface_id == "discord_control:123456789:987654321"

    def test_get_voice_state_initial(self):
        """Test initial voice state."""
        control = DiscordControlChannel(123456789, 987654321)

        assert control.get_voice_state() == "disconnected"
        assert not control.is_speaking()
        assert not control.is_deaf()
        assert not control.is_mute()

    def test_update_voice_state(self):
        """Test updating voice state."""
        control = DiscordControlChannel(123456789, 987654321)

        control.update_voice_state("connected")
        assert control.get_voice_state() == "connected"

        control.update_voice_state("speaking")
        assert control.get_voice_state() == "speaking"

    def test_update_speaking_state(self):
        """Test updating speaking state."""
        control = DiscordControlChannel(123456789, 987654321)

        control.update_speaking_state(True)
        assert control.is_speaking()

        control.update_speaking_state(False)
        assert not control.is_speaking()

    def test_update_deaf_state(self):
        """Test updating deaf state."""
        control = DiscordControlChannel(123456789, 987654321)

        control.update_deaf_state(True)
        assert control.is_deaf()

        control.update_deaf_state(False)
        assert not control.is_deaf()

    def test_update_mute_state(self):
        """Test updating mute state."""
        control = DiscordControlChannel(123456789, 987654321)

        control.update_mute_state(True)
        assert control.is_mute()

        control.update_mute_state(False)
        assert not control.is_mute()

    def test_register_event_handler(self):
        """Test registering event handler."""
        control = DiscordControlChannel(123456789, 987654321)

        handler = Mock()
        control.register_event_handler(handler)

        assert handler in control._event_handlers

    def test_unregister_event_handler(self):
        """Test unregistering event handler."""
        control = DiscordControlChannel(123456789, 987654321)

        handler = Mock()
        control.register_event_handler(handler)
        control.unregister_event_handler(handler)

        assert handler not in control._event_handlers

    def test_unregister_event_handler_not_registered(self):
        """Test unregistering non-registered event handler."""
        control = DiscordControlChannel(123456789, 987654321)

        handler = Mock()
        # Don't register handler

        # Should not raise exception
        control.unregister_event_handler(handler)

    def test_get_connection_stats(self):
        """Test getting connection statistics."""
        control = DiscordControlChannel(123456789, 987654321)
        stats = control.get_connection_stats()

        assert "is_connected" in stats
        assert "total_events_sent" in stats
        assert "total_events_received" in stats
        assert "last_event_time" in stats
        assert "queue_size" in stats
        assert "voice_state" in stats
        assert "speaking" in stats
        assert "deaf" in stats
        assert "mute" in stats

        assert stats["is_connected"] is False
        assert stats["total_events_sent"] == 0
        assert stats["total_events_received"] == 0
        assert stats["voice_state"] == "disconnected"
        assert stats["speaking"] is False
        assert stats["deaf"] is False
        assert stats["mute"] is False

    def test_get_telemetry(self):
        """Test getting telemetry data."""
        control = DiscordControlChannel(123456789, 987654321, user_id=555666777)
        telemetry = control.get_telemetry()

        assert "surface_id" in telemetry
        assert "guild_id" in telemetry
        assert "channel_id" in telemetry
        assert "user_id" in telemetry
        assert "is_connected" in telemetry
        assert "total_events_sent" in telemetry
        assert "total_events_received" in telemetry
        assert "last_event_time" in telemetry
        assert "queue_size" in telemetry
        assert "voice_state" in telemetry
        assert "speaking" in telemetry
        assert "deaf" in telemetry
        assert "mute" in telemetry

        assert telemetry["surface_id"] == "discord_control:123456789:987654321"
        assert telemetry["guild_id"] == 123456789
        assert telemetry["channel_id"] == 987654321
        assert telemetry["user_id"] == 555666777
        assert telemetry["is_connected"] is False

    def test_update_policy(self):
        """Test updating surface policies."""
        control = DiscordControlChannel(123456789, 987654321)

        policy_config = {
            "wake_sensitivity": 0.8,
            "vad_threshold": 0.5,
            "barge_in_enabled": True,
        }

        # Should not raise exception
        control.update_policy(policy_config)

    def test_repr(self):
        """Test string representation."""
        control = DiscordControlChannel(123456789, 987654321, user_id=555666777)
        repr_str = repr(control)

        assert "DiscordControlChannel" in repr_str
        assert "guild_id=123456789" in repr_str
        assert "channel_id=987654321" in repr_str
        assert "user_id=555666777" in repr_str
        assert "connected=False" in repr_str

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connecting control channel."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()

        assert control._is_connected
        assert control._total_events_sent == 1  # Connection event
        assert control._last_event_time > 0

    @pytest.mark.asyncio
    async def test_connect_already_connected(self):
        """Test connecting when already connected."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()
        await control.connect()  # Should not raise exception

        assert control._is_connected

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting control channel."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()
        await control.disconnect()

        assert not control._is_connected
        assert control._total_events_sent == 2  # Connection and disconnect events

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self):
        """Test disconnecting when not connected."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.disconnect()  # Should not raise exception

        assert not control._is_connected

    @pytest.mark.asyncio
    async def test_send_event_not_connected(self):
        """Test sending event when not connected."""
        control = DiscordControlChannel(123456789, 987654321)

        # Should not raise exception
        await control.send_event({"event_type": "test"})

        assert control._total_events_sent == 0

    @pytest.mark.asyncio
    async def test_send_event_connected(self):
        """Test sending event when connected."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()
        await control.send_event({"event_type": "test"})

        assert control._total_events_sent == 2  # Connection + test event
        assert control._event_queue.qsize() == 2  # Both events in queue

    @pytest.mark.asyncio
    async def test_send_event_with_metadata(self):
        """Test sending event with metadata."""
        control = DiscordControlChannel(123456789, 987654321, user_id=555666777)

        await control.connect()
        await control.send_event({"event_type": "test"})

        # Check that metadata was added
        assert control._event_queue.qsize() == 2

        # Get the test event from queue
        await control._event_queue.get()  # Connection event
        test_event = await control._event_queue.get()

        assert test_event["event_type"] == "test"
        assert test_event["guild_id"] == 123456789
        assert test_event["channel_id"] == 987654321
        assert test_event["user_id"] == 555666777
        assert "timestamp" in test_event

    @pytest.mark.asyncio
    async def test_receive_event_not_connected(self):
        """Test receiving events when not connected."""
        control = DiscordControlChannel(123456789, 987654321)

        # Should not raise exception
        events = []
        async for event in control.receive_event():
            events.append(event)

        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_receive_event_connected(self):
        """Test receiving events when connected."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()
        await control.send_event({"event_type": "test1"})
        await control.send_event({"event_type": "test2"})

        events = []
        async for event in control.receive_event():
            events.append(event)
            if len(events) >= 3:  # Connection + 2 test events
                break

        assert len(events) == 3
        assert events[0]["event_type"] == "connection.established"
        assert events[1]["event_type"] == "test1"
        assert events[2]["event_type"] == "test2"

    @pytest.mark.asyncio
    async def test_receive_event_handlers(self):
        """Test that event handlers are called."""
        control = DiscordControlChannel(123456789, 987654321)

        handler = Mock()
        control.register_event_handler(handler)

        await control.connect()
        await control.send_event({"event_type": "test"})

        # Process events
        events = []
        async for event in control.receive_event():
            events.append(event)
            if len(events) >= 2:  # Connection + test event
                break

        # Handler should be called for both events
        assert handler.call_count >= 2

    @pytest.mark.asyncio
    async def test_receive_event_multiple_handlers(self):
        """Test that multiple event handlers are called."""
        control = DiscordControlChannel(123456789, 987654321)

        handler1 = Mock()
        handler2 = Mock()
        control.register_event_handler(handler1)
        control.register_event_handler(handler2)

        await control.connect()
        await control.send_event({"event_type": "test"})

        # Process events
        events = []
        async for event in control.receive_event():
            events.append(event)
            if len(events) >= 2:  # Connection + test event
                break

        # Both handlers should be called
        assert handler1.call_count >= 2
        assert handler2.call_count >= 2

    @pytest.mark.asyncio
    async def test_receive_event_handler_exception(self):
        """Test that handler exceptions don't break event processing."""
        control = DiscordControlChannel(123456789, 987654321)

        def failing_handler(event):
            raise ValueError("Handler failed")

        handler = Mock()
        control.register_event_handler(failing_handler)
        control.register_event_handler(handler)

        await control.connect()
        await control.send_event({"event_type": "test"})

        # Process events
        events = []
        async for event in control.receive_event():
            events.append(event)
            if len(events) >= 2:  # Connection + test event
                break

        # Should not raise exception
        assert len(events) == 2
        handler.assert_called()

    @pytest.mark.asyncio
    async def test_send_wake_detected(self):
        """Test sending wake detected event."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()
        await control.send_wake_detected(confidence=0.9, ts_device=1234567890.0)

        assert control._total_events_sent == 2  # Connection + wake event

        # Check event content
        await control._event_queue.get()  # Connection event
        wake_event = await control._event_queue.get()

        assert wake_event["event_type"] == "wake.detected"
        assert wake_event["confidence"] == 0.9
        assert wake_event["ts_device"] == 1234567890.0

    @pytest.mark.asyncio
    async def test_send_vad_start_speech(self):
        """Test sending VAD start speech event."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()
        await control.send_vad_start_speech(ts_device=1234567890.0)

        assert control._total_events_sent == 2  # Connection + VAD event

        # Check event content
        await control._event_queue.get()  # Connection event
        vad_event = await control._event_queue.get()

        assert vad_event["event_type"] == "vad.start_speech"
        assert vad_event["ts_device"] == 1234567890.0

    @pytest.mark.asyncio
    async def test_send_vad_end_speech(self):
        """Test sending VAD end speech event."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()
        await control.send_vad_end_speech(duration_ms=1500.0, ts_device=1234567890.0)

        assert control._total_events_sent == 2  # Connection + VAD event

        # Check event content
        await control._event_queue.get()  # Connection event
        vad_event = await control._event_queue.get()

        assert vad_event["event_type"] == "vad.end_speech"
        assert vad_event["ts_device"] == 1234567890.0
        assert vad_event["duration_ms"] == 1500.0

    @pytest.mark.asyncio
    async def test_send_barge_in_request(self):
        """Test sending barge-in request event."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()
        await control.send_barge_in_request(
            reason="user_interruption", ts_device=1234567890.0
        )

        assert control._total_events_sent == 2  # Connection + barge-in event

        # Check event content
        await control._event_queue.get()  # Connection event
        barge_in_event = await control._event_queue.get()

        assert barge_in_event["event_type"] == "barge_in.request"
        assert barge_in_event["reason"] == "user_interruption"
        assert barge_in_event["ts_device"] == 1234567890.0

    @pytest.mark.asyncio
    async def test_send_session_state(self):
        """Test sending session state event."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()
        await control.send_session_state(SessionAction.JOIN)

        assert control._total_events_sent == 2  # Connection + session event

        # Check event content
        await control._event_queue.get()  # Connection event
        session_event = await control._event_queue.get()

        assert session_event["event_type"] == "session.state"
        assert session_event["action"] == "join"

    @pytest.mark.asyncio
    async def test_send_route_change(self):
        """Test sending route change event."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()
        await control.send_route_change(
            input_route="microphone", output_route="speakers"
        )

        assert control._total_events_sent == 2  # Connection + route event

        # Check event content
        await control._event_queue.get()  # Connection event
        route_event = await control._event_queue.get()

        assert route_event["event_type"] == "route.change"
        assert route_event["input"] == "microphone"
        assert route_event["output"] == "speakers"

    @pytest.mark.asyncio
    async def test_send_playback_control(self):
        """Test sending playback control event."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()
        await control.send_playback_control(
            PlaybackAction.PAUSE, reason="user_interruption"
        )

        assert control._total_events_sent == 2  # Connection + playback event

        # Check event content
        await control._event_queue.get()  # Connection event
        playback_event = await control._event_queue.get()

        assert playback_event["event_type"] == "playback.control"
        assert playback_event["action"] == "pause"
        assert playback_event["reason"] == "user_interruption"

    @pytest.mark.asyncio
    async def test_send_endpointing(self):
        """Test sending endpointing event."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()
        await control.send_endpointing(EndpointingState.PROCESSING)

        assert control._total_events_sent == 2  # Connection + endpointing event

        # Check event content
        await control._event_queue.get()  # Connection event
        endpointing_event = await control._event_queue.get()

        assert endpointing_event["event_type"] == "endpointing"
        assert endpointing_event["state"] == "processing"

    @pytest.mark.asyncio
    async def test_send_transcript_partial(self):
        """Test sending partial transcript event."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()
        await control.send_transcript_partial(
            text="hello world", confidence=0.9, ts_server=1234567890.0
        )

        assert control._total_events_sent == 2  # Connection + transcript event

        # Check event content
        await control._event_queue.get()  # Connection event
        transcript_event = await control._event_queue.get()

        assert transcript_event["event_type"] == "transcript.partial"
        assert transcript_event["text"] == "hello world"
        assert transcript_event["confidence"] == 0.9
        assert transcript_event["ts_server"] == 1234567890.0

    @pytest.mark.asyncio
    async def test_send_transcript_final(self):
        """Test sending final transcript event."""
        control = DiscordControlChannel(123456789, 987654321)

        words = [
            WordTimestamp("hello", 0.0, 0.5, 0.9),
            WordTimestamp("world", 0.5, 1.0, 0.8),
        ]

        await control.connect()
        await control.send_transcript_final(text="hello world", words=words)

        assert control._total_events_sent == 2  # Connection + transcript event

        # Check event content
        await control._event_queue.get()  # Connection event
        transcript_event = await control._event_queue.get()

        assert transcript_event["event_type"] == "transcript.final"
        assert transcript_event["text"] == "hello world"
        assert len(transcript_event["words"]) == 2
        assert transcript_event["words"][0]["word"] == "hello"
        assert transcript_event["words"][1]["word"] == "world"

    @pytest.mark.asyncio
    async def test_send_telemetry_snapshot(self):
        """Test sending telemetry snapshot event."""
        control = DiscordControlChannel(123456789, 987654321)

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

        await control.connect()
        await control.send_telemetry_snapshot(metrics)

        assert control._total_events_sent == 2  # Connection + telemetry event

        # Check event content
        await control._event_queue.get()  # Connection event
        telemetry_event = await control._event_queue.get()

        assert telemetry_event["event_type"] == "telemetry.snapshot"
        assert telemetry_event["rtt_ms"] == 50.0
        assert telemetry_event["packet_loss_percent"] == 2.0
        assert telemetry_event["jitter_ms"] == 5.0
        assert telemetry_event["battery_temp"] == 35.0
        assert telemetry_event["e2e_latency_ms"] == 200.0
        assert telemetry_event["barge_in_delay_ms"] == 150.0
        assert telemetry_event["stt_partial_time_ms"] == 300.0
        assert telemetry_event["tts_first_byte_ms"] == 100.0

    @pytest.mark.asyncio
    async def test_send_error(self):
        """Test sending error event."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()
        await control.send_error(
            code="AUDIO_ERROR", message="Audio device not available", recoverable=True
        )

        assert control._total_events_sent == 2  # Connection + error event

        # Check event content
        await control._event_queue.get()  # Connection event
        error_event = await control._event_queue.get()

        assert error_event["event_type"] == "error"
        assert error_event["code"] == "AUDIO_ERROR"
        assert error_event["message"] == "Audio device not available"
        assert error_event["recoverable"] is True

    @pytest.mark.asyncio
    async def test_connection_stats_after_events(self):
        """Test connection stats after sending events."""
        control = DiscordControlChannel(123456789, 987654321)

        await control.connect()
        await control.send_event({"event_type": "test1"})
        await control.send_event({"event_type": "test2"})

        stats = control.get_connection_stats()

        assert stats["total_events_sent"] == 3  # Connection + 2 test events
        assert stats["queue_size"] == 3
        assert stats["last_event_time"] > 0
