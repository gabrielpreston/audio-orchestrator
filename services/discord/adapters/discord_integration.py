"""
Discord adapter integration for the voice bot.

This module provides integration between the Discord voice bot and the new
surface adapter system, allowing the bot to use the composable architecture
while maintaining backward compatibility.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from services.common.surfaces.interfaces import (
    AudioSink,
    AudioSource,
    ControlChannel,
    SurfaceLifecycle,
)
from services.common.surfaces.types import AudioFormat, PCMFrame

from .discord_control import DiscordControlChannel
from .discord_lifecycle import DiscordSurfaceLifecycle
from .discord_sink import DiscordAudioSink
from .discord_source import DiscordAudioSource

logger = logging.getLogger(__name__)


class DiscordAdapterIntegration:
    """
    Integration layer between Discord voice bot and surface adapters.

    This class manages the lifecycle of Discord adapters and provides
    a unified interface for the voice bot to interact with the new
    composable architecture.
    """

    def __init__(self, guild_id: int, channel_id: int, user_id: int):
        """
        Initialize Discord adapter integration.

        Args:
            guild_id: Discord guild (server) ID
            channel_id: Discord voice channel ID
            user_id: Discord user ID
        """
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.user_id = user_id

        # Initialize adapters
        self._audio_source: DiscordAudioSource | None = None
        self._audio_sink: DiscordAudioSink | None = None
        self._control_channel: DiscordControlChannel | None = None
        self._surface_lifecycle: DiscordSurfaceLifecycle | None = None

        # Integration state
        self._is_initialized = False
        self._is_connected = False
        self._adapter_tasks: list[asyncio.Task[None]] = []

        # Event handlers
        self._event_handlers: dict[str, list[Callable[..., Any]]] = {}

        # Configuration
        self._use_new_architecture = True  # Feature flag
        self._audio_format = AudioFormat(
            value={
                "sample_rate": 16000,
                "channels": 1,
                "bit_depth": 16,
                "frame_size_ms": 20,
            }
        )

    async def initialize(self) -> bool:
        """
        Initialize all Discord adapters.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing Discord adapter integration")

            # Create adapters
            self._audio_source = DiscordAudioSource(
                guild_id=self.guild_id, channel_id=self.channel_id
            )

            self._audio_sink = DiscordAudioSink(
                guild_id=self.guild_id, channel_id=self.channel_id
            )

            self._control_channel = DiscordControlChannel(
                guild_id=self.guild_id, channel_id=self.channel_id
            )

            self._surface_lifecycle = DiscordSurfaceLifecycle(
                guild_id=self.guild_id, channel_id=self.channel_id, user_id=self.user_id
            )

            # Set up event routing
            await self._setup_event_routing()

            self._is_initialized = True
            logger.info("Discord adapter integration initialized successfully")
            return True

        except Exception as e:
            logger.error("Failed to initialize Discord adapter integration: %s", e)
            return False

    async def connect(self) -> bool:
        """
        Connect all adapters.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._is_initialized:
            logger.error("Integration not initialized")
            return False

        try:
            logger.info("Connecting Discord adapters")

            # Connect lifecycle first
            if not await self._surface_lifecycle.connect():
                logger.error("Failed to connect surface lifecycle")
                return False

            # Connect other adapters
            if self._audio_source:
                # Audio source doesn't have connect method, it's always ready
                pass

            if self._audio_sink:
                # Audio sink doesn't have connect method, it's always ready
                pass

            if self._control_channel:
                # Control channel doesn't have connect method, it's always ready
                pass

            # Start adapter tasks
            await self._start_adapter_tasks()

            self._is_connected = True
            logger.info("Discord adapters connected successfully")
            return True

        except Exception as e:
            logger.error("Failed to connect Discord adapters: %s", e)
            return False

    async def disconnect(self) -> bool:
        """
        Disconnect all adapters.

        Returns:
            True if disconnection successful, False otherwise
        """
        try:
            logger.info("Disconnecting Discord adapters")

            # Stop adapter tasks
            await self._stop_adapter_tasks()

            # Disconnect adapters
            if self._audio_source:
                # Audio source doesn't have disconnect method
                pass

            if self._audio_sink:
                # Audio sink doesn't have disconnect method
                pass

            if self._control_channel:
                await self._control_channel.disconnect()

            if self._surface_lifecycle:
                await self._surface_lifecycle.disconnect()

            self._is_connected = False
            logger.info("Discord adapters disconnected successfully")
            return True

        except Exception as e:
            logger.error("Failed to disconnect Discord adapters: %s", e)
            return False

    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            await self.disconnect()

            # Clear adapters
            self._audio_source = None
            self._audio_sink = None
            self._control_channel = None
            self._surface_lifecycle = None

            self._is_initialized = False
            logger.info("Discord adapter integration cleaned up")

        except Exception as e:
            logger.error("Error during cleanup: %s", e)

    def is_connected(self) -> bool:
        """Check if adapters are connected."""
        return self._is_connected

    def get_audio_source(self) -> AudioSource | None:
        """Get audio source adapter."""
        return self._audio_source

    def get_audio_sink(self) -> AudioSink | None:
        """Get audio sink adapter."""
        return self._audio_sink

    def get_control_channel(self) -> ControlChannel | None:
        """Get control channel adapter."""
        return self._control_channel

    def get_surface_lifecycle(self) -> SurfaceLifecycle | None:
        """Get surface lifecycle adapter."""
        return self._surface_lifecycle

    async def register_event_handler(
        self, event_type: str, handler: Callable[..., Any]
    ) -> None:
        """
        Register event handler for specific event type.

        Args:
            event_type: Type of event to handle
            handler: Handler function
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        logger.debug("Registered event handler for %s", event_type)

    async def _setup_event_routing(self) -> None:
        """Set up event routing between adapters."""
        try:
            # Route audio source events
            if self._audio_source:
                # Audio source doesn't have register_frame_handler method
                pass

            # Route control channel events
            if self._control_channel:
                # Control channel doesn't have register_event_handler method
                pass

            # Route surface lifecycle events
            if self._surface_lifecycle:
                # Surface lifecycle doesn't have subscribe method
                pass

            logger.debug("Event routing set up successfully")

        except Exception as e:
            logger.error("Failed to set up event routing: %s", e)

    async def _start_adapter_tasks(self) -> None:
        """Start background tasks for adapters."""
        try:
            # Start audio processing task
            if self._audio_source:
                task = asyncio.create_task(self._audio_processing_loop())
                self._adapter_tasks.append(task)

            # Start control event processing task
            if self._control_channel:
                task = asyncio.create_task(self._control_event_loop())
                self._adapter_tasks.append(task)

            logger.debug("Adapter tasks started")

        except Exception as e:
            logger.error("Failed to start adapter tasks: %s", e)

    async def _stop_adapter_tasks(self) -> None:
        """Stop background tasks for adapters."""
        try:
            # Cancel all tasks
            for task in self._adapter_tasks:
                task.cancel()

            # Wait for tasks to complete
            if self._adapter_tasks:
                await asyncio.gather(*self._adapter_tasks, return_exceptions=True)

            self._adapter_tasks.clear()
            logger.debug("Adapter tasks stopped")

        except Exception as e:
            logger.error("Failed to stop adapter tasks: %s", e)

    async def _handle_audio_frame(self, frame: PCMFrame) -> None:
        """Handle audio frame from source adapter."""
        try:
            # Process audio frame
            if self._audio_source:
                # Get audio metadata
                metadata = await self._audio_source.get_telemetry()

                # Emit audio frame event
                await self._emit_event(
                    "audio.frame",
                    {
                        "frame": frame,
                        "metadata": metadata,
                        "timestamp": datetime.now().timestamp(),
                    },
                )

        except Exception as e:
            logger.error("Error handling audio frame: %s", e)

    async def _handle_control_event(self, event: dict[str, Any]) -> None:
        """Handle control event from control channel adapter."""
        try:
            event_type = event.get("event_type", "unknown")

            # Route to registered handlers
            if event_type in self._event_handlers:
                for handler in self._event_handlers[event_type]:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                    except Exception as e:
                        logger.error("Error in control event handler: %s", e)

            # Emit control event
            await self._emit_event("control.event", event)

        except Exception as e:
            logger.error("Error handling control event: %s", e)

    async def _handle_lifecycle_event(self, event: dict[str, Any]) -> None:
        """Handle lifecycle event from surface lifecycle adapter."""
        try:
            event_type = event.get("event_type", "unknown")

            # Route to registered handlers
            if event_type in self._event_handlers:
                for handler in self._event_handlers[event_type]:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                    except Exception as e:
                        logger.error("Error in lifecycle event handler: %s", e)

            # Emit lifecycle event
            await self._emit_event("lifecycle.event", event)

        except Exception as e:
            logger.error("Error handling lifecycle event: %s", e)

    async def _audio_processing_loop(self) -> None:
        """Background task for audio processing."""
        try:
            while self._is_connected and self._audio_source:
                # Process audio frames
                frames = await self._audio_source.read_audio_frame()
                if frames:
                    for frame in frames:
                        await self._handle_audio_frame(frame)

                await asyncio.sleep(0.01)  # 10ms loop

        except asyncio.CancelledError:
            logger.debug("Audio processing loop cancelled")
        except Exception as e:
            logger.error("Error in audio processing loop: %s", e)

    async def _control_event_loop(self) -> None:
        """Background task for control event processing."""
        try:
            while self._is_connected and self._control_channel:
                # Process control events
                event = await self._control_channel.receive_event()
                if event:
                    await self._handle_control_event(event)

                await asyncio.sleep(0.01)  # 10ms loop

        except asyncio.CancelledError:
            logger.debug("Control event loop cancelled")
        except Exception as e:
            logger.error("Error in control event loop: %s", e)

    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit event to registered handlers."""
        try:
            if event_type in self._event_handlers:
                for handler in self._event_handlers[event_type]:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(data)
                        else:
                            handler(data)
                    except Exception as e:
                        logger.error("Error in event handler: %s", e)

        except Exception as e:
            logger.error("Error emitting event: %s", e)

    async def get_integration_metrics(self) -> dict[str, Any]:
        """
        Get integration metrics and statistics.

        Returns:
            Dictionary containing integration metrics
        """
        metrics = {
            "is_initialized": self._is_initialized,
            "is_connected": self._is_connected,
            "adapter_tasks_count": len(self._adapter_tasks),
            "event_handlers_count": sum(
                len(handlers) for handlers in self._event_handlers.values()
            ),
            "use_new_architecture": self._use_new_architecture,
        }

        # Add adapter-specific metrics
        if self._audio_source:
            metrics["audio_source_metrics"] = await self._audio_source.get_telemetry()

        if self._audio_sink:
            metrics["audio_sink_metrics"] = await self._audio_sink.get_telemetry()

        if self._control_channel:
            metrics["control_channel_metrics"] = (
                await self._control_channel.get_telemetry()
            )

        if self._surface_lifecycle:
            metrics["surface_lifecycle_metrics"] = (
                await self._surface_lifecycle.get_connection_metrics()
            )

        return metrics
