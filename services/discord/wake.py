"""Wake phrase detection helpers leveraging openwakeword when available."""

from __future__ import annotations

import audioop
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from rapidfuzz import fuzz, process, utils

from services.common.logging import get_logger


try:  # pragma: no cover - optional dependency import guard
    from openwakeword import Model as WakeWordModel
except Exception:  # pragma: no cover - gracefully degrade when package missing
    WakeWordModel = None

if TYPE_CHECKING:
    from .audio import AudioSegment
    from .config import WakeConfig


@dataclass(slots=True)
class WakeDetectionResult:
    """Details about a detected wake phrase."""

    phrase: str
    confidence: float | None
    source: Literal["audio", "transcript"]


class WakeDetector:
    """Detect wake phrases from transcripts and raw audio."""

    _TRANSCRIPT_SCORE_CUTOFF = 90.0  # RapidFuzz scores range from 0 to 100.

    def __init__(self, config: WakeConfig) -> None:
        self._config = config
        self._logger = get_logger(__name__, service_name="discord")
        self._phrases: list[str] = [
            phrase.strip()
            for phrase in config.wake_phrases
            if phrase and phrase.strip()
        ]
        self._normalized_phrases: list[str] = [
            self._normalize_phrase(phrase) for phrase in self._phrases
        ]
        self._target_sample_rate = config.target_sample_rate_hz
        self._threshold = config.activation_threshold
        self._model = self._load_model(config.model_paths)

    def _load_model(self, paths: Iterable[Path]) -> Any:
        model_paths = [str(path) for path in paths if path]
        if not model_paths:
            return None
        if WakeWordModel is None:
            self._logger.warning(
                "wake.openwakeword_unavailable",
                model_paths=model_paths,
            )
            return None
        try:
            return WakeWordModel(wakeword_model_paths=model_paths)
        except Exception as exc:
            self._logger.error(
                "wake.model_load_failed",
                error=str(exc),
                model_paths=model_paths,
            )
            return None

    def detect(
        self,
        segment: AudioSegment,
        transcript: str | None,
    ) -> WakeDetectionResult | None:
        """Detect a wake phrase from audio first, then fall back to transcripts."""
        from services.common.logging import bind_correlation_id

        logger = bind_correlation_id(self._logger, segment.correlation_id)

        # Log wake detection attempt
        logger.debug(
            "wake.detection_attempt",
            correlation_id=segment.correlation_id,
            user_id=segment.user_id,
            transcript_preview=transcript[:120] if transcript else None,
            wake_phrases=self._phrases,
            enabled=self._config.enabled,
        )

        if not self._config.enabled:
            result = WakeDetectionResult(
                phrase="testing_mode",
                confidence=1.0,
                source="transcript",
            )
            logger.info(
                "wake.detection_result",
                correlation_id=segment.correlation_id,
                user_id=segment.user_id,
                detected=True,
                phrase=result.phrase,
                confidence=result.confidence,
                source=result.source,
            )
            return result

        audio_result = self._detect_audio(segment.pcm, segment.sample_rate)
        if audio_result:
            logger.info(
                "wake.detection_result",
                correlation_id=segment.correlation_id,
                user_id=segment.user_id,
                detected=True,
                phrase=audio_result.phrase,
                confidence=audio_result.confidence,
                source=audio_result.source,
            )
            return audio_result

        transcript_result = self._detect_transcript(transcript)
        if transcript_result:
            logger.info(
                "wake.detection_result",
                correlation_id=segment.correlation_id,
                user_id=segment.user_id,
                detected=True,
                phrase=transcript_result.phrase,
                confidence=transcript_result.confidence,
                source=transcript_result.source,
            )
            return transcript_result

        # Log no detection
        logger.info(
            "wake.detection_result",
            correlation_id=segment.correlation_id,
            user_id=segment.user_id,
            detected=False,
            phrase=None,
            confidence=None,
            source=None,
        )
        return None

    def _detect_audio(self, pcm: bytes, sample_rate: int) -> WakeDetectionResult | None:
        if not pcm or self._model is None:
            return None
        converted = self._resample(pcm, sample_rate)
        if not converted:
            return None
        normalized = (
            np.frombuffer(converted, dtype=np.int16).astype(np.float32) / 32768.0
        )
        payload = normalized.tolist()
        try:
            scores = self._model.predict(payload)
        except TypeError:
            scores = self._model.predict(
                payload,
                sample_rate=self._target_sample_rate,
            )
        except Exception as exc:
            self._logger.error("wake.audio_inference_failed", error=str(exc))
            return None
        if not isinstance(scores, dict) or not scores:
            return None
        phrase, score = max(scores.items(), key=lambda item: item[1])
        if score is None or score < self._threshold:
            return None
        return WakeDetectionResult(str(phrase), float(score), "audio")

    def _detect_transcript(self, transcript: str | None) -> WakeDetectionResult | None:
        if not transcript or not self._normalized_phrases:
            return None
        normalized_transcript = utils.default_process(transcript)
        if not normalized_transcript:
            return None
        match = process.extractOne(
            normalized_transcript,
            self._normalized_phrases,
            scorer=fuzz.partial_ratio,
            score_cutoff=self._TRANSCRIPT_SCORE_CUTOFF,
        )
        if not match:
            return None
        _, score, index = match
        if index < 0 or index >= len(
            self._phrases
        ):  # pragma: no cover - defensive guard
            return None
        phrase = self._phrases[index]
        confidence = float(score) / 100.0
        return WakeDetectionResult(phrase.lower(), confidence, "transcript")

    def _resample(self, pcm: bytes, sample_rate: int) -> bytes:
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
        return self._detect_transcript(transcript) is not None

    def first_match(self, transcript: str) -> str | None:
        detection = self._detect_transcript(transcript)
        return detection.phrase if detection else None

    def filter_segments(self, transcripts: Iterable[str]) -> list[str]:
        return [segment for segment in transcripts if self.matches(segment)]

    @staticmethod
    def _normalize_phrase(value: str) -> str:
        """Normalize phrases the same way RapidFuzz normalizes inputs."""

        return utils.default_process(value) or ""


__all__ = ["WakeDetectionResult", "WakeDetector"]
