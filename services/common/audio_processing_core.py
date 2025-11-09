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
            Normalized frame (returns original frame on error)
        """
        # Input validation
        if not hasattr(frame, "pcm"):
            self._logger.warning(
                "audio_processing_core.normalization_failed",
                error="frame missing 'pcm' attribute",
                error_type="AttributeError",
            )
            return frame

        if not frame.pcm:
            self._logger.warning(
                "audio_processing_core.normalization_failed",
                error="frame.pcm is empty",
                error_type="ValueError",
            )
            return frame

        # Validate minimum size (at least 2 bytes for 1 int16 sample)
        if len(frame.pcm) < 2:
            self._logger.warning(
                "audio_processing_core.normalization_failed",
                error=f"frame.pcm too small (minimum 2 bytes, got {len(frame.pcm)} bytes)",
                error_type="ValueError",
            )
            return frame

        try:
            import numpy as np

            # Convert to numpy array
            frame_data = np.frombuffer(frame.pcm, dtype=np.int16).astype(np.float32)

            # Validate array after conversion
            if frame_data.size == 0:
                self._logger.warning(
                    "audio_processing_core.normalization_failed",
                    error="frame_data array is empty after conversion",
                    error_type="ValueError",
                )
                return frame

            # Normalize to target RMS in int16 domain
            # Note: target_rms is in int16 domain (0-32767), not normalized (0-1)
            # Typical values: 1000-2000 for normal speech, 2000-5000 for loud speech
            target_rms = 2000.0  # Target RMS level in int16 domain
            # Calculate current RMS in int16 domain (frame_data is already int16 values)
            current_rms = np.sqrt(np.mean(frame_data.astype(np.float64) ** 2))

            if current_rms > 0:
                scale_factor = target_rms / current_rms

                # Validate scale factor is finite
                if not np.isfinite(scale_factor):
                    self._logger.warning(
                        "audio_processing_core.normalization_failed",
                        error=f"scale_factor is not finite: {scale_factor}",
                        error_type="ValueError",
                        current_rms=float(current_rms),
                        target_rms=target_rms,
                    )
                    return frame

                frame_data = frame_data * scale_factor

                # Clamp to prevent clipping (use full int16 range)
                frame_data = np.clip(frame_data, -32768, 32767)

            # Convert back to int16
            frame.pcm = frame_data.astype(np.int16).tobytes()

            return frame

        except (ValueError, TypeError, AttributeError) as exc:
            # Specific exception types with context
            self._logger.warning(
                "audio_processing_core.normalization_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                frame_pcm_length=len(frame.pcm) if frame.pcm else 0,
            )
            return frame
        except MemoryError as exc:
            # Memory errors with context
            self._logger.warning(
                "audio_processing_core.normalization_memory_error",
                error=str(exc),
                error_type="MemoryError",
                frame_pcm_length=len(frame.pcm) if frame.pcm else 0,
            )
            return frame
        except Exception as exc:
            # Catch-all for unexpected errors
            self._logger.warning(
                "audio_processing_core.normalization_unexpected_error",
                error=str(exc),
                error_type=type(exc).__name__,
                frame_pcm_length=len(frame.pcm) if frame.pcm else 0,
            )
            return frame
