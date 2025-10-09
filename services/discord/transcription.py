"""Client for the speech-to-text service."""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from services.common.http import post_with_retries
from services.common.logging import get_logger

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

    def __init__(self, config: STTConfig, *, session: Optional[httpx.AsyncClient] = None) -> None:
        self._config = config
        self._session = session
        self._owns_session = session is None
        self._logger = get_logger(__name__, service_name="discord")

    async def __aenter__(self) -> "TranscriptionClient":
        if self._session is None:
            timeout = httpx.Timeout(self._config.request_timeout_seconds, connect=5.0)
            self._session = httpx.AsyncClient(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        if self._owns_session and self._session:
            await self._session.aclose()

    async def transcribe(self, segment: AudioSegment) -> TranscriptResult:
        if not self._session:
            raise RuntimeError("TranscriptionClient must be used as an async context manager")

        wav_bytes = _pcm_to_wav(segment.pcm, sample_rate=segment.sample_rate)
        files = {
            "file": (
                f"segment-{segment.correlation_id}.wav",
                wav_bytes,
                "audio/wav",
            )
        }
        data = {"metadata": segment.correlation_id}
        logger = self._logger.bind(correlation_id=segment.correlation_id)
        logger.info(
            "stt.transcribe_request",
            frames=segment.frame_count,
            payload_bytes=len(wav_bytes),
        )
        try:
            response = await post_with_retries(
                self._session,
                f"{self._config.base_url}/transcribe",
                files=files,
                data=data,
                max_retries=self._config.max_retries,
                log_fields={"correlation_id": segment.correlation_id},
                logger=logger,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("stt.transcribe_failed", error=str(exc))
            raise
        payload = response.json()
        await response.aclose()
        logger.info(
            "stt.transcribe_success",
            language=payload.get("language"),
            confidence=payload.get("confidence"),
        )
        return TranscriptResult(
            text=payload.get("text", ""),
            start_timestamp=segment.start_timestamp,
            end_timestamp=segment.end_timestamp,
            language=payload.get("language"),
            confidence=payload.get("confidence"),
            correlation_id=segment.correlation_id,
            raw_response=payload,
        )


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
