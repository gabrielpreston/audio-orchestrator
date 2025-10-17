"""
Discord AudioSink adapter implementation.

This module implements the AudioSink interface for Discord voice playback,
providing a standardized way to play audio to Discord voice channels.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from services.common.logging import get_logger
from services.common.surfaces.interfaces import AudioSink
from services.common.surfaces.media_gateway import MediaGateway
from services.common.surfaces.types import AudioFormat, AudioMetadata, PCMFrame

logger = get_logger(__name__)


class DiscordAudioSink(AudioSink):
    """Discord audio sink adapter implementing AudioSink interface."""

    def __init__(
        self,
        guild_id: int,
        channel_id: int,
        media_gateway: MediaGateway | None = None,
    ) -> None:
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.media_gateway = media_gateway or MediaGateway()

        # Playback state
        self._is_playing = False
        self._playback_handlers: list[Callable[[str, Any], None]] = []
        self._current_audio_url: str | None = None
        self._playback_start_time = 0.0

        # Audio metadata
        self._metadata = AudioMetadata(
            sample_rate=48000,  # Discord's default sample rate
            channels=2,  # Discord's default channel count
            sample_width=2,  # 16-bit PCM
            duration=0.0,
            frames=0,
            format=AudioFormat.PCM,
            bit_depth=16,
        )

        # Performance tracking
        self._total_audio_played = 0.0
        self._total_playback_requests = 0
        self._last_playback_time = 0.0

        self._logger = get_logger(__name__)

    async def start_playback(self) -> None:
        """Start audio playback to Discord voice channel."""
        if self._is_playing:
            self._logger.warning("discord_sink.already_playing")
            return

        try:
            self._is_playing = True
            self._playback_start_time = time.time()

            self._logger.info(
                "discord_sink.playback_started",
                guild_id=self.guild_id,
                channel_id=self.channel_id,
            )

            # Notify handlers
            for handler in self._playback_handlers:
                try:
                    handler(
                        "playback_started", {"timestamp": self._playback_start_time}
                    )
                except (ValueError, TypeError, KeyError) as e:
                    self._logger.error(
                        "discord_sink.playback_handler_failed", error=str(e)
                    )

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_sink.playback_start_failed", error=str(e))
            self._is_playing = False
            raise

    async def stop_playback(self) -> None:
        """Stop audio playback to Discord voice channel."""
        if not self._is_playing:
            self._logger.warning("discord_sink.not_playing")
            return

        try:
            self._is_playing = False
            self._current_audio_url = None

            playback_duration = time.time() - self._playback_start_time
            self._total_audio_played += playback_duration

            self._logger.info(
                "discord_sink.playback_stopped",
                guild_id=self.guild_id,
                channel_id=self.channel_id,
                duration=playback_duration,
            )

            # Notify handlers
            for handler in self._playback_handlers:
                try:
                    handler("playback_stopped", {"duration": playback_duration})
                except (ValueError, TypeError, KeyError) as e:
                    self._logger.error(
                        "discord_sink.playback_handler_failed", error=str(e)
                    )

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_sink.playback_stop_failed", error=str(e))
            raise

    async def play_audio_chunk(self, frame: PCMFrame) -> None:
        """Play a chunk of decoded audio to Discord voice channel."""
        if not self._is_playing:
            self._logger.warning("discord_sink.not_playing")
            return

        try:
            # Process audio through media gateway if available
            if self.media_gateway:
                result = await self.media_gateway.process_outgoing_audio(
                    audio_data=frame.pcm,
                    to_format="pcm",
                    to_metadata=frame,
                )

                if not result.success:
                    self._logger.warning(
                        "discord_sink.media_gateway_processing_failed",
                        error=result.error,
                    )
                    return

                frame.pcm = result.audio_data

            # This is a stub implementation
            # In a real implementation, this would send audio to Discord's voice channel
            # For now, we'll simulate audio playback

            # Simulate audio processing time
            await asyncio.sleep(0.01)  # 10ms processing time

            # Update metadata
            self._metadata = AudioMetadata(
                sample_rate=frame.sample_rate,
                channels=frame.channels,
                sample_width=frame.sample_width,
                duration=frame.duration,
                frames=1,
                format=AudioFormat.PCM,
                bit_depth=frame.sample_width * 8,
            )
            self._last_playback_time = time.time()

            # Notify handlers
            for handler in self._playback_handlers:
                try:
                    handler(
                        "frame_played",
                        {
                            "frame_size": len(frame.pcm),
                            "sample_rate": frame.sample_rate,
                            "channels": frame.channels,
                            "duration": frame.duration,
                            "timestamp": frame.timestamp,
                        },
                    )
                except (ValueError, TypeError, KeyError) as e:
                    self._logger.error(
                        "discord_sink.playback_handler_failed", error=str(e)
                    )

            self._logger.debug(
                "discord_sink.frame_played",
                frame_size=len(frame.pcm),
                sample_rate=frame.sample_rate,
                channels=frame.channels,
            )

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_sink.audio_chunk_play_failed", error=str(e))
            raise

    def register_playback_handler(self, handler: Callable[[str, Any], None]) -> None:
        """Register a callback for playback events."""
        self._playback_handlers.append(handler)
        self._logger.debug("discord_sink.playback_handler_registered")

    def unregister_playback_handler(self, handler: Callable[[str, Any], None]) -> None:
        """Unregister a playback handler."""
        if handler in self._playback_handlers:
            self._playback_handlers.remove(handler)
            self._logger.debug("discord_sink.playback_handler_unregistered")

    def get_playback_stats(self) -> dict[str, Any]:
        """Get audio playback statistics."""
        return {
            "is_playing": self._is_playing,
            "total_audio_played": self._total_audio_played,
            "total_playback_requests": self._total_playback_requests,
            "last_playback_time": self._last_playback_time,
            "current_audio_url": self._current_audio_url,
            "playback_start_time": self._playback_start_time,
        }

    def is_playing(self) -> bool:
        """Check if audio playback is active."""
        return self._is_playing

    def get_guild_id(self) -> int:
        """Get Discord guild ID."""
        return self.guild_id

    def get_channel_id(self) -> int:
        """Get Discord channel ID."""
        return self.channel_id

    def get_current_audio_url(self) -> str | None:
        """Get current audio URL being played."""
        return self._current_audio_url

    def set_current_audio_url(self, audio_url: str) -> None:
        """Set current audio URL."""
        self._current_audio_url = audio_url
        self._logger.debug("discord_sink.audio_url_set", url=audio_url)

    def set_media_gateway(self, media_gateway: MediaGateway) -> None:
        """Set the media gateway for audio processing."""
        self.media_gateway = media_gateway
        self._logger.debug("discord_sink.media_gateway_updated")

    def get_media_gateway(self) -> MediaGateway:
        """Get the current media gateway."""
        return self.media_gateway

    async def play_audio_from_url(self, audio_url: str) -> bool:
        """Play audio from URL (Discord-specific method)."""
        if not self._is_playing:
            await self.start_playback()

        try:
            self._current_audio_url = audio_url
            self._total_playback_requests += 1

            # This is a stub implementation
            # In a real implementation, this would fetch and play audio from URL

            self._logger.info(
                "discord_sink.audio_url_playback_started",
                url=audio_url,
                guild_id=self.guild_id,
                channel_id=self.channel_id,
            )

            # Notify handlers
            for handler in self._playback_handlers:
                try:
                    handler("audio_url_playback_started", {"url": audio_url})
                except (ValueError, TypeError, KeyError) as e:
                    self._logger.error(
                        "discord_sink.playback_handler_failed", error=str(e)
                    )

            return True

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_sink.audio_url_playback_failed", error=str(e))
            return False

    async def pause_playback(self) -> None:
        """Pause audio playback."""
        if not self._is_playing:
            self._logger.warning("discord_sink.not_playing")
            return

        try:
            # This is a stub implementation
            # In a real implementation, this would pause Discord audio playback

            self._logger.info("discord_sink.playback_paused")

            # Notify handlers
            for handler in self._playback_handlers:
                try:
                    handler("playback_paused", {"timestamp": time.time()})
                except (ValueError, TypeError, KeyError) as e:
                    self._logger.error(
                        "discord_sink.playback_handler_failed", error=str(e)
                    )

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_sink.playback_pause_failed", error=str(e))
            raise

    async def resume_playback(self) -> None:
        """Resume audio playback."""
        if not self._is_playing:
            self._logger.warning("discord_sink.not_playing")
            return

        try:
            # This is a stub implementation
            # In a real implementation, this would resume Discord audio playback

            self._logger.info("discord_sink.playback_resumed")

            # Notify handlers
            for handler in self._playback_handlers:
                try:
                    handler("playback_resumed", {"timestamp": time.time()})
                except (ValueError, TypeError, KeyError) as e:
                    self._logger.error(
                        "discord_sink.playback_handler_failed", error=str(e)
                    )

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_sink.playback_resume_failed", error=str(e))
            raise

    def get_surface_id(self) -> str:
        """Get unique surface identifier."""
        return f"discord_sink:{self.guild_id}:{self.channel_id}"

    def get_telemetry(self) -> dict[str, Any]:
        """Get telemetry data for the audio sink."""
        return {
            "surface_id": self.get_surface_id(),
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "is_playing": self._is_playing,
            "total_audio_played": self._total_audio_played,
            "total_playback_requests": self._total_playback_requests,
            "last_playback_time": self._last_playback_time,
            "current_audio_url": self._current_audio_url,
            "playback_start_time": self._playback_start_time,
            "metadata": {
                "sample_rate": self._metadata.sample_rate,
                "channels": self._metadata.channels,
                "sample_width": self._metadata.sample_width,
                "duration": self._metadata.duration,
                "frames": self._metadata.frames,
                "format": self._metadata.format,
                "bit_depth": self._metadata.bit_depth,
            },
        }

    def update_policy(self, policy_config: dict[str, Any]) -> None:
        """Update surface-specific policies."""
        # This is a stub implementation
        # In a real implementation, this would update playback policies
        self._logger.debug(
            "discord_sink.policy_updated", config_keys=list(policy_config.keys())
        )

    def __repr__(self) -> str:
        """String representation of the audio sink."""
        return (
            f"DiscordAudioSink(guild_id={self.guild_id}, "
            f"channel_id={self.channel_id}, playing={self._is_playing})"
        )
