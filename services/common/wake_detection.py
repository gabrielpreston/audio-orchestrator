"""Wake word detection library for audio-orchestrator services.

This module provides wake phrase detection capabilities that can be used
by any audio I/O surface (Discord, WebRTC, SIP, etc.).

REQUIRES: Services using this module must have openwakeword installed
or will gracefully degrade to transcript-based detection only.
"""

from __future__ import annotations

import audioop
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import numpy as np

from services.common.structured_logging import get_logger


try:  # pragma: no cover - optional dependency import guard
    from openwakeword import Model as WakeWordModel
except Exception:  # pragma: no cover - gracefully degrade when package missing
    WakeWordModel = None

if TYPE_CHECKING:
    from services.common.config.presets import WakeConfig


@dataclass(slots=True)
class WakeDetectionResult:
    """Details about a detected wake phrase."""

    phrase: str
    confidence: float | None
    source: Literal["audio", "transcript"]


class WakeDetector:
    """Detect wake phrases from audio PCM data and transcripts.

    This class can be used by any audio I/O service to detect wake phrases
    in real-time audio streams or transcribed text.
    """

    def __init__(self, config: WakeConfig, service_name: str = "common") -> None:
        """Initialize wake detector.

        Args:
            config: Wake detection configuration
            service_name: Service name for logging context
        """
        self._config = config
        self._logger = get_logger(__name__, service_name=service_name)
        self._target_sample_rate = config.target_sample_rate_hz
        self._threshold = config.activation_threshold
        self._model = self._load_model([Path(p) for p in config.model_paths])

    def _filter_wake_word_models(self, model_files: list[Path]) -> list[Path]:
        """Filter model files to only include wake word models.

        Excludes infrastructure models and prefers ONNX over TFLite.

        Args:
            model_files: List of discovered model file paths

        Returns:
            Filtered list of wake word model paths
        """
        # Infrastructure models to exclude (not wake word models)
        exclude_patterns = {"embedding_model", "melspectrogram", "silero_vad"}

        # Group by model name (stem) to deduplicate formats
        onnx_files = {f.stem: f for f in model_files if f.suffix == ".onnx"}
        tflite_files = {f.stem: f for f in model_files if f.suffix == ".tflite"}

        # Collect wake word models, preferring ONNX
        filtered_models = []
        all_model_names = set(onnx_files.keys()) | set(tflite_files.keys())

        for model_name in all_model_names:
            # Skip infrastructure models
            if any(pattern in model_name.lower() for pattern in exclude_patterns):
                continue

            # Prefer ONNX, fallback to TFLite
            if model_name in onnx_files:
                filtered_models.append(onnx_files[model_name])
            elif model_name in tflite_files:
                filtered_models.append(tflite_files[model_name])

        return filtered_models

    def _load_model(self, paths: Iterable[Path]) -> Any:
        """Load wake word models with three-tier fallback strategy.

        Tier 1: User-provided paths (WAKE_MODEL_PATHS)
        Tier 2: Auto-discover in ./services/models/wake/
        Tier 3: Built-in default models (if available)
        """
        # Tier 1: Filter user-provided paths
        model_paths_raw = [str(path) for path in paths if path]
        if model_paths_raw:
            # Filter user-provided paths as well
            model_files = [Path(p) for p in model_paths_raw if Path(p).exists()]
            if not model_files:
                self._logger.warning(
                    "wake.user_paths_not_found",
                    provided_paths=model_paths_raw,
                    message="User-provided model paths not found, falling back to auto-discovery",
                )
            model_paths = [str(f) for f in self._filter_wake_word_models(model_files)]
        else:
            model_paths = []

        # Tier 2: Auto-discover models if no paths provided
        if not model_paths:
            # Check openwakeword's default location first (works in containers with volume mounts)
            # Default location: ~/.local/share/openwakeword/models
            # With HOME=/app in containers, this is /app/.local/share/openwakeword/models
            default_wake_dir = (
                Path.home() / ".local" / "share" / "openwakeword" / "models"
            )

            if default_wake_dir.exists():
                # Discover all model files
                model_files = list(default_wake_dir.glob("*.tflite")) + list(
                    default_wake_dir.glob("*.onnx")
                )
                if model_files:
                    # Filter to only wake word models
                    filtered_files = self._filter_wake_word_models(model_files)
                    if filtered_files:
                        model_paths = [str(f) for f in filtered_files]
                        self._logger.info(
                            "wake.auto_discovered_models",
                            count=len(model_paths),
                            total_discovered=len(model_files),
                            filtered_out=len(model_files) - len(model_paths),
                            directory=str(default_wake_dir),
                            format="onnx_preferred",
                        )

        if WakeWordModel is None:
            self._logger.warning(
                "wake.openwakeword_unavailable",
                model_paths=model_paths if model_paths else "default",
            )
            return None

        try:
            # Tier 1 & 2: Use provided or auto-discovered models
            if model_paths:
                return WakeWordModel(
                    wakeword_models=model_paths,
                    inference_framework=self._config.inference_framework,
                )

            # Tier 3: Try built-in default models
            try:
                default_model = WakeWordModel(
                    inference_framework=self._config.inference_framework,
                )
                self._logger.info(
                    "wake.using_default_models",
                    message="Using openwakeword built-in default models",
                )
                return default_model
            except (TypeError, ValueError, Exception):
                # Default models not available
                self._logger.info(
                    "wake.no_models_available",
                    message="No model paths provided, auto-discovery found none, and default models unavailable. Falling back to transcript-based detection only.",
                )
                return None

        except Exception as exc:
            model_count = len(model_paths) if model_paths else 0
            model_preview = (
                [Path(p).name for p in model_paths[:5]] if model_paths else []
            )

            # Provide specific guidance for common errors
            error_str = str(exc)
            suggestion = "Check model compatibility. Ensure only wake word models (not infrastructure) are included."
            if (
                "NO_SUCHFILE" in error_str
                or "melspectrogram" in error_str
                or "embedding_model" in error_str
            ):
                suggestion = (
                    "Openwakeword infrastructure models are missing. "
                    "This may indicate an incomplete package installation. "
                    "Try reinstalling openwakeword: pip install --force-reinstall openwakeword==0.6.0"
                )
            elif "inference framework" in error_str.lower():
                suggestion = (
                    "Inference framework mismatch. "
                    "Ensure WAKE_INFERENCE_FRAMEWORK matches your model format (onnx or tflite). "
                    "On Linux, use 'onnx' (default)."
                )

            self._logger.warning(  # Changed from error() to warning()
                "wake.model_load_failed",
                error=error_str,
                error_type=type(exc).__name__,
                model_count=model_count,
                model_preview=model_preview,
                fallback="transcript_only",
                suggestion=suggestion,
            )
            return None

    def detect_audio(self, pcm: bytes, sample_rate: int) -> WakeDetectionResult | None:
        """Detect wake phrase from raw PCM audio data.

        Args:
            pcm: Raw PCM audio bytes
            sample_rate: Sample rate in Hz

        Returns:
            WakeDetectionResult if wake phrase detected, None otherwise
        """
        if not pcm or self._model is None:
            self._logger.debug(
                "wake.detect_audio_skipped",
                reason="no_pcm" if not pcm else "model_unavailable",
                pcm_length=len(pcm) if pcm else 0,
                model_loaded=self._model is not None,
            )
            return None
        converted = self._resample(pcm, sample_rate)
        if not converted:
            self._logger.debug(
                "wake.resample_failed_for_detection",
                source_rate=sample_rate,
                target_rate=self._target_sample_rate,
                pcm_length=len(pcm),
            )
            return None
        normalized = (
            np.frombuffer(converted, dtype=np.int16).astype(np.float32) / 32768.0
        )

        # Ensure consistent input dimensions for ONNX model
        # NOTE: The ONNX error suggests melspectrogram frame mismatch, but openwakeword
        # converts raw audio to melspectrogram internally. The model may have been trained
        # with a specific audio length. We'll pad/truncate to a standard length that typically
        # produces the expected melspectrogram frame count.
        #
        # Based on openwakeword's typical processing: ~320ms of audio at 16kHz produces
        # approximately 16 melspectrogram frames (20ms hop, 16 frames = 320ms)
        # 16 frames * 320 samples/frame = 5120 samples at 16kHz
        expected_samples = 16 * 320  # 5120 samples at 16kHz

        if len(normalized) < expected_samples:
            # Pad with zeros (silence at end)
            original_length = len(normalized)
            normalized = np.pad(
                normalized,
                (0, expected_samples - len(normalized)),
                mode="constant",
            )
            self._logger.debug(
                "wake.audio_padded",
                original_length=original_length,
                padded_length=expected_samples,
                padding_samples=expected_samples - original_length,
            )
        elif len(normalized) > expected_samples:
            # Truncate to expected length (take last N samples to preserve recent audio)
            original_length = len(normalized)
            normalized = normalized[-expected_samples:]
            self._logger.debug(
                "wake.audio_truncated",
                original_length=original_length,
                truncated_length=expected_samples,
                discarded_samples=original_length - expected_samples,
            )

        # Convert back to int16 for OpenWakeWord (requires 16-bit PCM)
        # Clamp to [-1, 1] range to prevent overflow when converting back
        normalized_clamped = np.clip(normalized, -1.0, 1.0)
        # Convert to int16: multiply by 32768.0 (symmetric with normalization) and cast
        # Using 32768.0 instead of 32767.0 for symmetric conversion (eliminates amplitude loss)
        # Clamp after multiplication to prevent overflow (32768.0 * 1.0 = 32768 overflows int16)
        audio_float = normalized_clamped * 32768.0
        audio_int16 = np.clip(audio_float, -32768.0, 32767.0).astype(np.int16)

        self._logger.debug(
            "wake.format_conversion",
            original_dtype="float32",
            converted_dtype="int16",
            sample_count=len(audio_int16),
        )

        # openwakeword.Model.predict() requires numpy array, not list
        try:
            scores = self._model.predict(audio_int16)
        except TypeError:
            # Fallback for models that require sample_rate parameter
            scores = self._model.predict(
                audio_int16,
                sample_rate=self._target_sample_rate,
            )
        except Exception as exc:
            self._logger.error("wake.audio_inference_failed", error=str(exc))
            return None
        if not isinstance(scores, dict) or not scores:
            self._logger.debug(
                "wake.invalid_scores",
                scores_type=type(scores).__name__,
                scores_empty=not scores if isinstance(scores, dict) else True,
            )
            return None
        phrase, score = max(scores.items(), key=lambda item: item[1])
        self._logger.debug(
            "wake.detection_scores",
            all_scores=scores,  # Log all scores for debugging
            max_phrase=phrase,
            max_score=score,
            threshold=self._threshold,
            above_threshold=score is not None and score >= self._threshold
            if score is not None
            else False,
        )
        if score is None or score < self._threshold:
            return None
        return WakeDetectionResult(str(phrase), float(score), "audio")

    def detect_transcript(self, transcript: str | None) -> WakeDetectionResult | None:
        """Detect wake phrase from transcribed text.

        Note: Transcript-based detection is disabled as wake phrases are determined
        by the model itself, not by configuration.

        Args:
            transcript: Transcribed text to search

        Returns:
            None (transcript detection disabled)
        """
        # Transcript-based detection disabled - model determines wake phrases
        return None

    def detect(
        self,
        pcm_or_segment: bytes | Any | None,
        sample_rate: int | None = None,
        transcript: str | None = None,
    ) -> WakeDetectionResult | None:
        """Detect wake phrase from audio first, then fall back to transcript.

        Supports both new signature (pcm, sample_rate, transcript) and legacy signature
        (AudioSegment, transcript) for backward compatibility.

        Args:
            pcm_or_segment: Raw PCM bytes OR AudioSegment-like object with .pcm and .sample_rate
            sample_rate: Sample rate in Hz (required if pcm_or_segment is bytes, ignored if AudioSegment)
            transcript: Transcribed text (optional)

        Returns:
            WakeDetectionResult if wake phrase detected, None otherwise
        """
        pcm: bytes | None = None
        detected_sample_rate: int | None = None

        # Handle backward compatibility: if first arg looks like AudioSegment
        if pcm_or_segment is not None and not isinstance(pcm_or_segment, bytes):
            # Assume it's an AudioSegment-like object
            if hasattr(pcm_or_segment, "pcm") and hasattr(
                pcm_or_segment, "sample_rate"
            ):
                pcm = pcm_or_segment.pcm
                detected_sample_rate = pcm_or_segment.sample_rate
            else:
                # Invalid input - not bytes and not AudioSegment-like
                return None
        else:
            # New signature: pcm, sample_rate, transcript
            pcm = pcm_or_segment
            detected_sample_rate = sample_rate

        # Try audio detection first
        if pcm and detected_sample_rate is not None:
            audio_result = self.detect_audio(pcm, detected_sample_rate)
            if audio_result:
                return audio_result

        # Fall back to transcript detection
        if transcript:
            return self.detect_transcript(transcript)

        return None

    def _resample(self, pcm: bytes, sample_rate: int) -> bytes:
        """Resample audio to target sample rate using audioop.ratecv().

        Uses audioop.ratecv() (fast, lower quality) instead of librosa.resample()
        because wake detection is performance-critical and runs on every audio frame.
        For quality-critical paths (e.g., STT preprocessing), use librosa.resample()
        instead (see services/common/audio.py:resample_audio()).
        """
        if sample_rate == self._target_sample_rate:
            return pcm
        try:
            converted, _ = audioop.ratecv(
                pcm, 2, 1, sample_rate, self._target_sample_rate, None
            )
            return converted
        except Exception as exc:
            self._logger.warning(
                "wake.resample_failed",
                error=str(exc),
                source_rate=sample_rate,
                target_rate=self._target_sample_rate,
            )
            return b""

    def matches(self, transcript: str) -> bool:
        """Check if transcript matches any wake phrase."""
        return self.detect_transcript(transcript) is not None

    def first_match(self, transcript: str) -> str | None:
        """Get first matching wake phrase from transcript."""
        detection = self.detect_transcript(transcript)
        return detection.phrase if detection else None

    def filter_segments(self, transcripts: Iterable[str]) -> list[str]:
        """Filter transcripts to only those containing wake phrases."""
        return [segment for segment in transcripts if self.matches(segment)]


__all__ = ["WakeDetectionResult", "WakeDetector"]
