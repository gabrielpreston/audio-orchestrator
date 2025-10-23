"""Wrapper for the audio processor service that replaces AudioPipeline functionality.

This module provides a drop-in replacement for AudioPipeline that uses the
unified audio processor service via HTTP API.
"""

from __future__ import annotations

import time
from typing import Any

from services.common.logging import get_logger
from services.discord.audio import AudioSegment, PCMFrame
from services.discord.audio_processor_client import AudioProcessorClient

logger = get_logger(__name__)


class AudioProcessorWrapper:
    """Wrapper for audio processor service that replaces AudioPipeline functionality."""

    def __init__(
        self,
        audio_config: Any,
        telemetry_config: Any,
        audio_processor_client: AudioProcessorClient | None = None,
    ) -> None:
        """Initialize audio processor wrapper.

        Args:
            audio_config: Audio configuration
            telemetry_config: Telemetry configuration
            audio_processor_client: Optional audio processor client (for testing)
        """
        self._config = audio_config
        self._telemetry_config = telemetry_config
        self._logger = get_logger(__name__)

        # Initialize audio processor client
        if audio_processor_client is None:
            self._audio_processor_client = AudioProcessorClient(
                base_url=getattr(
                    audio_config, "service_url", "http://audio-processor:9100"
                ),
                timeout=getattr(audio_config, "service_timeout", 20.0)
                / 1000.0,  # Convert ms to seconds
            )
        else:
            self._audio_processor_client = audio_processor_client

        # Track user accumulators (simplified version of AudioPipeline logic)
        self._accumulators: dict[int, dict[str, Any]] = {}

        self._logger.info("audio_processor_wrapper.initialized")

    async def close(self) -> None:
        """Close the audio processor client."""
        await self._audio_processor_client.close()
        self._logger.info("audio_processor_wrapper.closed")

    def register_frame(
        self,
        user_id: int,
        pcm: bytes,
        rms: float,
        duration: float,
        sample_rate: int,
    ) -> AudioSegment | None:
        """Register a frame and return segment if ready (synchronous interface).

        This method provides a synchronous interface that matches the original AudioPipeline
        but internally uses async processing. For now, it returns None to maintain compatibility.

        Args:
            user_id: User ID
            pcm: PCM audio data
            rms: RMS value
            duration: Frame duration
            sample_rate: Sample rate

        Returns:
            AudioSegment if ready, None otherwise
        """
        # For now, return None to maintain compatibility
        # In a full implementation, this would need to be async
        # or use a different approach for real-time processing
        return None

    async def register_frame_async(
        self,
        user_id: int,
        pcm: bytes,
        rms: float,
        duration: float,
        sample_rate: int,
    ) -> AudioSegment | None:
        """Register a frame and return segment if ready (async interface).

        Args:
            user_id: User ID
            pcm: PCM audio data
            rms: RMS value
            duration: Frame duration
            sample_rate: Sample rate

        Returns:
            AudioSegment if ready, None otherwise
        """
        try:
            # Create PCMFrame for audio processor
            frame = PCMFrame(
                pcm=pcm,
                timestamp=time.time(),
                rms=rms,
                duration=duration,
                sequence=0,  # Will be updated by audio processor
                sample_rate=sample_rate,
            )

            # Process frame with audio processor
            processed_frame = await self._audio_processor_client.process_frame(frame)
            if processed_frame is None:
                self._logger.warning(
                    "audio_processor_wrapper.frame_processing_failed",
                    user_id=user_id,
                    sequence=frame.sequence,
                )
                return None

            # For now, we don't implement the full accumulator logic
            # This is a simplified version that processes frames individually
            # In a full implementation, you would need to:
            # 1. Track user accumulators
            # 2. Implement VAD logic
            # 3. Handle silence detection
            # 4. Manage segment boundaries

            # Create a simple segment for testing
            segment = AudioSegment(
                user_id=user_id,
                pcm=processed_frame.pcm,
                start_timestamp=processed_frame.timestamp,
                end_timestamp=processed_frame.timestamp + processed_frame.duration,
                correlation_id=f"frame-{user_id}-{int(processed_frame.timestamp)}",
                frame_count=1,
                sample_rate=processed_frame.sample_rate,
            )

            self._logger.debug(
                "audio_processor_wrapper.frame_processed",
                user_id=user_id,
                sequence=processed_frame.sequence,
                correlation_id=segment.correlation_id,
            )

            return segment

        except Exception as exc:
            self._logger.error(
                "audio_processor_wrapper.frame_processing_error",
                user_id=user_id,
                error=str(exc),
            )
            return None

    def flush_inactive(self) -> list[AudioSegment]:
        """Flush inactive accumulators (simplified version).

        Returns:
            List of audio segments
        """
        # For now, we don't implement the full accumulator logic
        # This is a placeholder that returns an empty list
        return []

    def force_flush(self) -> list[AudioSegment]:
        """Force flush all accumulators (simplified version).

        Returns:
            List of audio segments
        """
        # For now, we don't implement the full accumulator logic
        # This is a placeholder that returns an empty list
        return []

    async def health_check(self) -> bool:
        """Check if the audio processor service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        return await self._audio_processor_client.health_check()
