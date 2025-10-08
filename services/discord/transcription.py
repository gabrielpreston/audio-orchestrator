"""Client for the speech-to-text service."""

from __future__ import annotations

import asyncio
import io
import wave
from dataclasses import dataclass
from typing import Any, Dict, Optional

import aiohttp

from .audio import AudioSegment
from .config import STTConfig


@dataclass(slots=True)
class TranscriptResult:
    """Structured response from the STT service."""

    text: str
    start_timestamp: float
    end_timestamp: float
    language: Optional[str]
    confidence: Optional[float]
    correlation_id: str
    raw_response: Dict[str, Any]


class TranscriptionClient:
    """Async client that sends audio segments to the STT service."""

    def __init__(self, config: STTConfig, *, session: Optional[aiohttp.ClientSession] = None) -> None:
        self._config = config
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self) -> "TranscriptionClient":
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self._config.request_timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        if self._owns_session and self._session:
            await self._session.close()

    async def transcribe(self, segment: AudioSegment) -> TranscriptResult:
        if not self._session:
            raise RuntimeError("TranscriptionClient must be used as an async context manager")

        attempt = 0
        while True:
            attempt += 1
            try:
                wav_bytes = _pcm_to_wav(segment.pcm)
                payload = aiohttp.FormData()
                payload.add_field(
                    "file",
                    wav_bytes,
                    filename=f"segment-{segment.correlation_id}.wav",
                    content_type="audio/wav",
                )
                payload.add_field("metadata", segment.correlation_id)
                assert self._session is not None
                async with self._session.post(f"{self._config.base_url}/transcribe", data=payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return TranscriptResult(
                        text=data.get("text", ""),
                        start_timestamp=segment.start_timestamp,
                        end_timestamp=segment.end_timestamp,
                        language=data.get("language"),
                        confidence=data.get("confidence"),
                        correlation_id=segment.correlation_id,
                        raw_response=data,
                    )
            except Exception as exc:  # noqa: BLE001
                if attempt >= self._config.max_retries:
                    raise
                backoff = min(2 ** (attempt - 1), 10)
                await asyncio.sleep(backoff)


def _pcm_to_wav(pcm: bytes, *, sample_rate: int = 48000, channels: int = 1) -> bytes:
    """Encode raw PCM bytes into a WAV container."""

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return buffer.getvalue()


__all__ = ["TranscriptionClient", "TranscriptResult"]
