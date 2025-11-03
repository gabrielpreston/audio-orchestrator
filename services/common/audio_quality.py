"""Audio quality metrics calculation module.

This module provides pure functions for calculating audio quality metrics
including RMS, SNR, clarity scores, and frequency analysis.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from services.common.surfaces.types import AudioSegment, PCMFrame


class AudioQualityMetrics:
    """Calculate audio quality metrics."""

    @staticmethod
    async def calculate_metrics(
        audio_data: PCMFrame | AudioSegment,
    ) -> dict[str, Any]:
        """Calculate audio quality metrics for frame or segment.

        Args:
            audio_data: PCM frame or audio segment to analyze

        Returns:
            Dictionary containing quality metrics:
            - rms: Root mean square (volume level)
            - snr_db: Signal-to-noise ratio in dB
            - clarity_score: Clarity score (0-1)
            - dominant_frequency_hz: Dominant frequency in Hz
            - sample_rate: Sample rate in Hz
            - duration_ms: Duration in milliseconds
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

            return metrics

        except (ValueError, IndexError, ZeroDivisionError) as exc:
            # Return default metrics on error (invalid audio data, empty array, etc.)
            # Log specific error for debugging
            from services.common.structured_logging import get_logger

            logger = get_logger(__name__)
            logger.warning(
                "audio_quality.metrics_calculation_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return {
                "rms": 0.0,
                "snr_db": 0.0,
                "clarity_score": 0.0,
                "dominant_frequency_hz": 0.0,
                "sample_rate": audio_data.sample_rate
                if hasattr(audio_data, "sample_rate")
                else 16000,
                "duration_ms": 0.0,
            }
