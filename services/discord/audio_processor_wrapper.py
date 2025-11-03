"""Wrapper for the audio processor that uses direct library calls.

This module provides a drop-in replacement for AudioPipeline that uses the
audio processing library directly (no HTTP calls).
"""

from __future__ import annotations

import time
from typing import Any

from services.common.audio_processing_core import AudioProcessingCore
from services.common.structured_logging import get_logger
from services.common.surfaces.types import PCMFrame

from .audio import AudioSegment

logger = get_logger(__name__)


class AudioProcessorWrapper:
    """Wrapper for audio processor that uses direct library calls."""

    def __init__(
        self,
        audio_config: Any,
        telemetry_config: Any,
        audio_processor_core: AudioProcessingCore | None = None,
    ) -> None:
        """Initialize audio processor wrapper.

        Args:
            audio_config: Audio configuration
            telemetry_config: Telemetry configuration
            audio_processor_core: Optional audio processor core (for testing)
        """
        self._config = audio_config
        self._telemetry_config = telemetry_config
        self._logger = get_logger(__name__)

        # Initialize audio processor core
        if audio_processor_core is None:
            self._audio_processor_core = AudioProcessingCore(audio_config)
        else:
            self._audio_processor_core = audio_processor_core

        # Track user accumulators (simplified version of AudioPipeline logic)
        self._accumulators: dict[int, dict[str, Any]] = {}

        self._logger.info("audio_processor_wrapper.initialized")

    async def close(self) -> None:
        """Close the audio processor (no-op for library-based implementation)."""
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
            # Create PCMFrame for audio processor (using common types)
            frame = PCMFrame(
                pcm=pcm,
                timestamp=time.time(),
                rms=rms,
                duration=duration,
                sequence=0,  # Will be updated by audio processor
                sample_rate=sample_rate,
                channels=1,  # Default for Discord mono audio
                sample_width=2,  # 16-bit
            )

            # Process frame with audio processor core
            processed_frame = await self._audio_processor_core.process_frame(frame)

            # For now, we don't implement the full accumulator logic
            # This is a simplified version that processes frames individually
            # In a full implementation, you would need to:
            # 1. Track user accumulators
            # 2. Implement VAD logic
            # 3. Handle silence detection
            # 4. Manage segment boundaries

            # Create a simple segment for testing (discord AudioSegment uses int user_id)
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
        """Check if the audio processor is healthy.

        Returns:
            True (library-based implementation is always available)
        """
        return True
