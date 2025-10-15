"""Client for the speech-to-text service."""

from __future__ import annotations

import audioop
import io
import wave
from dataclasses import dataclass
from types import TracebackType
from typing import Any

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
    language: str | None
    confidence: float | None
    correlation_id: str
    raw_response: dict[str, Any]


class TranscriptionClient:
    """Async client that sends audio segments to the STT service."""

    def __init__(
        self, config: STTConfig, *, session: httpx.AsyncClient | None = None
    ) -> None:
        self._config = config
        self._session = session
        self._owns_session = session is None
        self._logger = get_logger(__name__, service_name="discord")

    async def __aenter__(self) -> TranscriptionClient:
        if self._session is None:
            timeout = httpx.Timeout(connect=5.0, read=None, write=None, pool=None)
            self._session = httpx.AsyncClient(timeout=timeout)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._owns_session and self._session:
            await self._session.aclose()

    async def transcribe(self, segment: AudioSegment) -> TranscriptResult:
        if not self._session:
            raise RuntimeError(
                "TranscriptionClient must be used as an async context manager"
            )

        wav_bytes = _pcm_to_wav(segment.pcm, sample_rate=segment.sample_rate)
        files = {
            "file": (
                f"segment-{segment.correlation_id}.wav",
                wav_bytes,
                "audio/wav",
            )
        }
        data = {"metadata": segment.correlation_id}
        params: dict[str, Any] = {}
        if self._config.forced_language:
            params["language"] = self._config.forced_language
        logger = self._logger.bind(correlation_id=segment.correlation_id)
        logger.debug(
            "stt.transcribe_request",
            frames=segment.frame_count,
            payload_bytes=len(wav_bytes),
            language=params.get("language"),
        )
        processing_timeout = max(
            self._config.request_timeout_seconds,
            (segment.duration * 4.0) + 5.0,
        )
        request_timeout = httpx.Timeout(
            connect=5.0,
            read=processing_timeout,
            write=processing_timeout,
            pool=None,
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
                params=params or None,
                timeout=request_timeout,
            )
        except Exception as exc:
            logger.error("stt.transcribe_failed", error=str(exc))
            raise
        payload = response.json()
        await response.aclose()
        text = payload.get("text", "")
        logger.info(
            "stt.transcribe_success",
            language=payload.get("language"),
            confidence=payload.get("confidence"),
            text_length=len(text),
        )
        if text:
            logger.debug("stt.transcribe_text", text=text)
        return TranscriptResult(
            text=payload.get("text", ""),
            start_timestamp=segment.start_timestamp,
            end_timestamp=segment.end_timestamp,
            language=payload.get("language"),
            confidence=payload.get("confidence"),
            correlation_id=segment.correlation_id,
            raw_response=payload,
        )


def _pcm_to_wav(
    pcm: bytes,
    *,
    sample_rate: int = 48000,
    channels: int = 1,
    target_sample_rate: int = 16000,
) -> bytes:
    """Encode raw PCM bytes into a WAV container using standardized audio processing."""
    from services.common.audio import AudioProcessor

    processor = AudioProcessor("discord")

    # Convert audio format using standardized processing
    result = processor.convert_audio_format(
        audio_data=pcm,
        from_format="pcm",
        to_format="wav",
        from_sample_rate=sample_rate,
        to_sample_rate=target_sample_rate,
        from_channels=channels,
        to_channels=channels,
        from_sample_width=2,
        to_sample_width=2,
    )

    if result.success:
        return result.audio_data
    else:
        # Fallback to original implementation if conversion fails
        if sample_rate != target_sample_rate and pcm:
            try:
                pcm, _ = audioop.ratecv(
                    pcm, 2, channels, sample_rate, target_sample_rate, None
                )
                sample_rate = target_sample_rate
            except Exception:
                # Fall back to the original sample rate if resampling fails.
                pass

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm)
        return buffer.getvalue()


__all__ = ["TranscriptResult", "TranscriptionClient"]
