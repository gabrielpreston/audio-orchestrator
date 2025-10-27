"""Core audio processing logic for the unified audio processor service.

This module provides the main audio processing functionality including:
- Frame processing with VAD
- Audio segment processing
- Quality metrics calculation
- Performance optimization
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import numpy as np
import webrtcvad

from services.common.audio import AudioProcessor as CommonAudioProcessor
from services.common.structured_logging import get_logger
from services.common.surfaces.types import AudioSegment, PCMFrame

logger = get_logger(__name__)


class AudioProcessor:
    """Unified audio processor combining best of all implementations."""

    def __init__(self, config: Any) -> None:
        """Initialize audio processor.

        Args:
            config: Audio configuration
        """
        self.config = config
        self._logger = get_logger(__name__)

        # Initialize VAD
        self._vad = webrtcvad.Vad(
            config.vad_aggressiveness if hasattr(config, "vad_aggressiveness") else 1
        )

        # Initialize common audio processor
        self._common_processor = CommonAudioProcessor("audio_processor")

        # Performance tracking
        self._processing_stats = {
            "total_frames": 0,
            "total_segments": 0,
            "total_processing_time": 0.0,
            "avg_frame_processing_time": 0.0,
            "avg_segment_processing_time": 0.0,
        }

        self._logger.info("audio_processor.initialized")

    async def initialize(self) -> None:
        """Initialize the audio processor."""
        try:
            # Initialize any async resources
            self._logger.info("audio_processor.initialization_completed")
        except Exception as exc:
            self._logger.error("audio_processor.initialization_failed", error=str(exc))
            raise

    async def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            self._logger.info("audio_processor.cleanup_completed")
        except Exception as exc:
            self._logger.error("audio_processor.cleanup_failed", error=str(exc))

    async def process_frame(self, frame: PCMFrame) -> PCMFrame:
        """Process single PCM frame with VAD and basic processing.

        Args:
            frame: PCM frame to process

        Returns:
            Processed PCM frame
        """
        start_time = time.perf_counter()

        try:
            # Apply VAD if enabled
            if self.config.enable_vad:
                frame = await self._apply_vad(frame)

            # Apply basic normalization
            frame = await self._normalize_frame(frame)

            # Update statistics
            processing_time = time.perf_counter() - start_time
            self._update_frame_stats(processing_time)

            self._logger.debug(
                "audio_processor.frame_processed",
                sequence=frame.sequence,
                processing_time_ms=processing_time * 1000,
            )

            return frame

        except Exception as exc:
            processing_time = time.perf_counter() - start_time
            self._logger.error(
                "audio_processor.frame_processing_failed",
                sequence=frame.sequence,
                error=str(exc),
                processing_time_ms=processing_time * 1000,
            )
            # Return original frame on error
            return frame

    async def process_segment(self, segment: AudioSegment) -> AudioSegment:
        """Process audio segment with full enhancement pipeline.

        Args:
            segment: Audio segment to process

        Returns:
            Processed audio segment
        """
        start_time = time.perf_counter()

        try:
            # Convert PCM to WAV for processing
            wav_data = self._common_processor.pcm_to_wav(
                segment.pcm, sample_rate=segment.sample_rate, channels=1, sample_width=2
            )

            # Apply format conversion if needed
            processed_wav = await self._convert_audio_format(
                wav_data, segment.sample_rate
            )

            # Apply resampling if needed
            processed_wav = await self._resample_audio(
                processed_wav, segment.sample_rate
            )

            # Apply normalization if enabled
            if self.config.enable_volume_normalization:
                processed_wav = await self._normalize_audio(processed_wav)

            # Apply noise reduction if enabled
            if self.config.enable_noise_reduction:
                processed_wav = await self._reduce_noise(processed_wav)

            # Convert back to PCM
            processed_pcm = self._common_processor.wav_to_pcm(processed_wav)[0]

            # Create processed segment
            processed_segment = AudioSegment(
                user_id=segment.user_id,
                pcm=processed_pcm,
                start_timestamp=segment.start_timestamp,
                end_timestamp=segment.end_timestamp,
                correlation_id=segment.correlation_id,
                frame_count=segment.frame_count,
                sample_rate=segment.sample_rate,
            )

            # Update statistics
            processing_time = time.perf_counter() - start_time
            self._update_segment_stats(processing_time)

            self._logger.info(
                "audio_processor.segment_processed",
                correlation_id=segment.correlation_id,
                user_id=segment.user_id,
                processing_time_ms=processing_time * 1000,
            )

            return processed_segment

        except Exception as exc:
            processing_time = time.perf_counter() - start_time
            self._logger.error(
                "audio_processor.segment_processing_failed",
                correlation_id=segment.correlation_id,
                user_id=segment.user_id,
                error=str(exc),
                processing_time_ms=processing_time * 1000,
            )
            # Return original segment on error
            return segment

    async def calculate_quality_metrics(
        self, audio_data: PCMFrame | AudioSegment
    ) -> dict[str, Any]:
        """Calculate audio quality metrics.

        Args:
            audio_data: Audio data to analyze

        Returns:
            Quality metrics dictionary
        """
        try:
            # Convert to numpy array for analysis
            if isinstance(audio_data, PCMFrame):
                audio_array = np.frombuffer(audio_data.pcm, dtype=np.int16).astype(
                    np.float32
                )
                sample_rate = audio_data.sample_rate
            else:
                audio_array = np.frombuffer(audio_data.pcm, dtype=np.int16).astype(
                    np.float32
                )
                sample_rate = audio_data.sample_rate

            # Normalize to [-1, 1]
            audio_array = audio_array / 32768.0

            # Calculate RMS (volume level)
            rms = np.sqrt(np.mean(audio_array**2))

            # Calculate SNR (signal-to-noise ratio)
            signal_power = np.mean(audio_array**2)
            noise_power = np.var(audio_array - np.mean(audio_array))
            snr = 10 * np.log10(signal_power / (noise_power + 1e-10))

            # Calculate clarity score (simplified)
            clarity_score = min(1.0, max(0.0, (snr + 20) / 40))  # Normalize to 0-1

            # Calculate frequency content
            fft = np.fft.fft(audio_array)
            freqs = np.fft.fftfreq(len(audio_array), 1 / sample_rate)
            dominant_freq = freqs[np.argmax(np.abs(fft))]

            metrics = {
                "rms": float(rms),
                "snr_db": float(snr),
                "clarity_score": float(clarity_score),
                "dominant_frequency_hz": float(abs(dominant_freq)),
                "sample_rate": sample_rate,
                "duration_ms": len(audio_array) / sample_rate * 1000,
            }

            self._logger.debug(
                "audio_processor.quality_metrics_calculated", metrics=metrics
            )

            return metrics

        except Exception as exc:
            self._logger.error("audio_processor.quality_metrics_failed", error=str(exc))
            return {
                "rms": 0.0,
                "snr_db": 0.0,
                "clarity_score": 0.0,
                "dominant_frequency_hz": 0.0,
                "sample_rate": 16000,
                "duration_ms": 0.0,
            }

    async def _apply_vad(self, frame: PCMFrame) -> PCMFrame:
        """Apply voice activity detection to frame.

        Args:
            frame: PCM frame to process

        Returns:
            Frame with VAD applied
        """
        try:
            # Convert to 16kHz for VAD (required by webrtcvad)
            if frame.sample_rate != 16000:
                # Simple resampling (in production, use proper resampling)
                frame_data = np.frombuffer(frame.pcm, dtype=np.int16)
                if frame.sample_rate > 16000:
                    # Downsample
                    ratio = frame.sample_rate // 16000
                    frame_data = frame_data[::ratio]
                else:
                    # Upsample (simple repeat)
                    ratio = 16000 // frame.sample_rate
                    frame_data = np.repeat(frame_data, ratio)

                # Ensure frame is correct length for VAD (10ms, 20ms, or 30ms)
                frame_duration_ms = 30  # Use 30ms frames
                frame_length = int(16000 * frame_duration_ms / 1000)

                if len(frame_data) > frame_length:
                    frame_data = frame_data[:frame_length]
                elif len(frame_data) < frame_length:
                    frame_data = np.pad(frame_data, (0, frame_length - len(frame_data)))

                frame_bytes = frame_data.astype(np.int16).tobytes()
            else:
                frame_bytes = frame.pcm

            # Apply VAD
            is_speech = self._vad.is_speech(frame_bytes, 16000)

            # Update frame based on VAD result
            if not is_speech:
                # Reduce volume for non-speech frames
                frame_data = np.frombuffer(frame.pcm, dtype=np.int16)
                frame_data = (frame_data * 0.1).astype(np.int16)
                frame.pcm = frame_data.tobytes()

            return frame

        except Exception as exc:
            self._logger.warning("audio_processor.vad_failed", error=str(exc))
            return frame

    async def _normalize_frame(self, frame: PCMFrame) -> PCMFrame:
        """Apply basic normalization to frame.

        Args:
            frame: PCM frame to normalize

        Returns:
            Normalized frame
        """
        try:
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
            self._logger.warning("audio_processor.normalization_failed", error=str(exc))
            return frame

    async def _convert_audio_format(self, wav_data: bytes, sample_rate: int) -> bytes:
        """Convert audio format if needed.

        Args:
            wav_data: WAV audio data
            sample_rate: Current sample rate

        Returns:
            Converted audio data
        """
        # For now, just return the original data
        # In production, implement proper format conversion
        await asyncio.sleep(0.001)  # Simulate processing time
        return wav_data

    async def _resample_audio(self, wav_data: bytes, sample_rate: int) -> bytes:
        """Resample audio to target sample rate.

        Args:
            wav_data: WAV audio data
            sample_rate: Current sample rate

        Returns:
            Resampled audio data
        """
        # For now, just return the original data
        # In production, implement proper resampling
        await asyncio.sleep(0.001)  # Simulate processing time
        return wav_data

    async def _normalize_audio(self, wav_data: bytes) -> bytes:
        """Normalize audio volume.

        Args:
            wav_data: WAV audio data

        Returns:
            Normalized audio data
        """
        # For now, just return the original data
        # In production, implement proper normalization
        await asyncio.sleep(0.001)  # Simulate processing time
        return wav_data

    async def _reduce_noise(self, wav_data: bytes) -> bytes:
        """Reduce noise in audio.

        Args:
            wav_data: WAV audio data

        Returns:
            Noise-reduced audio data
        """
        # For now, just return the original data
        # In production, implement proper noise reduction
        await asyncio.sleep(0.001)  # Simulate processing time
        return wav_data

    def _update_frame_stats(self, processing_time: float) -> None:
        """Update frame processing statistics."""
        self._processing_stats["total_frames"] += 1
        self._processing_stats["total_processing_time"] += processing_time
        self._processing_stats["avg_frame_processing_time"] = (
            self._processing_stats["total_processing_time"]
            / self._processing_stats["total_frames"]
        )

    def _update_segment_stats(self, processing_time: float) -> None:
        """Update segment processing statistics."""
        self._processing_stats["total_segments"] += 1
        self._processing_stats["avg_segment_processing_time"] = processing_time

    def get_processing_stats(self) -> dict[str, Any]:
        """Get processing statistics."""
        return self._processing_stats.copy()
