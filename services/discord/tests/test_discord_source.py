"""
Tests for Discord audio source adapter.

This module validates that the Discord audio source correctly implements
the AudioSource interface and handles audio capture properly.
"""

import time
from unittest.mock import Mock, patch

import pytest

from services.common.surfaces.media_gateway import MediaGateway
from services.common.surfaces.types import AudioFormat, PCMFrame
from services.discord.adapters.discord_source import DiscordAudioSource


class TestDiscordAudioSource:
    """Test DiscordAudioSource functionality."""

    @pytest.mark.component
    def test_discord_audio_source_creation(self):
        """Test creating DiscordAudioSource with basic parameters."""
        source = DiscordAudioSource(
            guild_id=123456789,
            channel_id=987654321,
        )

        assert source.guild_id == 123456789
        assert source.channel_id == 987654321
        assert source.user_id is None
        assert source.media_gateway is not None
        assert not source.is_capturing()
        assert source.get_buffer_size() == 0

    @pytest.mark.component
    def test_discord_audio_source_creation_with_user(self):
        """Test creating DiscordAudioSource with user filter."""
        source = DiscordAudioSource(
            guild_id=123456789,
            channel_id=987654321,
            user_id=555666777,
        )

        assert source.guild_id == 123456789
        assert source.channel_id == 987654321
        assert source.user_id == 555666777

    @pytest.mark.component
    def test_discord_audio_source_creation_with_media_gateway(self):
        """Test creating DiscordAudioSource with custom media gateway."""
        media_gateway = MediaGateway()
        source = DiscordAudioSource(
            guild_id=123456789,
            channel_id=987654321,
            media_gateway=media_gateway,
        )

        assert source.media_gateway is media_gateway

    @pytest.mark.component
    def test_get_metadata(self):
        """Test getting audio metadata."""
        source = DiscordAudioSource(123456789, 987654321)
        metadata = source.get_metadata()

        assert metadata.sample_rate == 48000
        assert metadata.channels == 2
        assert metadata.sample_width == 2
        assert metadata.bit_depth == 16
        assert metadata.format == AudioFormat.PCM

    @pytest.mark.component
    def test_get_surface_id(self):
        """Test getting surface ID."""
        source = DiscordAudioSource(123456789, 987654321)
        surface_id = source.get_surface_id()

        assert surface_id == "discord:123456789:987654321"

    @pytest.mark.component
    def test_get_guild_id(self):
        """Test getting guild ID."""
        source = DiscordAudioSource(123456789, 987654321)
        guild_id = source.get_guild_id()

        assert guild_id == 123456789

    @pytest.mark.component
    def test_get_channel_id(self):
        """Test getting channel ID."""
        source = DiscordAudioSource(123456789, 987654321)
        channel_id = source.get_channel_id()

        assert channel_id == 987654321

    @pytest.mark.component
    def test_get_user_id(self):
        """Test getting user ID."""
        source = DiscordAudioSource(123456789, 987654321, user_id=555666777)
        user_id = source.get_user_id()

        assert user_id == 555666777

    @pytest.mark.component
    def test_get_user_id_none(self):
        """Test getting user ID when not set."""
        source = DiscordAudioSource(123456789, 987654321)
        user_id = source.get_user_id()

        assert user_id is None

    @pytest.mark.component
    def test_is_capturing_initial(self):
        """Test initial capturing state."""
        source = DiscordAudioSource(123456789, 987654321)

        assert not source.is_capturing()

    @pytest.mark.component
    def test_get_buffer_size_initial(self):
        """Test initial buffer size."""
        source = DiscordAudioSource(123456789, 987654321)

        assert source.get_buffer_size() == 0

    @pytest.mark.component
    def test_clear_buffer(self):
        """Test clearing audio buffer."""
        source = DiscordAudioSource(123456789, 987654321)

        # Add some frames to buffer (simulated)
        source._audio_buffer = [Mock(), Mock(), Mock()]

        source.clear_buffer()

        assert source.get_buffer_size() == 0

    @pytest.mark.component
    def test_register_frame_handler(self):
        """Test registering frame handler."""
        source = DiscordAudioSource(123456789, 987654321)

        handler = Mock()
        source.register_frame_handler(handler)

        assert handler in source._frame_handlers

    @pytest.mark.component
    def test_unregister_frame_handler(self):
        """Test unregistering frame handler."""
        source = DiscordAudioSource(123456789, 987654321)

        handler = Mock()
        source.register_frame_handler(handler)
        source.unregister_frame_handler(handler)

        assert handler not in source._frame_handlers

    @pytest.mark.component
    def test_unregister_frame_handler_not_registered(self):
        """Test unregistering non-registered frame handler."""
        source = DiscordAudioSource(123456789, 987654321)

        handler = Mock()
        # Don't register handler

        # Should not raise exception
        source.unregister_frame_handler(handler)

    @pytest.mark.component
    def test_set_media_gateway(self):
        """Test setting media gateway."""
        source = DiscordAudioSource(123456789, 987654321)
        new_gateway = MediaGateway()

        source.set_media_gateway(new_gateway)

        assert source.media_gateway is new_gateway

    @pytest.mark.component
    def test_get_media_gateway(self):
        """Test getting media gateway."""
        source = DiscordAudioSource(123456789, 987654321)
        gateway = source.get_media_gateway()

        assert gateway is not None
        assert isinstance(gateway, MediaGateway)

    @pytest.mark.component
    def test_get_capture_stats(self):
        """Test getting capture statistics."""
        source = DiscordAudioSource(123456789, 987654321)
        stats = source.get_capture_stats()

        assert "is_capturing" in stats
        assert "total_frames_captured" in stats
        assert "total_audio_duration" in stats
        assert "buffer_size" in stats
        assert "last_frame_time" in stats
        assert "sequence_counter" in stats

        assert stats["is_capturing"] is False
        assert stats["total_frames_captured"] == 0
        assert stats["total_audio_duration"] == 0.0
        assert stats["buffer_size"] == 0
        assert stats["sequence_counter"] == 0

    @pytest.mark.component
    def test_get_telemetry(self):
        """Test getting telemetry data."""
        source = DiscordAudioSource(123456789, 987654321, user_id=555666777)
        telemetry = source.get_telemetry()

        assert "surface_id" in telemetry
        assert "guild_id" in telemetry
        assert "channel_id" in telemetry
        assert "user_id" in telemetry
        assert "is_capturing" in telemetry
        assert "total_frames_captured" in telemetry
        assert "total_audio_duration" in telemetry
        assert "buffer_size" in telemetry
        assert "last_frame_time" in telemetry
        assert "sequence_counter" in telemetry
        assert "metadata" in telemetry

        assert telemetry["surface_id"] == "discord:123456789:987654321"
        assert telemetry["guild_id"] == 123456789
        assert telemetry["channel_id"] == 987654321
        assert telemetry["user_id"] == 555666777
        assert telemetry["is_capturing"] is False

    @pytest.mark.component
    def test_update_policy(self):
        """Test updating surface policies."""
        source = DiscordAudioSource(123456789, 987654321)

        policy_config = {
            "vad_threshold": 0.5,
            "wake_sensitivity": 0.8,
            "barge_in_enabled": True,
        }

        # Should not raise exception
        source.update_policy(policy_config)

    @pytest.mark.component
    def test_repr(self):
        """Test string representation."""
        source = DiscordAudioSource(123456789, 987654321, user_id=555666777)
        repr_str = repr(source)

        assert "DiscordAudioSource" in repr_str
        assert "guild_id=123456789" in repr_str
        assert "channel_id=987654321" in repr_str
        assert "user_id=555666777" in repr_str
        assert "capturing=False" in repr_str

    @pytest.mark.asyncio
    async def test_start_capture(self):
        """Test starting audio capture."""
        source = DiscordAudioSource(123456789, 987654321)

        await source.start_capture()

        assert source.is_capturing()
        assert source._sequence_counter == 0

    @pytest.mark.asyncio
    async def test_start_capture_already_capturing(self):
        """Test starting capture when already capturing."""
        source = DiscordAudioSource(123456789, 987654321)

        await source.start_capture()
        await source.start_capture()  # Should not raise exception

        assert source.is_capturing()

    @pytest.mark.asyncio
    async def test_stop_capture(self):
        """Test stopping audio capture."""
        source = DiscordAudioSource(123456789, 987654321)

        await source.start_capture()
        await source.stop_capture()

        assert not source.is_capturing()
        assert source.get_buffer_size() == 0

    @pytest.mark.asyncio
    async def test_stop_capture_not_capturing(self):
        """Test stopping capture when not capturing."""
        source = DiscordAudioSource(123456789, 987654321)

        await source.stop_capture()  # Should not raise exception

        assert not source.is_capturing()

    @pytest.mark.asyncio
    async def test_read_audio_frame_not_capturing(self):
        """Test reading audio frame when not capturing."""
        source = DiscordAudioSource(123456789, 987654321)

        frame = await source.read_audio_frame()

        assert frame is None

    @pytest.mark.asyncio
    async def test_read_audio_frame_capturing(self):
        """Test reading audio frame when capturing."""
        source = DiscordAudioSource(123456789, 987654321)

        await source.start_capture()
        frame = await source.read_audio_frame()

        assert frame is not None
        assert isinstance(frame, PCMFrame)
        assert frame.sample_rate == 48000
        assert frame.duration == 0.02
        assert frame.sequence == 0
        assert len(frame.pcm) > 0

    @pytest.mark.asyncio
    async def test_read_audio_frame_sequence_counter(self):
        """Test that sequence counter increments."""
        source = DiscordAudioSource(123456789, 987654321)

        await source.start_capture()

        frame1 = await source.read_audio_frame()
        frame2 = await source.read_audio_frame()

        assert frame1 is not None and frame1.sequence == 0
        assert frame2 is not None and frame2.sequence == 1

    @pytest.mark.asyncio
    async def test_read_audio_frame_handlers(self):
        """Test that frame handlers are called."""
        source = DiscordAudioSource(123456789, 987654321)

        handler = Mock()
        source.register_frame_handler(handler)

        await source.start_capture()
        await source.read_audio_frame()

        handler.assert_called_once()
        assert isinstance(handler.call_args[0][0], PCMFrame)

    @pytest.mark.asyncio
    async def test_read_audio_frame_multiple_handlers(self):
        """Test that multiple frame handlers are called."""
        source = DiscordAudioSource(123456789, 987654321)

        handler1 = Mock()
        handler2 = Mock()
        source.register_frame_handler(handler1)
        source.register_frame_handler(handler2)

        await source.start_capture()
        await source.read_audio_frame()

        handler1.assert_called_once()
        handler2.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_audio_frame_handler_exception(self):
        """Test that handler exceptions don't break frame reading."""
        source = DiscordAudioSource(123456789, 987654321)

        def failing_handler(frame):
            raise ValueError("Handler failed")

        handler = Mock()
        source.register_frame_handler(failing_handler)
        source.register_frame_handler(handler)

        await source.start_capture()
        frame = await source.read_audio_frame()

        assert frame is not None
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_audio_frame_no_media_gateway(self):
        """Test processing audio frame without media gateway."""
        source = DiscordAudioSource(123456789, 987654321)
        # Test without media gateway - temporarily set to None for testing
        source.media_gateway = None  # type: ignore[assignment]

        frame = PCMFrame(
            pcm=b"test_data",
            timestamp=time.time(),
            rms=0.5,
            duration=0.02,
            sequence=0,
            sample_rate=48000,
        )

        processed_frame = await source.process_audio_frame(frame)

        assert processed_frame is frame

    @pytest.mark.asyncio
    async def test_process_audio_frame_with_media_gateway(self):
        """Test processing audio frame with media gateway."""
        source = DiscordAudioSource(123456789, 987654321)

        frame = PCMFrame(
            pcm=b"test_data",
            timestamp=time.time(),
            rms=0.5,
            duration=0.02,
            sequence=0,
            sample_rate=48000,
        )

        processed_frame = await source.process_audio_frame(frame)

        assert processed_frame is not None
        assert isinstance(processed_frame, PCMFrame)

    @pytest.mark.asyncio
    async def test_start_capture_loop(self):
        """Test starting capture loop."""
        source = DiscordAudioSource(123456789, 987654321)

        # Mock the read_audio_frame method to return None after first call
        original_read = source.read_audio_frame
        call_count = 0

        async def mock_read():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return await original_read()
            else:
                source._is_capturing = False  # Stop the loop
                return None

        # Mock the read_audio_frame method
        with patch.object(source, "read_audio_frame", side_effect=mock_read):
            await source.start_capture_loop()

        assert call_count > 0

    @pytest.mark.asyncio
    async def test_stop_capture_loop(self):
        """Test stopping capture loop."""
        source = DiscordAudioSource(123456789, 987654321)

        await source.start_capture()
        await source.stop_capture_loop()

        assert not source.is_capturing()

    @pytest.mark.asyncio
    async def test_capture_loop_exception_handling(self):
        """Test that capture loop handles exceptions gracefully."""
        source = DiscordAudioSource(123456789, 987654321)

        # Mock read_audio_frame to raise exception
        async def failing_read():
            raise ValueError("Read failed")

        with patch.object(source, "read_audio_frame", side_effect=failing_read):
            await source.start_capture()

        # Should not raise exception
        await source.start_capture_loop()

        assert not source.is_capturing()

    @pytest.mark.component
    def test_capture_stats_after_frames(self):
        """Test capture stats after reading frames."""
        source = DiscordAudioSource(123456789, 987654321)

        # Simulate some captured frames
        source._total_frames_captured = 10
        source._total_audio_duration = 0.2
        source._last_frame_time = time.time()
        source._sequence_counter = 10

        stats = source.get_capture_stats()

        assert stats["total_frames_captured"] == 10
        assert stats["total_audio_duration"] == 0.2
        assert stats["sequence_counter"] == 10
        assert stats["last_frame_time"] > 0
