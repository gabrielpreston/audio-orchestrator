"""
Discord AudioSink adapter implementation.

This module implements the AudioSink interface for Discord voice playback,
providing a standardized way to play audio to Discord voice channels.
"""

from __future__ import annotations

from collections.abc import Callable
import io
import time
from typing import Any

import discord

from services.common.structured_logging import get_logger
from services.common.surfaces.media_gateway import MediaGateway
from services.common.surfaces.protocols import AudioPlaybackProtocol
from services.common.surfaces.types import AudioFormat, AudioMetadata, PCMFrame


class DiscordAudioSink(AudioPlaybackProtocol):
    """Discord audio sink adapter implementing AudioPlaybackProtocol."""

    def __init__(
        self,
        guild_id: int,
        channel_id: int,
        media_gateway: MediaGateway | None = None,
        voice_client: discord.VoiceClient | None = None,
    ) -> None:
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.media_gateway = media_gateway or MediaGateway()
        self.voice_client = voice_client

        # Playback state
        self._is_playing = False
        self._playback_handlers: list[Callable[[str, Any], None]] = []
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

        self._logger = get_logger(__name__, service_name="discord")

    def _check_playing_state(self, operation: str) -> bool:
        """Check if playback is active, log warning if not."""
        if not self._is_playing:
            self._logger.warning(f"discord_sink.not_playing_for_{operation}")
            return False
        return True

    def _notify_handlers(self, event: str, data: dict[str, Any]) -> None:
        """Notify all registered handlers of an event."""
        for handler in self._playback_handlers:
            try:
                handler(event, data)
            except (ValueError, TypeError, KeyError) as e:
                self._logger.error("discord_sink.playback_handler_failed", error=str(e))

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
            self._notify_handlers(
                "playback_started", {"timestamp": self._playback_start_time}
            )

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_sink.playback_start_failed", error=str(e))
            self._is_playing = False
            raise

    async def stop_playback(self) -> None:
        """Stop audio playback to Discord voice channel."""
        if not self._check_playing_state("stop"):
            return

        try:
            self._is_playing = False

            playback_duration = time.time() - self._playback_start_time
            self._total_audio_played += playback_duration

            self._logger.info(
                "discord_sink.playback_stopped",
                guild_id=self.guild_id,
                channel_id=self.channel_id,
                duration=playback_duration,
            )

            # Notify handlers
            self._notify_handlers("playback_stopped", {"duration": playback_duration})

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_sink.playback_stop_failed", error=str(e))
            raise

    async def play_audio_chunk(self, frame: PCMFrame) -> None:
        """Play a chunk of decoded audio to Discord voice channel."""
        if not self._check_playing_state("play_chunk"):
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

            # Send audio to Discord's voice channel using FFmpeg
            if self.voice_client and self.voice_client.is_connected():
                try:
                    # Create audio source from PCM frame bytes
                    # Note: For frame-by-frame playback, we'd need to buffer frames
                    # For now, this is primarily used for full audio playback via play_audio_bytes
                    audio_source = discord.FFmpegPCMAudio(
                        source=io.BytesIO(frame.pcm),
                        pipe=True,
                    )
                    if not self.voice_client.is_playing():
                        self.voice_client.play(audio_source)
                except Exception as playback_exc:
                    self._logger.warning(
                        "discord_sink.frame_playback_failed",
                        error=str(playback_exc),
                    )
            else:
                self._logger.debug(
                    "discord_sink.voice_client_unavailable",
                    has_voice_client=self.voice_client is not None,
                    is_connected=(
                        self.voice_client.is_connected() if self.voice_client else False
                    ),
                )

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
            self._notify_handlers(
                "frame_played",
                {
                    "frame_size": len(frame.pcm),
                    "sample_rate": frame.sample_rate,
                    "channels": frame.channels,
                    "duration": frame.duration,
                    "timestamp": frame.timestamp,
                },
            )

            self._logger.debug(
                "discord_sink.frame_played",
                frame_size=len(frame.pcm),
                voice_client_available=self.voice_client is not None,
                is_playing=(
                    self.voice_client.is_playing() if self.voice_client else False
                ),
                sample_rate=frame.sample_rate,
                channels=frame.channels,
            )

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_sink.audio_chunk_play_failed", error=str(e))
            raise

    async def play_audio_bytes(
        self,
        audio_bytes: bytes,
        *,
        sample_rate: int = 22050,
        channels: int = 1,
        correlation_id: str | None = None,
    ) -> None:
        """Play full audio bytes (e.g., from TTS) to Discord voice channel.

        Args:
            audio_bytes: Audio data as bytes (WAV format expected)
            sample_rate: Sample rate of the audio (default: 22050 for Bark TTS)
            channels: Number of audio channels (default: 1 for mono)
            correlation_id: Correlation ID for logging
        """
        if not self.voice_client or not self.voice_client.is_connected():
            self._logger.warning(
                "discord_sink.audio_playback_skipped",
                reason="voice_client_not_connected",
                correlation_id=correlation_id,
            )
            return

        try:
            # Ensure playback state is active
            if not self._is_playing:
                await self.start_playback()

            # Create an in-memory file-like object from the audio bytes
            audio_source = discord.FFmpegPCMAudio(
                source=io.BytesIO(audio_bytes),
                pipe=True,
            )

            # Play the audio
            self.voice_client.play(
                audio_source,
                after=lambda error: self._playback_finished(error, correlation_id),
            )

            self._logger.info(
                "discord_sink.audio_playback_started",
                audio_size=len(audio_bytes),
                sample_rate=sample_rate,
                channels=channels,
                correlation_id=correlation_id,
            )

        except Exception as exc:
            self._logger.error(
                "discord_sink.audio_playback_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                correlation_id=correlation_id,
            )
            raise

    def _playback_finished(
        self, error: Exception | None, correlation_id: str | None
    ) -> None:
        """Callback when audio playback finishes.

        Args:
            error: Error if playback failed, None if successful
            correlation_id: Correlation ID for logging
        """
        if error:
            self._logger.error(
                "discord_sink.audio_playback_error",
                error=str(error),
                error_type=type(error).__name__,
                correlation_id=correlation_id,
            )
        else:
            self._logger.debug(
                "discord_sink.audio_playback_completed",
                correlation_id=correlation_id,
            )

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

    def set_media_gateway(self, media_gateway: MediaGateway) -> None:
        """Set the media gateway for audio processing."""
        self.media_gateway = media_gateway
        self._logger.debug("discord_sink.media_gateway_updated")

    def get_media_gateway(self) -> MediaGateway:
        """Get the current media gateway."""
        return self.media_gateway

    async def pause_playback(self) -> None:
        """Pause audio playback."""
        if not self._check_playing_state("pause"):
            return

        try:
            # This is a stub implementation
            # In a real implementation, this would pause Discord audio playback

            self._logger.info("discord_sink.playback_paused")

            # Notify handlers
            self._notify_handlers("playback_paused", {"timestamp": time.time()})

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_sink.playback_pause_failed", error=str(e))
            raise

    async def resume_playback(self) -> None:
        """Resume audio playback."""
        if not self._check_playing_state("resume"):
            return

        try:
            # This is a stub implementation
            # In a real implementation, this would resume Discord audio playback

            self._logger.info("discord_sink.playback_resumed")

            # Notify handlers
            self._notify_handlers("playback_resumed", {"timestamp": time.time()})

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

    async def set_volume(self, volume: float) -> None:
        """Set the playback volume (0.0 to 1.0)."""
        if not 0.0 <= volume <= 1.0:
            raise ValueError("Volume must be between 0.0 and 1.0")
        self._volume = volume
        self._logger.info(f"Volume set to {volume}")

    def __repr__(self) -> str:
        """String representation of the audio sink."""
        return (
            f"DiscordAudioSink(guild_id={self.guild_id}, "
            f"channel_id={self.channel_id}, playing={self._is_playing})"
        )
