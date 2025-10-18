"""
Discord ControlChannel adapter implementation.

This module implements the ControlChannel interface for Discord voice events,
providing a standardized way to handle control events between the agent and Discord.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from services.common.logging import get_logger
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
from services.common.surfaces.interfaces import ControlChannel
from services.common.surfaces.types import (
    EndpointingState,
    PlaybackAction,
    SessionAction,
    TelemetryMetrics,
    WordTimestamp,
)

logger = get_logger(__name__)


class DiscordControlChannel(ControlChannel):
    """Discord control channel adapter implementing ControlChannel interface."""

    def __init__(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int | None = None,
    ) -> None:
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.user_id = user_id

        # Connection state
        self._is_connected = False
        self._event_handlers: list[Callable[[dict[str, Any]], None]] = []
        self._event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        # Event tracking
        self._total_events_sent = 0
        self._total_events_received = 0
        self._last_event_time = 0.0

        # Discord-specific state
        self._current_voice_state = "disconnected"
        self._current_speaking = False
        self._current_deaf = False
        self._current_mute = False

        self._logger = get_logger(__name__)

    async def connect(self) -> None:
        """Establish connection for control events."""
        if self._is_connected:
            self._logger.warning("discord_control.already_connected")
            return

        try:
            self._is_connected = True
            self._last_event_time = time.time()

            self._logger.info(
                "discord_control.connected",
                guild_id=self.guild_id,
                channel_id=self.channel_id,
                user_id=self.user_id,
            )

            # Send initial connection event
            await self.send_event(
                {
                    "event_type": "connection.established",
                    "timestamp": time.time(),
                    "guild_id": self.guild_id,
                    "channel_id": self.channel_id,
                    "user_id": self.user_id,
                }
            )

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_control.connection_failed", error=str(e))
            self._is_connected = False
            raise

    async def disconnect(self) -> None:
        """Close control channel connection."""
        if not self._is_connected:
            self._logger.warning("discord_control.not_connected")
            return

        try:
            self._is_connected = False

            # Send disconnect event
            await self.send_event(
                {
                    "event_type": "connection.closed",
                    "timestamp": time.time(),
                    "guild_id": self.guild_id,
                    "channel_id": self.channel_id,
                    "user_id": self.user_id,
                }
            )

            self._logger.info(
                "discord_control.disconnected",
                guild_id=self.guild_id,
                channel_id=self.channel_id,
                total_events_sent=self._total_events_sent,
                total_events_received=self._total_events_received,
            )

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_control.disconnection_failed", error=str(e))
            raise

    async def send_event(self, event: dict[str, Any]) -> None:
        """Send a control event to the connected client/agent."""
        if not self._is_connected:
            self._logger.warning("discord_control.not_connected")
            return

        try:
            # Add metadata
            event["timestamp"] = time.time()
            event["guild_id"] = self.guild_id
            event["channel_id"] = self.channel_id
            event["user_id"] = self.user_id

            # Queue event for processing
            await self._event_queue.put(event)
            self._total_events_sent += 1
            self._last_event_time = time.time()

            self._logger.debug(
                "discord_control.event_sent",
                event_type=event.get("event_type"),
                total_sent=self._total_events_sent,
            )

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_control.event_send_failed", error=str(e))
            raise

    async def receive_event(self) -> dict[str, Any] | None:
        """Receive control events from the connected client/agent."""
        if not self._is_connected:
            self._logger.warning("discord_control.not_connected")
            return None

        try:
            # Simple stub implementation - return a dummy event
            return {
                "event_type": "discord.voice_state_update",
                "timestamp": time.time(),
                "data": {"user_id": 123456789, "channel_id": 987654321},
            }

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error(
                "discord_control.event_receive_loop_failed", error=str(e)
            )
            raise

    def register_event_handler(
        self, event_type: str, handler: Callable[[Any], None]
    ) -> None:
        """Register a callback for incoming control events."""
        self._event_handlers.append(handler)
        self._logger.debug("discord_control.event_handler_registered")

    def unregister_event_handler(
        self, handler: Callable[[dict[str, Any]], None]
    ) -> None:
        """Unregister an event handler."""
        if handler in self._event_handlers:
            self._event_handlers.remove(handler)
            self._logger.debug("discord_control.event_handler_unregistered")

    # Discord-specific event methods

    async def send_wake_detected(
        self, confidence: float, ts_device: float = 0.0
    ) -> None:
        """Send wake phrase detected event."""
        event = WakeDetectedEvent(
            confidence=confidence,
            ts_device=ts_device or time.time(),
        )
        await self.send_event(event.to_dict())

    async def send_vad_start_speech(self, ts_device: float = 0.0) -> None:
        """Send VAD start speech event."""
        event = VADStartSpeechEvent(
            ts_device=ts_device or time.time(),
        )
        await self.send_event(event.to_dict())

    async def send_vad_end_speech(
        self, duration_ms: float, ts_device: float = 0.0
    ) -> None:
        """Send VAD end speech event."""
        event = VADEndSpeechEvent(
            ts_device=ts_device or time.time(),
            duration_ms=duration_ms,
        )
        await self.send_event(event.to_dict())

    async def send_barge_in_request(self, reason: str, ts_device: float = 0.0) -> None:
        """Send barge-in request event."""
        event = BargeInRequestEvent(
            reason=reason,
            ts_device=ts_device or time.time(),
        )
        await self.send_event(event.to_dict())

    async def send_session_state(self, action: SessionAction) -> None:
        """Send session state event."""
        event = SessionStateEvent(
            action=action,
        )
        await self.send_event(event.to_dict())

    async def send_route_change(
        self, input_route: str | None, output_route: str | None
    ) -> None:
        """Send route change event."""
        event = RouteChangeEvent(
            input=input_route or "unknown",
            output=output_route or "unknown",
        )
        await self.send_event(event.to_dict())

    async def send_playback_control(
        self, action: PlaybackAction, reason: str | None = None
    ) -> None:
        """Send playback control event."""
        event = PlaybackControlEvent(
            action=action,
            reason=reason or "unknown",
        )
        await self.send_event(event.to_dict())

    async def send_endpointing(self, state: EndpointingState) -> None:
        """Send endpointing event."""
        event = EndpointingEvent(
            state=state,
        )
        await self.send_event(event.to_dict())

    async def send_transcript_partial(
        self, text: str, confidence: float, ts_server: float = 0.0
    ) -> None:
        """Send partial transcript event."""
        event = TranscriptPartialEvent(
            text=text,
            confidence=confidence,
            ts_server=ts_server or time.time(),
        )
        await self.send_event(event.to_dict())

    async def send_transcript_final(
        self, text: str, words: list[WordTimestamp]
    ) -> None:
        """Send final transcript event."""
        event = TranscriptFinalEvent(
            text=text,
            words=words,
        )
        await self.send_event(event.to_dict())

    async def send_telemetry_snapshot(self, metrics: TelemetryMetrics) -> None:
        """Send telemetry snapshot event."""
        event = TelemetrySnapshotEvent(
            metrics=metrics,
        )
        await self.send_event(event.to_dict())

    async def send_error(
        self, code: str, message: str, recoverable: bool = True
    ) -> None:
        """Send error event."""
        event = ErrorEvent(
            code=code,
            message=message,
            recoverable=recoverable,
        )
        await self.send_event(event.to_dict())

    # Discord state management

    def update_voice_state(self, state: str) -> None:
        """Update Discord voice state."""
        old_state = self._current_voice_state
        self._current_voice_state = state

        self._logger.debug(
            "discord_control.voice_state_updated",
            old_state=old_state,
            new_state=state,
        )

    def update_speaking_state(self, speaking: bool) -> None:
        """Update Discord speaking state."""
        old_speaking = self._current_speaking
        self._current_speaking = speaking

        self._logger.debug(
            "discord_control.speaking_state_updated",
            old_speaking=old_speaking,
            new_speaking=speaking,
        )

    def update_deaf_state(self, deaf: bool) -> None:
        """Update Discord deaf state."""
        old_deaf = self._current_deaf
        self._current_deaf = deaf

        self._logger.debug(
            "discord_control.deaf_state_updated",
            old_deaf=old_deaf,
            new_deaf=deaf,
        )

    def update_mute_state(self, mute: bool) -> None:
        """Update Discord mute state."""
        old_mute = self._current_mute
        self._current_mute = mute

        self._logger.debug(
            "discord_control.mute_state_updated",
            old_mute=old_mute,
            new_mute=mute,
        )

    def get_voice_state(self) -> str:
        """Get current Discord voice state."""
        return self._current_voice_state

    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return self._current_speaking

    def is_deaf(self) -> bool:
        """Check if currently deaf."""
        return self._current_deaf

    def is_mute(self) -> bool:
        """Check if currently muted."""
        return self._current_mute

    def get_connection_stats(self) -> dict[str, Any]:
        """Get connection statistics."""
        return {
            "is_connected": self._is_connected,
            "total_events_sent": self._total_events_sent,
            "total_events_received": self._total_events_received,
            "last_event_time": self._last_event_time,
            "queue_size": self._event_queue.qsize(),
            "voice_state": self._current_voice_state,
            "speaking": self._current_speaking,
            "deaf": self._current_deaf,
            "mute": self._current_mute,
        }

    def get_surface_id(self) -> str:
        """Get unique surface identifier."""
        return f"discord_control:{self.guild_id}:{self.channel_id}"

    def get_telemetry(self) -> dict[str, Any]:
        """Get telemetry data for the control channel."""
        return {
            "surface_id": self.get_surface_id(),
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "user_id": self.user_id,
            "is_connected": self._is_connected,
            "total_events_sent": self._total_events_sent,
            "total_events_received": self._total_events_received,
            "last_event_time": self._last_event_time,
            "queue_size": self._event_queue.qsize(),
            "voice_state": self._current_voice_state,
            "speaking": self._current_speaking,
            "deaf": self._current_deaf,
            "mute": self._current_mute,
        }

    def update_policy(self, policy_config: dict[str, Any]) -> None:
        """Update surface-specific policies."""
        # This is a stub implementation
        # In a real implementation, this would update control policies
        self._logger.debug(
            "discord_control.policy_updated", config_keys=list(policy_config.keys())
        )

    def __repr__(self) -> str:
        """String representation of the control channel."""
        return (
            f"DiscordControlChannel(guild_id={self.guild_id}, "
            f"channel_id={self.channel_id}, user_id={self.user_id}, "
            f"connected={self._is_connected})"
        )
