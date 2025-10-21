"""Client for the speech-to-text service."""

from __future__ import annotations

import asyncio

# audioop is deprecated, using alternative approach
import io
import time
import wave
from dataclasses import dataclass
from types import TracebackType
from typing import Any

import httpx

from services.common.circuit_breaker import CircuitBreakerConfig
from services.common.logging import get_logger
from services.common.resilient_http import ResilientHTTPClient, ServiceUnavailableError


# Prometheus metrics
try:
    from prometheus_client import Counter, Histogram

    PROMETHEUS_AVAILABLE = True

    stt_requests = Counter("stt_requests_total", "Total STT requests", ["service", "status"])

    stt_latency = Histogram(
        "stt_latency_seconds",
        "STT request latency",
        ["service"],
        buckets=(0.25, 0.5, 1, 2, 4, 8, 16, float("inf")),
    )
    pre_stt_encode = Histogram(
        "pre_stt_encode_seconds",
        "PCM to WAV encode latency prior to STT submission",
        ["service"],
        buckets=(
            0.001,
            0.005,
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1,
            2,
            4,
            float("inf"),
        ),
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    stt_requests = None
    stt_latency = None

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
    # Optional timing fields for downstream aggregation
    stt_latency_ms: int | None = None
    pre_stt_encode_ms: int | None = None


class TranscriptionClient:
    """Async client that sends audio segments to the STT service with resilience."""

    def __init__(self, config: STTConfig, *, session: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._session = session
        self._owns_session = session is None
        self._logger = get_logger(__name__, service_name="discord")

        # Set up resilient HTTP client with circuit breaker
        circuit_config = CircuitBreakerConfig(
            failure_threshold=5, success_threshold=2, timeout_seconds=30.0
        )
        self._http_client = ResilientHTTPClient(
            service_name="stt", base_url=config.base_url, circuit_config=circuit_config
        )

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

    async def check_health(self) -> bool:
        """Check if the STT service is healthy."""
        return bool(await self._http_client.check_health())

    async def transcribe(self, segment: AudioSegment) -> TranscriptResult | None:
        if not self._session:
            raise RuntimeError("TranscriptionClient must be used as an async context manager")

        from services.common.logging import bind_correlation_id

        logger = bind_correlation_id(self._logger, segment.correlation_id)

        # Pre-STT preprocessing: convert PCM -> WAV exactly once off the event loop thread
        pre_start = time.monotonic()
        encode_start = pre_start
        wav_bytes = await asyncio.to_thread(
            _pcm_to_wav, segment.pcm, sample_rate=segment.sample_rate
        )
        encode_ms = int((time.monotonic() - encode_start) * 1000)
        if PROMETHEUS_AVAILABLE and pre_stt_encode:
            from contextlib import suppress

            with suppress(Exception):
                pre_stt_encode.labels(service="discord").observe(encode_ms / 1000.0)

        # Log STT request initiation after conversion so audio_bytes is accurate
        logger.info(
            "stt.request_initiated",
            correlation_id=segment.correlation_id,
            user_id=segment.user_id,
            audio_bytes=len(wav_bytes),
            duration=segment.duration,
            sample_rate=segment.sample_rate,
            frames=segment.frame_count,
            language=self._config.forced_language,
            pre_stt_encode_ms=encode_ms,
            pre_stt_total_ms=encode_ms,  # currently dominated by encode step
        )

        start_time = time.monotonic()

        # Record metrics if Prometheus is available
        if PROMETHEUS_AVAILABLE and stt_latency:
            with stt_latency.labels(service="discord").time():
                result = await self._do_transcribe(
                    segment, logger, start_time, wav_bytes, encode_ms
                )
        else:
            result = await self._do_transcribe(segment, logger, start_time, wav_bytes, encode_ms)

        # Record request metrics
        if PROMETHEUS_AVAILABLE and stt_requests:
            status = "success" if result else "failure"
            stt_requests.labels(service="discord", status=status).inc()

        return result

    async def _do_transcribe(
        self,
        segment: AudioSegment,
        logger: Any,
        start_time: float,
        wav_bytes: bytes,
        encode_ms: int,
    ) -> TranscriptResult | None:
        """Internal transcription logic. Expects prebuilt WAV bytes."""
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
        if getattr(self._config, "beam_size", None):
            params["beam_size"] = str(self._config.beam_size)  # type: ignore[attr-defined]
        if getattr(self._config, "word_timestamps", False):
            params["word_timestamps"] = "true"

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
            # Check if STT is healthy before attempting
            if not await self._http_client.check_health():
                circuit_state = "unknown"
                if (
                    hasattr(self._http_client, "_circuit_breaker")
                    and self._http_client._circuit_breaker
                ):
                    circuit_state = self._http_client._circuit_breaker.get_state().value
                logger.warning(
                    "stt.service_not_ready",
                    correlation_id=segment.correlation_id,
                    circuit_state=circuit_state,
                    action="dropping_segment",
                )
                return None

            # Pass correlation ID in headers
            headers = {"X-Correlation-ID": segment.correlation_id}

            response = await self._http_client.post_with_retry(
                "/transcribe",
                files=files,
                data=data,
                headers=headers,
                params=params or None,
                timeout=request_timeout,
                max_retries=self._config.max_retries,
                log_fields={"correlation_id": segment.correlation_id},
                logger=logger,
            )
        except ServiceUnavailableError:
            logger.warning(
                "stt.circuit_open",
                correlation_id=segment.correlation_id,
                action="dropping_segment",
            )
            return None
        except Exception as exc:
            logger.error(
                "stt.request_failed",
                error=str(exc),
                correlation_id=segment.correlation_id,
            )
            return None
        payload = response.json()
        await response.aclose()
        text = payload.get("text", "")

        # Log STT response with latency

        latency_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "stt.response_received",
            correlation_id=segment.correlation_id,
            user_id=segment.user_id,
            text_length=len(text),
            confidence=payload.get("confidence"),
            language=payload.get("language"),
            latency_ms=latency_ms,
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
            stt_latency_ms=latency_ms,
            pre_stt_encode_ms=encode_ms,
        )

    def get_circuit_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        try:
            if (
                hasattr(self._http_client, "_circuit_breaker")
                and self._http_client._circuit_breaker is not None
            ):
                stats = self._http_client._circuit_breaker.get_stats()
                return dict(stats) if stats else {"state": "unknown", "available": True}
            return {"state": "unknown", "available": True}
        except Exception:
            return {"state": "unknown", "available": True}


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
        return bytes(result.audio_data)
    else:
        # Fallback to original implementation if conversion fails
        if sample_rate != target_sample_rate and pcm:
            try:
                from services.common.audio import resample_audio

                pcm = resample_audio(pcm, sample_rate, target_sample_rate, sample_width=2)
                sample_rate = target_sample_rate
            except Exception as e:
                # Fall back to the original sample rate if resampling fails.
                logger = get_logger(__name__, service_name="discord")
                logger.debug(
                    "Audio resampling failed, using original sample rate",
                    extra={"error": str(e)},
                )

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            # Linter incorrectly identifies this as Wave_read, but it's actually Wave_write
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm)
        return buffer.getvalue()


__all__ = ["TranscriptResult", "TranscriptionClient"]
