"""
Tests for Discord SurfaceLifecycle adapter.

This module contains unit tests for the DiscordSurfaceLifecycle class,
validating its implementation of the SurfaceLifecycle interface and
connection management functionality.
"""

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from services.common.surfaces.config import SurfaceStatus, SurfaceType
from services.discord.adapters.discord_lifecycle import DiscordSurfaceLifecycle


class TestDiscordSurfaceLifecycle:
    """Test cases for DiscordSurfaceLifecycle."""

    @pytest.mark.component
    def test_initialization(self):
        """Test DiscordSurfaceLifecycle initialization."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)

        assert lifecycle.guild_id == 123456789
        assert lifecycle.channel_id == 987654321
        assert lifecycle.user_id == 555666777
        assert not lifecycle.is_connected()
        assert lifecycle._surface_config.surface_id == "discord_123456789_987654321"
        assert lifecycle._surface_config.surface_type == SurfaceType.DISCORD
        assert lifecycle._surface_config.status == SurfaceStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)

        result = await lifecycle.connect()

        assert result is True
        assert lifecycle.is_connected()
        assert lifecycle._connection_start_time is not None
        assert lifecycle._last_heartbeat is not None
        assert lifecycle._reconnect_attempts == 0
        assert lifecycle._surface_config.status == SurfaceStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure handling."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)

        # Mock connection failure
        async def mock_connect():
            raise ValueError("Connection failed")

        with patch.object(lifecycle, "connect", side_effect=mock_connect):
            result = await lifecycle.connect()

        assert result is False
        assert not lifecycle.is_connected()
        assert lifecycle._surface_config.status == SurfaceStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_disconnect_success(self):
        """Test successful disconnection."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)

        # Connect first
        await lifecycle.connect()
        assert lifecycle.is_connected()

        # Disconnect
        result = await lifecycle.disconnect()

        assert result is True
        assert not lifecycle.is_connected()
        assert lifecycle._surface_config.status == SurfaceStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_disconnect_failure(self):
        """Test disconnection failure handling."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)

        # Connect first
        await lifecycle.connect()

        # Mock disconnection failure
        async def mock_disconnect():
            raise ValueError("Disconnection failed")

        with patch.object(lifecycle, "disconnect", side_effect=mock_disconnect):
            result = await lifecycle.disconnect()

        assert result is False

    @pytest.mark.asyncio
    async def test_reconnect_success(self):
        """Test successful reconnection."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)

        # Connect first
        await lifecycle.connect()
        assert lifecycle.is_connected()

        # Disconnect
        await lifecycle.disconnect()
        assert not lifecycle.is_connected()

        # Reconnect
        result = await lifecycle.reconnect()

        assert result is True
        assert lifecycle.is_connected()
        assert lifecycle._reconnect_attempts == 1

    @pytest.mark.asyncio
    async def test_reconnect_max_attempts(self):
        """Test reconnection with max attempts exceeded."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)
        lifecycle._max_reconnect_attempts = 2
        lifecycle._reconnect_attempts = 2

        result = await lifecycle.reconnect()

        assert result is False

    @pytest.mark.component
    def test_get_connection_info(self):
        """Test getting connection information."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)

        info = lifecycle.get_connection_info()

        assert info["surface_id"] == "discord_123456789_987654321"
        assert info["guild_id"] == 123456789
        assert info["channel_id"] == 987654321
        assert info["user_id"] == 555666777
        assert info["is_connected"] is False
        assert info["status"] == SurfaceStatus.DISCONNECTED.value

    @pytest.mark.component
    def test_get_surface_config(self):
        """Test getting surface configuration."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)

        config = lifecycle.get_surface_config()

        assert config.surface_id == "discord_123456789_987654321"
        assert config.surface_type.value == "discord"
        assert config.display_name == "Discord Voice Channel 987654321"
        assert config.capabilities.supports_audio_input
        assert config.capabilities.supports_audio_output
        assert config.capabilities.supports_wake_detection

    @pytest.mark.asyncio
    async def test_register_lifecycle_handler(self):
        """Test registering lifecycle handler."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)

        handler_called = False

        async def test_handler(event: dict[str, Any]) -> None:
            nonlocal handler_called
            handler_called = True

        await lifecycle.register_lifecycle_handler("test_event", test_handler)

        assert "test_event" in lifecycle._lifecycle_handlers
        assert lifecycle._lifecycle_handlers["test_event"] == test_handler

    @pytest.mark.asyncio
    async def test_emit_lifecycle_event_with_handler(self):
        """Test emitting lifecycle event with registered handler."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)

        handler_called = False
        received_event = None

        async def test_handler(event: dict[str, Any]) -> None:
            nonlocal handler_called, received_event
            handler_called = True
            received_event = event

        await lifecycle.register_lifecycle_handler("test_event", test_handler)

        test_event = {"event_type": "test_event", "data": "test_data"}
        await lifecycle._emit_lifecycle_event(test_event)

        assert handler_called is True
        assert received_event == test_event

    @pytest.mark.asyncio
    async def test_emit_lifecycle_event_without_handler(self):
        """Test emitting lifecycle event without registered handler."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)

        # Should not raise exception
        test_event = {"event_type": "unknown_event", "data": "test_data"}
        await lifecycle._emit_lifecycle_event(test_event)

    @pytest.mark.asyncio
    async def test_health_monitoring(self):
        """Test health monitoring functionality."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)
        lifecycle._health_check_interval = 0.1  # Fast for testing

        # Connect to start health monitoring
        await lifecycle.connect()
        assert lifecycle._health_check_task is not None

        # Wait for health check
        await asyncio.sleep(0.2)

        # Disconnect to stop health monitoring
        await lifecycle.disconnect()
        assert lifecycle._health_check_task is None or lifecycle._health_check_task.done()

    @pytest.mark.asyncio
    async def test_update_heartbeat(self):
        """Test heartbeat update functionality."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)

        initial_heartbeat = lifecycle._last_heartbeat
        await lifecycle.update_heartbeat()

        assert lifecycle._last_heartbeat is not None
        assert lifecycle._last_heartbeat != initial_heartbeat

    @pytest.mark.asyncio
    async def test_get_connection_metrics(self):
        """Test getting connection metrics."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)

        # Get metrics before connection
        metrics = await lifecycle.get_connection_metrics()

        assert metrics["is_connected"] is False
        assert metrics["uptime_seconds"] is None
        assert metrics["reconnect_attempts"] == 0
        assert metrics["last_heartbeat"] is None

        # Connect and get metrics
        await lifecycle.connect()
        metrics = await lifecycle.get_connection_metrics()

        assert metrics["is_connected"] is True
        assert metrics["uptime_seconds"] is not None
        assert metrics["reconnect_attempts"] == 0
        assert metrics["last_heartbeat"] is not None
        assert metrics["health_check_interval"] == 30.0
        assert metrics["connection_timeout"] == 60.0

    @pytest.mark.asyncio
    async def test_connection_timeout_handling(self):
        """Test connection timeout handling."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)
        lifecycle._connection_timeout = 0.1  # Short timeout for testing
        lifecycle._health_check_interval = 0.05  # Fast health checks

        # Connect
        await lifecycle.connect()
        assert lifecycle.is_connected()

        # Wait for timeout
        await asyncio.sleep(0.2)

        # Connection should be reconnected due to timeout
        assert lifecycle.is_connected()
        assert lifecycle._reconnect_attempts > 0

    @pytest.mark.asyncio
    async def test_lifecycle_event_handling(self):
        """Test lifecycle event handling during connection."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)

        events_received = []

        async def event_handler(event: dict[str, Any]) -> None:
            events_received.append(event)

        await lifecycle.register_lifecycle_handler("connection.established", event_handler)
        await lifecycle.register_lifecycle_handler("connection.closed", event_handler)

        # Connect and disconnect
        await lifecycle.connect()
        await lifecycle.disconnect()

        # Should have received connection events
        assert len(events_received) >= 2
        assert any(event.get("event_type") == "connection.established" for event in events_received)
        assert any(event.get("event_type") == "connection.closed" for event in events_received)

    @pytest.mark.asyncio
    async def test_error_event_handling(self):
        """Test error event handling during connection failure."""
        lifecycle = DiscordSurfaceLifecycle(123456789, 987654321, 555666777)

        error_events = []

        async def error_handler(event: dict[str, Any]) -> None:
            error_events.append(event)

        await lifecycle.register_lifecycle_handler("error", error_handler)

        # Mock connection failure
        async def mock_connect():
            raise ValueError("Connection failed")

        with patch.object(lifecycle, "connect", side_effect=mock_connect):
            # Attempt connection
            result = await lifecycle.connect()

        assert result is False
        assert len(error_events) > 0
        assert any(event.get("code") == "CONNECTION_FAILED" for event in error_events)
