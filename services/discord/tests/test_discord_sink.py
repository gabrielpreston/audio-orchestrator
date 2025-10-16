"""
Tests for Discord audio sink adapter.

This module validates that the Discord audio sink correctly implements
the AudioSink interface and handles audio playback properly.
"""

import asyncio
import time
from typing import Any
from unittest.mock import Mock

import pytest

from services.common.surfaces.media_gateway import MediaGateway
from services.common.surfaces.types import AudioMetadata
from services.discord.adapters.discord_sink import DiscordAudioSink


class TestDiscordAudioSink:
    """Test DiscordAudioSink functionality."""

    def test_discord_audio_sink_creation(self):
        """Test creating DiscordAudioSink with basic parameters."""
        sink = DiscordAudioSink(
            guild_id=123456789,
            channel_id=987654321,
        )

        assert sink.guild_id == 123456789
        assert sink.channel_id == 987654321
        assert sink.media_gateway is not None
        assert not sink.is_playing()
        assert sink.get_current_audio_url() is None

    def test_discord_audio_sink_creation_with_media_gateway(self):
        """Test creating DiscordAudioSink with custom media gateway."""
        media_gateway = MediaGateway()
        sink = DiscordAudioSink(
            guild_id=123456789,
            channel_id=987654321,
            media_gateway=media_gateway,
        )

        assert sink.media_gateway is media_gateway

    def test_get_surface_id(self):
        """Test getting surface ID."""
        sink = DiscordAudioSink(123456789, 987654321)
        surface_id = sink.get_surface_id()

        assert surface_id == "discord_sink:123456789:987654321"

    def test_get_guild_id(self):
        """Test getting guild ID."""
        sink = DiscordAudioSink(123456789, 987654321)
        guild_id = sink.get_guild_id()

        assert guild_id == 123456789

    def test_get_channel_id(self):
        """Test getting channel ID."""
        sink = DiscordAudioSink(123456789, 987654321)
        channel_id = sink.get_channel_id()

        assert channel_id == 987654321

    def test_is_playing_initial(self):
        """Test initial playing state."""
        sink = DiscordAudioSink(123456789, 987654321)

        assert not sink.is_playing()

    def test_get_current_audio_url_initial(self):
        """Test initial audio URL."""
        sink = DiscordAudioSink(123456789, 987654321)

        assert sink.get_current_audio_url() is None

    def test_set_current_audio_url(self):
        """Test setting current audio URL."""
        sink = DiscordAudioSink(123456789, 987654321)

        audio_url = "https://example.com/audio.wav"
        sink.set_current_audio_url(audio_url)

        assert sink.get_current_audio_url() == audio_url

    def test_register_playback_handler(self):
        """Test registering playback handler."""
        sink = DiscordAudioSink(123456789, 987654321)

        handler = Mock()
        sink.register_playback_handler(handler)

        assert handler in sink._playback_handlers

    def test_unregister_playback_handler(self):
        """Test unregistering playback handler."""
        sink = DiscordAudioSink(123456789, 987654321)

        handler = Mock()
        sink.register_playback_handler(handler)
        sink.unregister_playback_handler(handler)

        assert handler not in sink._playback_handlers

    def test_unregister_playback_handler_not_registered(self):
        """Test unregistering non-registered playback handler."""
        sink = DiscordAudioSink(123456789, 987654321)

        handler = Mock()
        # Don't register handler

        # Should not raise exception
        sink.unregister_playback_handler(handler)

    def test_set_media_gateway(self):
        """Test setting media gateway."""
        sink = DiscordAudioSink(123456789, 987654321)
        new_gateway = MediaGateway()

        sink.set_media_gateway(new_gateway)

        assert sink.media_gateway is new_gateway

    def test_get_media_gateway(self):
        """Test getting media gateway."""
        sink = DiscordAudioSink(123456789, 987654321)
        gateway = sink.get_media_gateway()

        assert gateway is not None
        assert isinstance(gateway, MediaGateway)

    def test_get_playback_stats(self):
        """Test getting playback statistics."""
        sink = DiscordAudioSink(123456789, 987654321)
        stats = sink.get_playback_stats()

        assert "is_playing" in stats
        assert "total_audio_played" in stats
        assert "total_playback_requests" in stats
        assert "last_playback_time" in stats
        assert "current_audio_url" in stats
        assert "playback_start_time" in stats

        assert stats["is_playing"] is False
        assert stats["total_audio_played"] == 0.0
        assert stats["total_playback_requests"] == 0
        assert stats["current_audio_url"] is None
        assert stats["playback_start_time"] == 0.0

    def test_get_telemetry(self):
        """Test getting telemetry data."""
        sink = DiscordAudioSink(123456789, 987654321)
        telemetry = sink.get_telemetry()

        assert "surface_id" in telemetry
        assert "guild_id" in telemetry
        assert "channel_id" in telemetry
        assert "is_playing" in telemetry
        assert "total_audio_played" in telemetry
        assert "total_playback_requests" in telemetry
        assert "last_playback_time" in telemetry
        assert "current_audio_url" in telemetry
        assert "playback_start_time" in telemetry
        assert "metadata" in telemetry

        assert telemetry["surface_id"] == "discord_sink:123456789:987654321"
        assert telemetry["guild_id"] == 123456789
        assert telemetry["channel_id"] == 987654321
        assert telemetry["is_playing"] is False

    def test_update_policy(self):
        """Test updating surface policies."""
        sink = DiscordAudioSink(123456789, 987654321)

        policy_config = {
            "playback_quality": "high",
            "volume": 0.8,
            "barge_in_enabled": True,
        }

        # Should not raise exception
        sink.update_policy(policy_config)

    def test_repr(self):
        """Test string representation."""
        sink = DiscordAudioSink(123456789, 987654321)
        repr_str = repr(sink)

        assert "DiscordAudioSink" in repr_str
        assert "guild_id=123456789" in repr_str
        assert "channel_id=987654321" in repr_str
        assert "playing=False" in repr_str

    @pytest.mark.asyncio
    async def test_start_playback(self):
        """Test starting audio playback."""
        sink = DiscordAudioSink(123456789, 987654321)

        await sink.start_playback()

        assert sink.is_playing()
        assert sink._playback_start_time > 0

    @pytest.mark.asyncio
    async def test_start_playback_already_playing(self):
        """Test starting playback when already playing."""
        sink = DiscordAudioSink(123456789, 987654321)

        await sink.start_playback()
        await sink.start_playback()  # Should not raise exception

        assert sink.is_playing()

    @pytest.mark.asyncio
    async def test_stop_playback(self):
        """Test stopping audio playback."""
        sink = DiscordAudioSink(123456789, 987654321)

        await sink.start_playback()
        await sink.stop_playback()

        assert not sink.is_playing()
        assert sink.get_current_audio_url() is None

    @pytest.mark.asyncio
    async def test_stop_playback_not_playing(self):
        """Test stopping playback when not playing."""
        sink = DiscordAudioSink(123456789, 987654321)

        await sink.stop_playback()  # Should not raise exception

        assert not sink.is_playing()

    @pytest.mark.asyncio
    async def test_play_audio_chunk_not_playing(self):
        """Test playing audio chunk when not playing."""
        sink = DiscordAudioSink(123456789, 987654321)

        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.1,
            frames=4800,
            format="pcm",
            bit_depth=16,
        )

        # Should not raise exception
        await sink.play_audio_chunk(b"test_audio_data", metadata)

    @pytest.mark.asyncio
    async def test_play_audio_chunk_playing(self):
        """Test playing audio chunk when playing."""
        sink = DiscordAudioSink(123456789, 987654321)

        await sink.start_playback()

        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.1,
            frames=4800,
            format="pcm",
            bit_depth=16,
        )

        # Should not raise exception
        await sink.play_audio_chunk(b"test_audio_data", metadata)

        assert sink._last_playback_time > 0

    @pytest.mark.asyncio
    async def test_play_audio_chunk_handlers(self):
        """Test that playback handlers are called."""
        sink = DiscordAudioSink(123456789, 987654321)

        handler = Mock()
        sink.register_playback_handler(handler)

        await sink.start_playback()

        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.1,
            frames=4800,
            format="pcm",
            bit_depth=16,
        )

        await sink.play_audio_chunk(b"test_audio_data", metadata)

        # Should be called for start_playback and audio_chunk_played
        assert handler.call_count >= 2

    @pytest.mark.asyncio
    async def test_play_audio_chunk_multiple_handlers(self):
        """Test that multiple playback handlers are called."""
        sink = DiscordAudioSink(123456789, 987654321)

        handler1 = Mock()
        handler2 = Mock()
        sink.register_playback_handler(handler1)
        sink.register_playback_handler(handler2)

        await sink.start_playback()

        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.1,
            frames=4800,
            format="pcm",
            bit_depth=16,
        )

        await sink.play_audio_chunk(b"test_audio_data", metadata)

        # Both handlers should be called
        assert handler1.call_count >= 2
        assert handler2.call_count >= 2

    @pytest.mark.asyncio
    async def test_play_audio_chunk_handler_exception(self):
        """Test that handler exceptions don't break audio playback."""
        sink = DiscordAudioSink(123456789, 987654321)

        def failing_handler(event: str, data: Any) -> None:
            raise ValueError("Handler failed")

        handler = Mock()
        sink.register_playback_handler(failing_handler)
        sink.register_playback_handler(handler)

        await sink.start_playback()

        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.1,
            frames=4800,
            format="pcm",
            bit_depth=16,
        )

        # Should not raise exception
        await sink.play_audio_chunk(b"test_audio_data", metadata)

        handler.assert_called()

    @pytest.mark.asyncio
    async def test_play_audio_from_url(self):
        """Test playing audio from URL."""
        sink = DiscordAudioSink(123456789, 987654321)

        audio_url = "https://example.com/audio.wav"
        success = await sink.play_audio_from_url(audio_url)

        assert success is True
        assert sink.is_playing()
        assert sink.get_current_audio_url() == audio_url
        assert sink._total_playback_requests == 1

    @pytest.mark.asyncio
    async def test_play_audio_from_url_already_playing(self):
        """Test playing audio from URL when already playing."""
        sink = DiscordAudioSink(123456789, 987654321)

        await sink.start_playback()
        audio_url = "https://example.com/audio.wav"
        success = await sink.play_audio_from_url(audio_url)

        assert success is True
        assert sink.is_playing()
        assert sink.get_current_audio_url() == audio_url

    @pytest.mark.asyncio
    async def test_pause_playback(self):
        """Test pausing audio playback."""
        sink = DiscordAudioSink(123456789, 987654321)

        await sink.start_playback()
        await sink.pause_playback()

        # Should not raise exception
        assert sink.is_playing()  # Still playing, just paused

    @pytest.mark.asyncio
    async def test_pause_playback_not_playing(self):
        """Test pausing playback when not playing."""
        sink = DiscordAudioSink(123456789, 987654321)

        await sink.pause_playback()  # Should not raise exception

    @pytest.mark.asyncio
    async def test_resume_playback(self):
        """Test resuming audio playback."""
        sink = DiscordAudioSink(123456789, 987654321)

        await sink.start_playback()
        await sink.resume_playback()

        # Should not raise exception
        assert sink.is_playing()

    @pytest.mark.asyncio
    async def test_resume_playback_not_playing(self):
        """Test resuming playback when not playing."""
        sink = DiscordAudioSink(123456789, 987654321)

        await sink.resume_playback()  # Should not raise exception

    @pytest.mark.asyncio
    async def test_playback_handlers_start_stop(self):
        """Test that handlers are called for start/stop events."""
        sink = DiscordAudioSink(123456789, 987654321)

        handler = Mock()
        sink.register_playback_handler(handler)

        await sink.start_playback()
        await sink.stop_playback()

        # Should be called for start and stop
        assert handler.call_count >= 2

        # Check that start and stop events were called
        events = [call[0][0] for call in handler.call_args_list]
        assert "playback_started" in events
        assert "playback_stopped" in events

    @pytest.mark.asyncio
    async def test_playback_handlers_url_events(self):
        """Test that handlers are called for URL playback events."""
        sink = DiscordAudioSink(123456789, 987654321)

        handler = Mock()
        sink.register_playback_handler(handler)

        audio_url = "https://example.com/audio.wav"
        await sink.play_audio_from_url(audio_url)

        # Should be called for start and URL playback
        assert handler.call_count >= 2

        # Check that URL playback event was called
        events = [call[0][0] for call in handler.call_args_list]
        assert "audio_url_playback_started" in events

    def test_playback_stats_after_playback(self):
        """Test playback stats after playing audio."""
        sink = DiscordAudioSink(123456789, 987654321)

        # Simulate some playback
        sink._total_audio_played = 5.0
        sink._total_playback_requests = 3
        sink._last_playback_time = time.time()
        sink._playback_start_time = time.time() - 10.0

        stats = sink.get_playback_stats()

        assert stats["total_audio_played"] == 5.0
        assert stats["total_playback_requests"] == 3
        assert stats["last_playback_time"] > 0
        assert stats["playback_start_time"] > 0

    @pytest.mark.asyncio
    async def test_playback_duration_tracking(self):
        """Test that playback duration is tracked correctly."""
        sink = DiscordAudioSink(123456789, 987654321)

        await sink.start_playback()

        # Wait a bit
        await asyncio.sleep(0.1)

        await sink.stop_playback()

        # Check that duration was tracked
        assert sink._total_audio_played > 0
        assert sink._total_audio_played >= 0.1
