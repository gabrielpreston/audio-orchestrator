"""Core audio processing module for frame and segment processing.

This module combines VAD, quality metrics, and format conversion to provide
a unified audio processing interface without ML dependencies.
"""

from __future__ import annotations

from typing import Any

from services.common.audio import AudioProcessor as CommonAudioProcessor
from services.common.audio_quality import AudioQualityMetrics
from services.common.audio_vad import VADProcessor
from services.common.structured_logging import get_logger
from services.common.surfaces.types import AudioSegment, PCMFrame

logger = get_logger(__name__)


class AudioProcessingCore:
    """Core audio processing - frame and segment processing without ML dependencies."""

    _vad_processor: VADProcessor | None

    def __init__(self, config: Any) -> None:
        """Initialize audio processing core.

        Args:
            config: Audio configuration with settings like enable_vad, enable_volume_normalization, etc.
        """
        self.config = config
        self._logger = get_logger(__name__)

        # Initialize VAD if enabled
        if hasattr(config, "enable_vad") and config.enable_vad:
            aggressiveness = (
                config.vad_aggressiveness
                if hasattr(config, "vad_aggressiveness")
                else 1
            )
            self._vad_processor = VADProcessor(aggressiveness=aggressiveness)
        else:
            self._vad_processor = None

        # Initialize quality metrics calculator
        self._quality_metrics = AudioQualityMetrics()

        # Initialize common audio processor for format conversion
        self._common_processor = CommonAudioProcessor("audio_processing_core")

        self._logger.info("audio_processing_core.initialized")

    async def process_frame(self, frame: PCMFrame) -> PCMFrame:
        """Process single PCM frame with VAD and basic normalization.

        Args:
            frame: PCM frame to process

        Returns:
            Processed PCM frame
        """
        try:
            # Apply VAD if enabled
            if self._vad_processor is not None:
                frame = await self._vad_processor.apply_vad(frame)

            # Apply basic normalization
            frame = await self._normalize_frame(frame)

            return frame

        except Exception as exc:
            self._logger.warning(
                "audio_processing_core.frame_processing_failed",
                error=str(exc),
                sequence=getattr(frame, "sequence", None),
            )
            # Return original frame on error
            return frame

    async def process_segment(self, segment: AudioSegment) -> AudioSegment:
        """Process audio segment with format conversion.

        Args:
            segment: Audio segment to process

        Returns:
            Processed audio segment
        """
        try:
            # Convert PCM to WAV for processing (if needed)
            # Note: Most segment processing happens at WAV level
            # This is a placeholder for future enhancement
            # For now, segments are typically already in correct format

            # Return segment as-is (format conversion happens at service level)
            return segment

        except Exception as exc:
            self._logger.warning(
                "audio_processing_core.segment_processing_failed",
                error=str(exc),
                correlation_id=getattr(segment, "correlation_id", None),
            )
            # Return original segment on error
            return segment

    async def calculate_quality_metrics(
        self, audio_data: PCMFrame | AudioSegment
    ) -> dict[str, Any]:
        """Calculate audio quality metrics.

        Args:
            audio_data: Audio data to analyze (frame or segment)

        Returns:
            Quality metrics dictionary
        """
        return await self._quality_metrics.calculate_metrics(audio_data)

    async def _normalize_frame(self, frame: PCMFrame) -> PCMFrame:
        """Apply basic normalization to frame.

        Args:
            frame: PCM frame to normalize

        Returns:
            Normalized frame
        """
        try:
            import numpy as np

            # Convert to numpy array
            frame_data = np.frombuffer(frame.pcm, dtype=np.int16).astype(np.float32)

            # Normalize to target RMS
            target_rms = 0.1  # Target RMS level
            current_rms = np.sqrt(np.mean(frame_data**2))

            if current_rms > 0:
                scale_factor = target_rms / current_rms
                frame_data = frame_data * scale_factor

                # Clamp to prevent clipping
                frame_data = np.clip(frame_data, -32767, 32767)

            # Convert back to int16
            frame.pcm = frame_data.astype(np.int16).tobytes()

            return frame

        except Exception as exc:
            self._logger.warning(
                "audio_processing_core.normalization_failed", error=str(exc)
            )
            return frame
