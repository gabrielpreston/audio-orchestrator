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
            - rms: Root mean square in normalized domain (0-1) for SNR calculations
            - rms_int16: Root mean square in int16 domain (0-32767) for threshold comparisons
            - snr_db: Signal-to-noise ratio in dB
            - clarity_score: Clarity score (0-1)
            - dominant_frequency_hz: Dominant frequency in Hz
            - sample_rate: Sample rate in Hz
            - duration_ms: Duration in milliseconds
        """
        # Input validation
        if audio_data is None:
            raise ValueError("audio_data cannot be None")
        if not hasattr(audio_data, "pcm"):
            raise ValueError(
                f"audio_data must have 'pcm' attribute, got {type(audio_data).__name__}"
            )
        if not hasattr(audio_data, "sample_rate"):
            raise ValueError(
                f"audio_data must have 'sample_rate' attribute, got {type(audio_data).__name__}"
            )

        # Validate pcm
        if not audio_data.pcm:
            raise ValueError("audio_data.pcm cannot be empty")

        # Validate sample_rate
        if (
            not isinstance(audio_data.sample_rate, (int, float))
            or audio_data.sample_rate <= 0
        ):
            raise ValueError(
                f"audio_data.sample_rate must be positive number, got {audio_data.sample_rate}"
            )

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

            # Early return for silent/empty audio to avoid -Infinity in SNR calculation
            if rms < 1e-6 or len(audio_array) == 0:
                from services.common.structured_logging import get_logger

                logger = get_logger(__name__)
                logger.debug(
                    "audio_quality.silent_audio_detected",
                    rms=float(rms),
                    array_length=len(audio_array),
                    sample_rate=sample_rate,
                )
                return {
                    "rms": 0.0,  # Normalized RMS (0-1)
                    "rms_int16": 0.0,  # Int16 domain RMS (0-32767)
                    "snr_db": float(-np.inf),  # Explicit silent audio handling
                    "clarity_score": 0.0,
                    "dominant_frequency_hz": 0.0,
                    "sample_rate": sample_rate,
                    "duration_ms": len(audio_array) / sample_rate * 1000
                    if sample_rate > 0
                    else 0.0,
                }

            # Calculate SNR (signal-to-noise ratio)
            signal_power = np.mean(audio_array**2)
            noise_power = np.var(audio_array - np.mean(audio_array))

            # Guard against silent audio (signal_power = 0) producing -Infinity
            if signal_power < 1e-10:
                snr = -np.inf
            else:
                snr = 10 * np.log10(signal_power / (noise_power + 1e-10))

            # Calculate clarity score with -Infinity handling
            if snr == -np.inf or np.isinf(snr):
                clarity_score = 0.0
            else:
                clarity_score = min(1.0, max(0.0, (snr + 20) / 40))  # Normalize to 0-1

            # Calculate frequency content
            fft = np.fft.fft(audio_array)
            freqs = np.fft.fftfreq(len(audio_array), 1 / sample_rate)
            dominant_freq = freqs[np.argmax(np.abs(fft))]

            # Calculate int16 domain RMS for threshold comparisons
            from services.common.audio import normalized_to_int16

            rms_int16 = normalized_to_int16(rms)

            metrics = {
                "rms": float(rms),  # Normalized RMS (0-1) for SNR calculations
                "rms_int16": float(
                    rms_int16
                ),  # Int16 domain RMS (0-32767) for threshold comparisons
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
                "rms": 0.0,  # Normalized RMS (0-1)
                "rms_int16": 0.0,  # Int16 domain RMS (0-32767)
                "snr_db": 0.0,
                "clarity_score": 0.0,
                "dominant_frequency_hz": 0.0,
                "sample_rate": audio_data.sample_rate
                if hasattr(audio_data, "sample_rate")
                else 16000,
                "duration_ms": 0.0,
            }

    @staticmethod
    def validate_quality_thresholds(
        metrics: dict[str, Any],
        min_snr_db: float = 10.0,
        min_rms: float = 100.0,
        min_clarity: float = 0.3,
    ) -> dict[str, Any]:
        """Validate audio quality against thresholds.

        Args:
            metrics: Quality metrics dictionary from calculate_metrics()
            min_snr_db: Minimum SNR in dB (default: 10.0)
            min_rms: Minimum RMS value in int16 domain (default: 100.0)
            min_clarity: Minimum clarity score 0-1 (default: 0.3)

        Returns:
            Dictionary containing validation results:
            - meets_thresholds: bool - True if all thresholds met
            - failures: list[str] - List of failed threshold checks
            - warnings: list[str] - List of warnings (marginal quality)
            - snr_db: float - Actual SNR value
            - rms: float - Actual RMS value (normalized)
            - rms_int16: float - Actual RMS value (int16 domain)
            - clarity_score: float - Actual clarity score

        Note:
            The min_rms threshold is in int16 domain (0-32767). If metrics contains
            normalized RMS only, it will be converted to int16 domain for comparison.
        """
        from services.common.audio import normalized_to_int16

        failures = []
        warnings = []

        snr = metrics.get("snr_db", 0.0)
        rms_normalized = metrics.get("rms", 0.0)
        rms_int16 = metrics.get("rms_int16", 0.0)
        clarity = metrics.get("clarity_score", 0.0)

        # Convert normalized RMS to int16 domain if rms_int16 not available
        if rms_int16 == 0.0 and rms_normalized > 0.0:
            rms_int16 = normalized_to_int16(rms_normalized)

        # Check SNR threshold
        if snr < min_snr_db:
            failures.append(f"SNR {snr:.1f}dB below minimum {min_snr_db}dB")
        elif snr < min_snr_db * 1.5:  # Warning for marginal SNR
            warnings.append(f"SNR {snr:.1f}dB is marginal (target: {min_snr_db}dB)")

        # Check RMS threshold (use int16 domain for comparison)
        if rms_int16 < min_rms:
            failures.append(
                f"RMS {rms_int16:.1f} below minimum {min_rms} (int16 domain)"
            )
        elif rms_int16 < min_rms * 1.5:  # Warning for marginal RMS
            warnings.append(
                f"RMS {rms_int16:.1f} is marginal (target: {min_rms}, int16 domain)"
            )

        # Check clarity threshold
        if clarity < min_clarity:
            warnings.append(
                f"Clarity score {clarity:.2f} below ideal {min_clarity} (not blocking)"
            )

        return {
            "meets_thresholds": len(failures) == 0,
            "failures": failures,
            "warnings": warnings,
            "snr_db": snr,
            "rms": rms_normalized,
            "rms_int16": float(rms_int16),
            "clarity_score": clarity,
        }
