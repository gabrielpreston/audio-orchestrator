"""Discord audio input adapter.

This module provides a Discord-specific implementation of the AudioInputAdapter
for capturing audio from Discord voice channels.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

from services.common.logging import get_logger

from .base import AudioInputAdapter
from .types import AdapterConfig, AudioChunk, AudioMetadata


logger = get_logger(__name__)


class DiscordAudioInputAdapter(AudioInputAdapter):
    """Discord-specific audio input adapter.

    This adapter captures audio from Discord voice channels using the
    Discord bot's audio capture capabilities.
    """

    def __init__(self, config: AdapterConfig) -> None:
        """Initialize the Discord audio input adapter.

        Args:
            config: Adapter configuration with Discord-specific settings
        """
        super().__init__(config)
        self._discord_client = None
        self._voice_channel = None
        self._audio_queue: asyncio.Queue[AudioChunk] = asyncio.Queue()
        self._capture_task: asyncio.Task[None] | None = None

    @property
    def name(self) -> str:
        """Adapter identifier."""
        return "discord_audio_input"

    async def start_capture(self) -> None:
        """Start capturing audio from Discord voice channel.

        This initializes the Discord connection and begins audio capture.
        """
        try:
            self._logger.info("Starting Discord audio capture")

            # Initialize Discord client (this would be injected in real implementation)
            # self._discord_client = await self._initialize_discord_client()

            # Connect to voice channel
            # self._voice_channel = await self._connect_to_voice_channel()

            # Start capture task
            self._capture_task = asyncio.create_task(self._capture_audio_loop())
            self._is_capturing = True

            self._logger.info("Discord audio capture started successfully")

        except Exception as e:
            self._logger.error(
                "Failed to start Discord audio capture", extra={"error": str(e)}
            )
            raise

    async def stop_capture(self) -> None:
        """Stop capturing audio from Discord voice channel."""
        try:
            self._logger.info("Stopping Discord audio capture")

            self._is_capturing = False

            if self._capture_task:
                self._capture_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._capture_task

            # Disconnect from voice channel
            # if self._voice_channel:
            #     await self._voice_channel.disconnect()

            self._logger.info("Discord audio capture stopped")

        except Exception as e:
            self._logger.error(
                "Error stopping Discord audio capture", extra={"error": str(e)}
            )

    async def get_audio_stream(self) -> AsyncIterator[AudioChunk]:
        """Get an async iterator of audio chunks from Discord.

        Yields:
            AudioChunk: Audio data captured from Discord voice channel
        """
        self._logger.info("Starting Discord audio stream")

        try:
            while self._is_capturing:
                try:
                    # Wait for audio data from Discord
                    audio_data = await asyncio.wait_for(
                        self._audio_queue.get(), timeout=1.0
                    )

                    if audio_data:
                        yield audio_data

                except TimeoutError:
                    # No audio data available, continue
                    continue
                except Exception as e:
                    self._logger.warning(
                        "Error getting audio data from Discord", extra={"error": str(e)}
                    )
                    continue

        except asyncio.CancelledError:
            self._logger.info("Discord audio stream cancelled")
            raise
        except Exception as e:
            self._logger.error("Error in Discord audio stream", extra={"error": str(e)})
            raise

    async def _capture_audio_loop(self) -> None:
        """Main audio capture loop for Discord.

        This runs in a separate task and captures audio from Discord,
        putting it into the audio queue for consumption.
        """
        self._logger.info("Discord audio capture loop started")

        try:
            while self._is_capturing:
                # In a real implementation, this would capture audio from Discord
                # For now, we'll simulate with a placeholder
                await asyncio.sleep(0.1)  # Simulate audio processing time

                # Create a mock audio chunk for testing
                if self._audio_queue.qsize() < 10:  # Limit queue size
                    mock_chunk = self._create_mock_audio_chunk()
                    await self._audio_queue.put(mock_chunk)

        except asyncio.CancelledError:
            self._logger.info("Discord audio capture loop cancelled")
        except Exception as e:
            self._logger.error(
                "Error in Discord audio capture loop", extra={"error": str(e)}
            )

    def _create_mock_audio_chunk(self) -> AudioChunk:
        """Create a mock audio chunk for testing.

        Returns:
            AudioChunk: Mock audio data
        """
        # Mock audio data (silence)
        audio_data = b"\x00" * 1024  # 1KB of silence

        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.1,  # 100ms
            frames=4800,
            format="pcm",
            bit_depth=16,
        )

        return AudioChunk(
            data=audio_data,
            metadata=metadata,
            correlation_id=f"discord_{asyncio.get_event_loop().time()}",
            sequence_number=0,
            is_silence=True,
            volume_level=0.0,
        )

    async def get_capabilities(self) -> dict[str, Any]:
        """Get Discord adapter capabilities.

        Returns:
            Dictionary describing Discord adapter capabilities
        """
        base_capabilities = await super().get_capabilities()
        discord_capabilities = {
            "platform": "discord",
            "supports_voice_channels": True,
            "supports_multiple_users": True,
            "supports_voice_activity_detection": True,
            "max_sample_rate": 48000,
            "supported_formats": ["pcm", "opus"],
        }

        return {**base_capabilities, **discord_capabilities}

    async def health_check(self) -> dict[str, Any]:
        """Perform health check for Discord adapter.

        Returns:
            Health check results
        """
        base_health = await super().health_check()
        discord_health = {
            "discord_connected": self._discord_client is not None,
            "voice_channel_connected": self._voice_channel is not None,
            "audio_queue_size": self._audio_queue.qsize(),
            "capture_task_running": self._capture_task is not None
            and not self._capture_task.done(),
        }

        return {**base_health, **discord_health}
