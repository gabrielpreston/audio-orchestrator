"""
Discord AudioSource adapter implementation.

This module implements the AudioSource interface for Discord voice capture,
providing a standardized way to capture audio from Discord voice channels.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from services.common.logging import get_logger
from services.common.surfaces.interfaces import AudioSource
from services.common.surfaces.media_gateway import MediaGateway
from services.common.surfaces.types import AudioMetadata, PCMFrame

logger = get_logger(__name__)


class DiscordAudioSource(AudioSource):
    """Discord audio source adapter implementing AudioSource interface."""

    def __init__(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int | None = None,
        media_gateway: MediaGateway | None = None,
    ) -> None:
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.user_id = user_id
        self.media_gateway = media_gateway or MediaGateway()

        # Audio capture state
        self._is_capturing = False
        self._frame_handlers: list[Callable[[PCMFrame], None]] = []
        self._audio_buffer: list[PCMFrame] = []
        self._sequence_counter = 0

        # Audio metadata
        self._metadata = AudioMetadata(
            sample_rate=48000,  # Discord's default sample rate
            channels=2,  # Discord's default channel count
            sample_width=2,  # 16-bit PCM
            duration=0.0,
            frames=0,
            format="pcm",
            bit_depth=16,
        )

        # Performance tracking
        self._total_frames_captured = 0
        self._total_audio_duration = 0.0
        self._last_frame_time = 0.0

        self._logger = get_logger(__name__)

    async def start_capture(self) -> None:
        """Start audio capture from Discord voice channel."""
        if self._is_capturing:
            self._logger.warning("discord_source.already_capturing")
            return

        try:
            self._is_capturing = True
            self._sequence_counter = 0
            self._last_frame_time = time.time()

            self._logger.info(
                "discord_source.capture_started",
                guild_id=self.guild_id,
                channel_id=self.channel_id,
                user_id=self.user_id,
            )

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_source.capture_start_failed", error=str(e))
            self._is_capturing = False
            raise

    async def stop_capture(self) -> None:
        """Stop audio capture from Discord voice channel."""
        if not self._is_capturing:
            self._logger.warning("discord_source.not_capturing")
            return

        try:
            self._is_capturing = False

            # Clear audio buffer
            self._audio_buffer.clear()

            self._logger.info(
                "discord_source.capture_stopped",
                guild_id=self.guild_id,
                channel_id=self.channel_id,
                total_frames=self._total_frames_captured,
                total_duration=self._total_audio_duration,
            )

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_source.capture_stop_failed", error=str(e))
            raise

    async def read_audio_frame(self) -> PCMFrame | None:
        """Read a single PCM audio frame from Discord."""
        if not self._is_capturing:
            return None

        try:
            # This is a stub implementation
            # In a real implementation, this would read from Discord's audio stream
            # For now, we'll simulate audio frames

            # Simulate audio frame generation
            await asyncio.sleep(0.02)  # 20ms frame duration

            # Create dummy PCM data (silence)
            pcm_data = (
                b"\x00\x00" * 960
            )  # 960 samples * 2 bytes = 1920 bytes for 20ms at 48kHz

            frame = PCMFrame(
                pcm=pcm_data,
                timestamp=time.time(),
                rms=0.0,  # Silence
                duration=0.02,  # 20ms
                sequence=self._sequence_counter,
                sample_rate=48000,
            )

            self._sequence_counter += 1
            self._total_frames_captured += 1
            self._total_audio_duration += frame.duration
            self._last_frame_time = frame.timestamp

            # Store frame in buffer
            self._audio_buffer.append(frame)

            # Notify frame handlers
            for handler in self._frame_handlers:
                try:
                    handler(frame)
                except (ValueError, TypeError, KeyError) as e:
                    self._logger.error(
                        "discord_source.frame_handler_failed", error=str(e)
                    )

            return frame

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_source.frame_read_failed", error=str(e))
            return None

    def get_metadata(self) -> AudioMetadata:
        """Return metadata for the audio source."""
        return self._metadata

    def register_frame_handler(self, handler: Callable[[PCMFrame], None]) -> None:
        """Register a callback for new audio frames."""
        self._frame_handlers.append(handler)
        self._logger.debug("discord_source.frame_handler_registered")

    def unregister_frame_handler(self, handler: Callable[[PCMFrame], None]) -> None:
        """Unregister a frame handler."""
        if handler in self._frame_handlers:
            self._frame_handlers.remove(handler)
            self._logger.debug("discord_source.frame_handler_unregistered")

    def get_capture_stats(self) -> dict[str, Any]:
        """Get audio capture statistics."""
        return {
            "is_capturing": self._is_capturing,
            "total_frames_captured": self._total_frames_captured,
            "total_audio_duration": self._total_audio_duration,
            "buffer_size": len(self._audio_buffer),
            "last_frame_time": self._last_frame_time,
            "sequence_counter": self._sequence_counter,
        }

    def clear_buffer(self) -> None:
        """Clear the audio buffer."""
        self._audio_buffer.clear()
        self._logger.debug("discord_source.buffer_cleared")

    def get_buffer_size(self) -> int:
        """Get current buffer size."""
        return len(self._audio_buffer)

    def is_capturing(self) -> bool:
        """Check if audio capture is active."""
        return self._is_capturing

    def get_guild_id(self) -> int:
        """Get Discord guild ID."""
        return self.guild_id

    def get_channel_id(self) -> int:
        """Get Discord channel ID."""
        return self.channel_id

    def get_user_id(self) -> int | None:
        """Get Discord user ID (if filtering by user)."""
        return self.user_id

    def set_media_gateway(self, media_gateway: MediaGateway) -> None:
        """Set the media gateway for audio processing."""
        self.media_gateway = media_gateway
        self._logger.debug("discord_source.media_gateway_updated")

    def get_media_gateway(self) -> MediaGateway:
        """Get the current media gateway."""
        return self.media_gateway

    async def process_audio_frame(self, frame: PCMFrame) -> PCMFrame | None:
        """Process audio frame through media gateway."""
        if not self.media_gateway:
            return frame

        try:
            # Convert frame to format expected by media gateway
            audio_data = frame.pcm
            metadata = AudioMetadata(
                sample_rate=frame.sample_rate,
                channels=2,  # Discord default
                sample_width=2,
                duration=frame.duration,
                frames=len(audio_data) // 4,  # 2 channels * 2 bytes per sample
                format="pcm",
                bit_depth=16,
            )

            # Process through media gateway
            result = self.media_gateway.process_incoming_audio(
                audio_data=audio_data,
                from_format="pcm",
                from_metadata=metadata,
            )

            if not result.success:
                self._logger.warning(
                    "discord_source.media_gateway_processing_failed",
                    error=result.error,
                )
                return frame

            # Create processed frame
            processed_frame = PCMFrame(
                pcm=result.audio_data,
                timestamp=frame.timestamp,
                rms=frame.rms,
                duration=frame.duration,
                sequence=frame.sequence,
                sample_rate=result.metadata.sample_rate,
            )

            return processed_frame

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_source.frame_processing_failed", error=str(e))
            return frame

    async def start_capture_loop(self) -> None:
        """Start continuous audio capture loop."""
        if not self._is_capturing:
            await self.start_capture()

        try:
            while self._is_capturing:
                frame = await self.read_audio_frame()
                if frame:
                    # Process frame through media gateway
                    processed_frame = await self.process_audio_frame(frame)
                    if processed_frame:
                        # Notify handlers with processed frame
                        for handler in self._frame_handlers:
                            try:
                                handler(processed_frame)
                            except (ValueError, TypeError, KeyError) as e:
                                self._logger.error(
                                    "discord_source.processed_frame_handler_failed",
                                    error=str(e),
                                )

                # Small delay to prevent excessive CPU usage
                await asyncio.sleep(0.001)

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("discord_source.capture_loop_failed", error=str(e))
            await self.stop_capture()
            raise

    async def stop_capture_loop(self) -> None:
        """Stop continuous audio capture loop."""
        await self.stop_capture()

    def get_surface_id(self) -> str:
        """Get unique surface identifier."""
        return f"discord:{self.guild_id}:{self.channel_id}"

    def get_telemetry(self) -> dict[str, Any]:
        """Get telemetry data for the audio source."""
        return {
            "surface_id": self.get_surface_id(),
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "user_id": self.user_id,
            "is_capturing": self._is_capturing,
            "total_frames_captured": self._total_frames_captured,
            "total_audio_duration": self._total_audio_duration,
            "buffer_size": len(self._audio_buffer),
            "last_frame_time": self._last_frame_time,
            "sequence_counter": self._sequence_counter,
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
        # In a real implementation, this would update VAD thresholds, etc.
        self._logger.debug(
            "discord_source.policy_updated", config_keys=list(policy_config.keys())
        )

    def __repr__(self) -> str:
        """String representation of the audio source."""
        return (
            f"DiscordAudioSource(guild_id={self.guild_id}, "
            f"channel_id={self.channel_id}, user_id={self.user_id}, "
            f"capturing={self._is_capturing})"
        )
