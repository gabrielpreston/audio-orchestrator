"""Wake phrase detection helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List


@dataclass(slots=True)
class WakeDetector:
    """Detects wake phrases using case-insensitive matching."""

    wake_phrases: List[str]
    _pattern: re.Pattern[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        patterns = [re.escape(phrase.strip()) for phrase in self.wake_phrases if phrase.strip()]
        if not patterns:
            raise ValueError("WakeDetector requires at least one phrase")
        self._pattern = re.compile(r"(?:^|\b)(" + "|".join(patterns) + r")(?:\b|$)", re.IGNORECASE)

    def matches(self, transcript: str) -> bool:
        """Return True if the transcript contains a wake phrase."""

        if not transcript:
            return False
        return bool(self._pattern.search(transcript))

    def first_match(self, transcript: str) -> str | None:
        """Return the first matching wake phrase, if any."""

        match = self._pattern.search(transcript)
        return match.group(0).lower() if match else None

    def filter_segments(self, transcripts: Iterable[str]) -> List[str]:
        """Return only segments that contain a wake phrase."""

        return [segment for segment in transcripts if self.matches(segment)]


__all__ = ["WakeDetector"]
