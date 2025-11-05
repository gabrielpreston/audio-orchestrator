"""Wrapper for the audio processor that uses direct library calls.

This module provides a drop-in replacement for AudioPipeline that uses the
audio processing library directly (no HTTP calls).
"""

from __future__ import annotations

import time
from typing import Any

from services.common.audio_processing_core import AudioProcessingCore
from services.common.audio_vad import VADProcessor
from services.common.correlation import CorrelationIDGenerator
from services.common.structured_logging import get_logger
from services.common.surfaces.types import PCMFrame as CommonPCMFrame

from .audio import Accumulator, AudioSegment, PCMFrame as DiscordPCMFrame

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

        # Initialize VAD processor for speech detection
        # Use separate instance for explicit control and independence from AudioProcessingCore
        vad_aggressiveness = (
            audio_config.vad_aggressiveness
            if hasattr(audio_config, "vad_aggressiveness")
            else 1
        )
        self._vad_processor = VADProcessor(aggressiveness=vad_aggressiveness)

        # Track user accumulators using Accumulator class
        self._accumulators: dict[int, Accumulator] = {}

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

        Uses Accumulator to collect frames and create meaningful speech segments
        based on VAD detection and silence timeouts.

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
            # Get or create accumulator for this user
            accumulator = self._accumulators.get(user_id)
            if accumulator is None:
                accumulator = Accumulator(user_id=user_id, config=self._config)
                self._accumulators[user_id] = accumulator

            # Create common PCMFrame for processing
            current_time = time.time()
            common_frame = CommonPCMFrame(
                pcm=pcm,
                timestamp=current_time,
                rms=rms,
                duration=duration,
                sequence=accumulator.sequence,
                sample_rate=sample_rate,
                channels=1,  # Default for Discord mono audio
                sample_width=2,  # 16-bit
            )

            # Detect speech using VAD on original audio (before processing)
            is_speech = await self._vad_processor.detect_speech(common_frame)

            # Process frame with audio processor core (normalization only, VAD disabled)
            processed_common_frame = await self._audio_processor_core.process_frame(
                common_frame
            )

            # Convert back to Discord PCMFrame for accumulator
            discord_frame = DiscordPCMFrame(
                pcm=processed_common_frame.pcm,
                timestamp=processed_common_frame.timestamp,
                rms=processed_common_frame.rms,
                duration=processed_common_frame.duration,
                sequence=accumulator.sequence,
                sample_rate=processed_common_frame.sample_rate,
            )
            accumulator.sequence += 1

            # Enhanced logging for VAD decisions (rate-limited for first 20 frames, then sampled)
            frame_count = len(accumulator.frames)
            should_log_frame = (
                frame_count < 20
                or (frame_count % 50 == 0)  # Every 50th frame
                or is_speech  # Always log speech detection
            )
            # Log low RMS values (potential audio level issue)
            if rms < 100 and (frame_count < 10 or frame_count % 100 == 0):
                self._logger.warning(
                    "audio_processor_wrapper.low_rms",
                    user_id=user_id,
                    rms=rms,
                    frame_duration=duration,
                    is_speech=is_speech,
                    accumulator_frames=frame_count,
                )
            if should_log_frame:
                self._logger.debug(
                    "audio_processor_wrapper.vad_decision",
                    user_id=user_id,
                    is_speech=is_speech,
                    rms=rms,
                    frame_duration=duration,
                    accumulator_frames=frame_count,
                    accumulator_active=accumulator.active,
                    silence_started_at=accumulator.silence_started_at,
                )

            # Update accumulator based on speech detection
            if is_speech:
                accumulator.append(discord_frame)
            else:
                new_silence = accumulator.mark_silence(discord_frame.timestamp)
                if new_silence and should_log_frame:
                    self._logger.debug(
                        "audio_processor_wrapper.silence_started",
                        user_id=user_id,
                        timestamp=discord_frame.timestamp,
                        accumulator_frames=len(accumulator.frames),
                    )

            # Check if accumulator should flush
            flush_decision = accumulator.should_flush(discord_frame.timestamp)
            if flush_decision:
                # Always log flush decisions
                self._logger.info(
                    "audio_processor_wrapper.flush_decision",
                    user_id=user_id,
                    action=flush_decision.action,
                    reason=flush_decision.reason,
                    total_duration=flush_decision.total_duration,
                    silence_age=flush_decision.silence_age,
                    frame_count=len(accumulator.frames),
                    min_segment_duration=self._config.min_segment_duration_seconds,
                    max_segment_duration=self._config.max_segment_duration_seconds,
                    silence_timeout=self._config.silence_timeout_seconds,
                )
            if flush_decision and flush_decision.action == "flush":
                # Generate correlation ID (guild_id not available in this context)
                correlation_id = CorrelationIDGenerator.generate_discord_correlation_id(
                    user_id=user_id, guild_id=None
                )
                segment = accumulator.pop_segment(correlation_id)
                if segment:
                    self._logger.info(
                        "audio_processor_wrapper.segment_created",
                        user_id=user_id,
                        correlation_id=segment.correlation_id,
                        duration=segment.duration,
                        frame_count=segment.frame_count,
                        reason=flush_decision.reason,
                    )
                    return segment
                else:
                    self._logger.warning(
                        "audio_processor_wrapper.flush_decision_no_segment",
                        user_id=user_id,
                        reason=flush_decision.reason,
                        accumulator_frames=len(accumulator.frames),
                    )

            # Log accumulator state periodically when not flushing (for debugging)
            if should_log_frame and len(accumulator.frames) > 0:
                current_duration = (
                    accumulator.frames[-1].timestamp
                    + accumulator.frames[-1].duration
                    - accumulator.frames[0].timestamp
                )
                silence_age = (
                    discord_frame.timestamp - accumulator.last_activity
                    if accumulator.last_activity
                    else 0.0
                )
                self._logger.debug(
                    "audio_processor_wrapper.accumulator_state",
                    user_id=user_id,
                    frame_count=len(accumulator.frames),
                    current_duration=current_duration,
                    silence_age=silence_age,
                    min_segment_duration=self._config.min_segment_duration_seconds,
                    max_segment_duration=self._config.max_segment_duration_seconds,
                    silence_timeout=self._config.silence_timeout_seconds,
                )

            return None

        except Exception as exc:
            self._logger.error(
                "audio_processor_wrapper.frame_processing_error",
                user_id=user_id,
                error=str(exc),
            )
            return None

    def flush_inactive(self) -> list[AudioSegment]:
        """Flush inactive accumulators that should be flushed due to silence timeout.

        Checks all accumulators and flushes those that have exceeded silence timeout
        and meet minimum duration requirements.

        Returns:
            List of audio segments that were flushed
        """
        segments = []
        current_time = time.time()  # Use time.time() to match frame timestamps

        for user_id, accumulator in list(self._accumulators.items()):
            flush_decision = accumulator.should_flush(current_time)
            if flush_decision and flush_decision.action == "flush":
                correlation_id = CorrelationIDGenerator.generate_discord_correlation_id(
                    user_id=user_id, guild_id=None
                )
                segment = accumulator.pop_segment(correlation_id)
                if segment:
                    segments.append(segment)
                    self._logger.debug(
                        "audio_processor_wrapper.segment_flushed_inactive",
                        user_id=user_id,
                        correlation_id=segment.correlation_id,
                        duration=segment.duration,
                        frame_count=segment.frame_count,
                        reason=flush_decision.reason,
                    )

        return segments

    def force_flush(self) -> list[AudioSegment]:
        """Force flush all accumulators with active frames.

        Used for cleanup or shutdown scenarios where all pending audio
        should be flushed regardless of duration or silence state.

        Returns:
            List of audio segments that were flushed
        """
        segments = []

        for user_id, accumulator in list(self._accumulators.items()):
            if accumulator.frames:
                correlation_id = CorrelationIDGenerator.generate_discord_correlation_id(
                    user_id=user_id, guild_id=None
                )
                segment = accumulator.pop_segment(correlation_id)
                if segment:
                    segments.append(segment)
                    self._logger.debug(
                        "audio_processor_wrapper.segment_force_flushed",
                        user_id=user_id,
                        correlation_id=segment.correlation_id,
                        duration=segment.duration,
                        frame_count=segment.frame_count,
                    )

        return segments

    async def health_check(self) -> bool:
        """Check if the audio processor is healthy.

        Returns:
            True (library-based implementation is always available)
        """
        return True
