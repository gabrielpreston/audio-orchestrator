"""Wake phrase detection helpers leveraging openwakeword when available."""

from __future__ import annotations

import audioop
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Literal, Optional, Pattern, TYPE_CHECKING

import numpy as np

from services.common.logging import get_logger

try:  # pragma: no cover - optional dependency import guard
    from openwakeword import Model as WakeWordModel
except Exception:  # pragma: no cover - gracefully degrade when package missing
    WakeWordModel = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from .audio import AudioSegment
    from .config import WakeConfig


@dataclass(slots=True)
class WakeDetectionResult:
    """Details about a detected wake phrase."""

    phrase: str
    confidence: Optional[float]
    source: Literal["audio", "transcript"]


class WakeDetector:
    """Detect wake phrases from transcripts and raw audio."""

    def __init__(self, config: "WakeConfig") -> None:
        self._config = config
        self._logger = get_logger(__name__, service_name="discord")
        self._pattern: Optional[Pattern[str]] = self._compile_pattern(config.wake_phrases)
        self._target_sample_rate = config.target_sample_rate_hz
        self._threshold = config.activation_threshold
        self._model = self._load_model(config.model_paths)

    def _compile_pattern(self, phrases: Iterable[str]) -> Optional[Pattern[str]]:
        cleaned = [re.escape(phrase.strip()) for phrase in phrases if phrase.strip()]
        if not cleaned:
            return None
        return re.compile(r"(?:^|\b)(" + "|".join(cleaned) + r")(?:\b|$)", re.IGNORECASE)

    def _load_model(self, paths: Iterable[Path]):
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
        except Exception as exc:  # noqa: BLE001
            self._logger.error(
                "wake.model_load_failed",
                error=str(exc),
                model_paths=model_paths,
            )
            return None

    def detect(self, segment: "AudioSegment", transcript: Optional[str]) -> Optional[WakeDetectionResult]:
        """Detect a wake phrase from audio first, then fall back to transcripts."""

        audio_result = self._detect_audio(segment.pcm, segment.sample_rate)
        if audio_result:
            return audio_result
        if transcript and self._pattern:
            match = self._pattern.search(transcript)
            if match:
                return WakeDetectionResult(match.group(0).lower(), None, "transcript")
        return None

    def _detect_audio(self, pcm: bytes, sample_rate: int) -> Optional[WakeDetectionResult]:
        if not pcm or self._model is None:
            return None
        converted = self._resample(pcm, sample_rate)
        if not converted:
            return None
        normalized = np.frombuffer(converted, dtype=np.int16).astype(np.float32) / 32768.0
        payload = normalized.tolist()
        try:
            scores = self._model.predict(payload)  # type: ignore[arg-type]
        except TypeError:
            scores = self._model.predict(payload, sample_rate=self._target_sample_rate)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            self._logger.error("wake.audio_inference_failed", error=str(exc))
            return None
        if not isinstance(scores, dict) or not scores:
            return None
        phrase, score = max(scores.items(), key=lambda item: item[1])
        if score is None or score < self._threshold:
            return None
        return WakeDetectionResult(str(phrase), float(score), "audio")

    def _resample(self, pcm: bytes, sample_rate: int) -> bytes:
        if sample_rate == self._target_sample_rate:
            return pcm
        try:
            converted, _ = audioop.ratecv(pcm, 2, 1, sample_rate, self._target_sample_rate, None)
            return converted
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "wake.resample_failed",
                error=str(exc),
                source_rate=sample_rate,
                target_rate=self._target_sample_rate,
            )
            return b""

    def matches(self, transcript: str) -> bool:
        if not transcript or not self._pattern:
            return False
        return bool(self._pattern.search(transcript))

    def first_match(self, transcript: str) -> Optional[str]:
        if not transcript or not self._pattern:
            return None
        match = self._pattern.search(transcript)
        return match.group(0).lower() if match else None

    def filter_segments(self, transcripts: Iterable[str]) -> List[str]:
        if not self._pattern:
            return list(transcripts)
        return [segment for segment in transcripts if self.matches(segment)]


__all__ = ["WakeDetector", "WakeDetectionResult"]
