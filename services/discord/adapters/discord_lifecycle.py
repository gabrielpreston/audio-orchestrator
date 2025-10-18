"""
Discord SurfaceLifecycle adapter implementation.

This module provides the Discord-specific implementation of the SurfaceLifecycle
interface, handling connection management, authentication, and lifecycle events
for Discord voice channels.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from services.common.surfaces.config import SurfaceConfig, SurfaceStatus, SurfaceType
from services.common.surfaces.events import ConnectionEvent, ErrorEvent
from services.common.surfaces.interfaces import SurfaceLifecycle

logger = logging.getLogger(__name__)


class DiscordSurfaceLifecycle(SurfaceLifecycle):
    """
    Discord implementation of SurfaceLifecycle interface.

    Manages Discord voice connection lifecycle including:
    - Voice channel connection/disconnection
    - Authentication and permissions
    - Connection health monitoring
    - Automatic reconnection
    """

    def __init__(self, guild_id: int, channel_id: int, user_id: int):
        """
        Initialize Discord surface lifecycle manager.

        Args:
            guild_id: Discord guild (server) ID
            channel_id: Discord voice channel ID
            user_id: Discord user ID for authentication
        """
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.user_id = user_id

        # Connection state
        self._is_connected = False
        self._connection_start_time: datetime | None = None
        self._last_heartbeat: datetime | None = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5

        # Event handlers
        self._lifecycle_handlers: dict[
            str, Callable[[dict[str, Any]], Awaitable[None]]
        ] = {}

        # Health monitoring
        self._health_check_interval = 30.0  # seconds
        self._health_check_task: asyncio.Task[None] | None = None
        self._connection_timeout = 60.0  # seconds

        # Surface configuration
        self._surface_config = SurfaceConfig(
            surface_id=f"discord_{guild_id}_{channel_id}",
            surface_type=SurfaceType.DISCORD,
            display_name=f"Discord Voice Channel {channel_id}",
            status=SurfaceStatus.DISCONNECTED,
            config={"guild_id": guild_id, "channel_id": channel_id, "user_id": user_id},
        )

    async def connect(self) -> bool:
        """
        Establish connection to Discord voice channel.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info("Connecting to Discord voice channel %s", self.channel_id)

            # Simulate connection process
            await asyncio.sleep(0.1)  # Simulate connection delay

            self._is_connected = True
            self._connection_start_time = datetime.now()
            self._last_heartbeat = datetime.now()
            self._reconnect_attempts = 0

            # Update surface status
            self._surface_config.status = SurfaceStatus.CONNECTED

            # Start health monitoring
            self._start_health_monitoring()

            # Emit connection event
            connection_event = ConnectionEvent(
                event_type="connection.established",
                surface_id=self._surface_config.surface_id,
                timestamp=datetime.now().timestamp(),
                connection_params=self._surface_config.config,
            )
            await self._emit_lifecycle_event(connection_event.to_dict())

            logger.info(
                "Successfully connected to Discord voice channel %s", self.channel_id
            )
            return True

        except (ValueError, TypeError, OSError) as e:
            logger.error("Failed to connect to Discord voice channel: %s", e)
            error_event = ErrorEvent(
                event_type="error",
                code="CONNECTION_FAILED",
                message=f"Failed to connect to Discord voice channel: {e}",
                recoverable=True,
            )
            await self._emit_lifecycle_event(error_event.to_dict())
            return False

    async def disconnect(self) -> bool:
        """
        Disconnect from Discord voice channel.

        Returns:
            True if disconnection successful, False otherwise
        """
        try:
            logger.info("Disconnecting from Discord voice channel %s", self.channel_id)

            # Stop health monitoring
            self._stop_health_monitoring()

            # Update state
            self._is_connected = False
            self._surface_config.status = SurfaceStatus.DISCONNECTED

            # Emit disconnection event
            disconnect_event = ConnectionEvent(
                event_type="connection.closed",
                surface_id=self._surface_config.surface_id,
                timestamp=datetime.now().timestamp(),
                connection_params=self._surface_config.config,
            )
            await self._emit_lifecycle_event(disconnect_event.to_dict())

            logger.info(
                "Successfully disconnected from Discord voice channel %s",
                self.channel_id,
            )
            return True

        except (ValueError, TypeError, OSError) as e:
            logger.error("Failed to disconnect from Discord voice channel: %s", e)
            return False

    async def reconnect(self) -> bool:
        """
        Attempt to reconnect to Discord voice channel.

        Returns:
            True if reconnection successful, False otherwise
        """
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(
                "Max reconnection attempts (%s) exceeded", self._max_reconnect_attempts
            )
            return False

        self._reconnect_attempts += 1
        logger.info(
            "Attempting reconnection %s/%s",
            self._reconnect_attempts,
            self._max_reconnect_attempts,
        )

        # Disconnect first
        await self.disconnect()

        # Wait before reconnecting
        await asyncio.sleep(2.0)

        # Attempt reconnection
        return await self.connect()

    def is_connected(self) -> bool:
        """Check if currently connected to Discord voice channel."""
        return self._is_connected

    def get_connection_info(self) -> dict[str, Any]:
        """
        Get current connection information.

        Returns:
            Dictionary containing connection details
        """
        return {
            "surface_id": self._surface_config.surface_id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "user_id": self.user_id,
            "is_connected": self._is_connected,
            "connection_start_time": (
                self._connection_start_time.isoformat()
                if self._connection_start_time
                else None
            ),
            "last_heartbeat": (
                self._last_heartbeat.isoformat() if self._last_heartbeat else None
            ),
            "reconnect_attempts": self._reconnect_attempts,
            "status": self._surface_config.status.value,
        }

    def get_surface_config(self) -> SurfaceConfig:
        """Get surface configuration."""
        return self._surface_config

    async def get_telemetry(self) -> dict[str, Any]:
        """Get telemetry data."""
        return {
            "surface_id": self._surface_config.surface_id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "user_id": self.user_id,
            "is_connected": self._is_connected,
            "connection_start_time": (
                self._connection_start_time.isoformat()
                if self._connection_start_time
                else None
            ),
            "last_heartbeat": (
                self._last_heartbeat.isoformat() if self._last_heartbeat else None
            ),
            "reconnect_attempts": self._reconnect_attempts,
            "status": self._surface_config.status.value,
        }

    async def register_lifecycle_handler(
        self, event_type: str, handler: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        Register handler for lifecycle events.

        Args:
            event_type: Type of event to handle
            handler: Async function to handle the event
        """
        self._lifecycle_handlers[event_type] = handler
        logger.debug("Registered lifecycle handler for %s", event_type)

    async def _emit_lifecycle_event(self, event: dict[str, Any]) -> None:
        """
        Emit lifecycle event to registered handlers.

        Args:
            event: Event data to emit
        """
        event_type = event.get("event_type", "unknown")

        if event_type in self._lifecycle_handlers:
            try:
                await self._lifecycle_handlers[event_type](event)
            except (ValueError, TypeError, KeyError) as e:
                logger.error("Error in lifecycle handler for %s: %s", event_type, e)
        else:
            logger.debug("No handler registered for lifecycle event: %s", event_type)

    def _start_health_monitoring(self) -> None:
        """Start health monitoring task."""
        if self._health_check_task is None or self._health_check_task.done():
            self._health_check_task = asyncio.create_task(self._health_monitor())

    def _stop_health_monitoring(self) -> None:
        """Stop health monitoring task."""
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()

    async def _health_monitor(self) -> None:
        """Monitor connection health and handle reconnection."""
        try:
            while self._is_connected:
                await asyncio.sleep(self._health_check_interval)

                # Check if heartbeat is recent
                if self._last_heartbeat:
                    time_since_heartbeat = datetime.now() - self._last_heartbeat
                    if time_since_heartbeat.total_seconds() > self._connection_timeout:
                        logger.warning(
                            "Connection timeout detected, attempting reconnection"
                        )
                        await self.reconnect()
                        break

                # Simulate heartbeat
                self._last_heartbeat = datetime.now()

        except asyncio.CancelledError:
            logger.debug("Health monitoring cancelled")
        except (ValueError, TypeError, OSError) as e:
            logger.error("Error in health monitoring: %s", e)

    async def update_heartbeat(self) -> None:
        """Update connection heartbeat timestamp."""
        self._last_heartbeat = datetime.now()
        logger.debug("Heartbeat updated")

    async def get_connection_metrics(self) -> dict[str, Any]:
        """
        Get connection metrics and statistics.

        Returns:
            Dictionary containing connection metrics
        """
        uptime = None
        if self._connection_start_time:
            uptime = (datetime.now() - self._connection_start_time).total_seconds()

        return {
            "is_connected": self._is_connected,
            "uptime_seconds": uptime,
            "reconnect_attempts": self._reconnect_attempts,
            "last_heartbeat": (
                self._last_heartbeat.isoformat() if self._last_heartbeat else None
            ),
            "health_check_interval": self._health_check_interval,
            "connection_timeout": self._connection_timeout,
        }

    async def prepare(self) -> bool:
        """
        Prepare the surface for use.

        Returns:
            True if preparation successful, False otherwise
        """
        try:
            logger.info("Preparing Discord surface for use")
            # Surface is ready when connected
            return self._is_connected
        except (ValueError, TypeError, OSError) as e:
            logger.error("Failed to prepare Discord surface: %s", e)
            return False

    async def publish(self, data: dict[str, Any]) -> bool:
        """
        Publish an event to the surface.

        Args:
            event: Event data to publish

        Returns:
            True if publish successful, False otherwise
        """
        try:
            await self._emit_lifecycle_event(data)
            return True
        except (ValueError, TypeError, KeyError) as e:
            logger.error("Failed to publish event: %s", e)
            return False

    async def subscribe(self, callback: Callable[[Any], None]) -> None:
        """
        Subscribe to surface events.

        Args:
            callback: Handler function for events
        """
        try:
            # Register a generic handler that calls the callback
            async def generic_handler(event: dict[str, Any]) -> None:
                callback(event)

            await self.register_lifecycle_handler("all_events", generic_handler)
        except (ValueError, TypeError, KeyError) as e:
            logger.error("Failed to subscribe to events: %s", e)
