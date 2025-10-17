from __future__ import annotations

import asyncio
import io
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from piper import PiperVoice
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field, model_validator

from services.common.logging import configure_logging, get_logger


def _env_bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    value = default
    if raw is not None:
        from contextlib import suppress

        with suppress(ValueError):
            value = int(raw)
    value = max(value, minimum)
    value = min(value, maximum)
    return value


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.getenv(name)
    value = default
    if raw is not None:
        from contextlib import suppress

        with suppress(ValueError):
            value = float(raw)
    value = max(value, minimum)
    value = min(value, maximum)
    return value


configure_logging(
    os.getenv("LOG_LEVEL", "INFO"),
    json_logs=_env_bool("LOG_JSON", "true"),
    service_name="tts",
)
logger = get_logger(__name__, service_name="tts")

app = FastAPI(title="Piper Text-to-Speech Service")

_MODEL_PATH = os.getenv("TTS_MODEL_PATH")
_MODEL_CONFIG_PATH = os.getenv("TTS_MODEL_CONFIG_PATH")
_DEFAULT_VOICE = os.getenv("TTS_DEFAULT_VOICE")
_MAX_TEXT_LENGTH = _env_int("TTS_MAX_TEXT_LENGTH", 1000, minimum=32, maximum=10000)
_MAX_CONCURRENCY = _env_int("TTS_MAX_CONCURRENCY", 4, minimum=1, maximum=64)
_RATE_LIMIT_PER_MINUTE = _env_int(
    "TTS_RATE_LIMIT_PER_MINUTE", 60, minimum=0, maximum=100000
)
_AUTH_TOKEN = os.getenv("TTS_AUTH_TOKEN")
_DEFAULT_LENGTH_SCALE = _env_float("TTS_LENGTH_SCALE", 1.0, minimum=0.1, maximum=3.0)
_DEFAULT_NOISE_SCALE = _env_float("TTS_NOISE_SCALE", 0.667, minimum=0.0, maximum=2.0)
_DEFAULT_NOISE_W = _env_float("TTS_NOISE_W", 0.8, minimum=0.0, maximum=2.0)

_CONCURRENCY_SEMAPHORE = asyncio.Semaphore(_MAX_CONCURRENCY)
_RATE_LIMIT_LOCK = asyncio.Lock()
_RATE_LIMIT_STATE: dict[str, tuple[int, int]] = {}
_VOICE: PiperVoice | None = None
_VOICE_SAMPLE_RATE: int = 0
_VOICE_OPTIONS: list[VoiceOption] = []
_VOICE_LOOKUP: dict[str, VoiceOption] = {}

# Debug manager for saving debug files

_SYNTHESIS_COUNTER = Counter(
    "tts_requests_total",
    "Total TTS synthesis requests",
    ["status"],
)
_SYNTHESIS_DURATION = Histogram(
    "tts_synthesis_seconds",
    "TTS synthesis latency",
    buckets=(0.25, 0.5, 1, 2, 4, 8, 16, float("inf")),
)
_SYNTHESIS_SIZE = Histogram(
    "tts_audio_bytes",
    "Size of generated audio payloads",
    buckets=(1024, 4096, 8192, 16384, 32768, 65536, 131072, 262144, float("inf")),
)

_SSML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class VoiceOption:
    key: str
    speaker_id: int | None
    language: str | None

    def as_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"id": self.key}
        if self.speaker_id is not None:
            payload["speaker_id"] = self.speaker_id
        if self.language:
            payload["language"] = self.language
        return payload


class SynthesisRequest(BaseModel):
    text: str | None = Field(None, max_length=_MAX_TEXT_LENGTH)
    ssml: str | None = Field(None, max_length=_MAX_TEXT_LENGTH)
    voice: str | None = None
    length_scale: float | None = Field(None, ge=0.1, le=3.0)
    noise_scale: float | None = Field(None, ge=0.0, le=2.0)
    noise_w: float | None = Field(None, ge=0.0, le=2.0)
    correlation_id: str | None = None

    @model_validator(mode="before")  # type: ignore[misc]
    @classmethod
    def _check_text_or_ssml(cls, data: Any) -> Any:
        if isinstance(data, dict):
            text = (data.get("text") or "").strip()
            ssml = (data.get("ssml") or "").strip()
            if not text and not ssml:
                raise ValueError("either text or ssml must be provided")
            data["text"] = text or None
            data["ssml"] = ssml or None
        return data


class VoiceListResponse(BaseModel):
    sample_rate: int
    voices: list[dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    sample_rate: int
    max_concurrency: int


async def _require_auth(authorization: str | None = Header(None)) -> None:
    if not _AUTH_TOKEN:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="unauthorized")
    token = authorization.split(" ", 1)[1]
    if token != _AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


async def _enforce_rate_limit(request: Request) -> None:
    if _RATE_LIMIT_PER_MINUTE <= 0:
        return
    client_host = request.headers.get("x-forwarded-for")
    if not client_host and request.client:
        client_host = request.client.host
    key = client_host or "anonymous"
    window = int(time.time() // 60)
    async with _RATE_LIMIT_LOCK:
        count, stored_window = _RATE_LIMIT_STATE.get(key, (0, window))
        if stored_window != window:
            count = 0
            stored_window = window
        if count >= _RATE_LIMIT_PER_MINUTE:
            raise HTTPException(status_code=429, detail="rate limit exceeded")
        _RATE_LIMIT_STATE[key] = (count + 1, stored_window)
        if len(_RATE_LIMIT_STATE) > 10000:
            # Prevent unbounded growth in the rate-limit map
            _RATE_LIMIT_STATE.pop(next(iter(_RATE_LIMIT_STATE)))


def _read_voice_language(config_data: dict[str, Any]) -> str | None:
    frontend = config_data.get("frontend") or {}
    language = frontend.get("phoneme_language") or frontend.get("phonemeLanguage")
    return language


def _load_voice() -> None:
    global _VOICE, _VOICE_SAMPLE_RATE, _VOICE_OPTIONS, _VOICE_LOOKUP
    if not _MODEL_PATH or not os.path.exists(_MODEL_PATH):
        logger.warning(
            "TTS_MODEL_PATH is not set or the file does not exist - TTS service will run in degraded mode"
        )
        _VOICE = None
        _VOICE_SAMPLE_RATE = 22050  # Default sample rate
        _VOICE_OPTIONS = []
        _VOICE_LOOKUP = {}
        return
    if not _MODEL_CONFIG_PATH or not os.path.exists(_MODEL_CONFIG_PATH):
        logger.warning(
            "TTS_MODEL_CONFIG_PATH is not set or the file does not exist - TTS service will run in degraded mode"
        )
        _VOICE = None
        _VOICE_SAMPLE_RATE = 22050  # Default sample rate
        _VOICE_OPTIONS = []
        _VOICE_LOOKUP = {}
        return

    # Load the voice model using file paths directly
    _VOICE = PiperVoice.load(_MODEL_PATH, _MODEL_CONFIG_PATH)

    # Read config for metadata extraction
    with open(_MODEL_CONFIG_PATH, encoding="utf-8") as config_file:
        config_data = json.load(config_file)
    sample_rate = (
        config_data.get("sample_rate")
        or config_data.get("sampleRate")
        or config_data.get("audio", {}).get("sample_rate")
        or getattr(_VOICE, "sample_rate", None)
    )
    if not sample_rate:
        raise RuntimeError("Unable to determine Piper sample rate from config")
    _VOICE_SAMPLE_RATE = int(sample_rate)

    language = _read_voice_language(config_data)
    speaker_map = (
        config_data.get("speaker_id_map") or config_data.get("speakerIdMap") or {}
    )

    _VOICE_OPTIONS = []
    _VOICE_LOOKUP = {}

    if speaker_map:
        for name, raw_id in speaker_map.items():
            speaker_id = int(raw_id)
            option = VoiceOption(key=name, speaker_id=speaker_id, language=language)
            _VOICE_OPTIONS.append(option)
            _VOICE_LOOKUP[name.lower()] = option
            _VOICE_LOOKUP[str(speaker_id)] = option
    else:
        option = VoiceOption(key="default", speaker_id=None, language=language)
        _VOICE_OPTIONS.append(option)
        _VOICE_LOOKUP["default"] = option
        _VOICE_LOOKUP[""] = option

    if _DEFAULT_VOICE and _DEFAULT_VOICE.lower() not in _VOICE_LOOKUP:
        raise RuntimeError(
            f"Configured default voice {_DEFAULT_VOICE!r} is not present in model"
        )

    logger.info(
        "tts.voice_loaded",
        model_path=_MODEL_PATH,
        config_path=_MODEL_CONFIG_PATH,
        voices=len(_VOICE_OPTIONS),
        sample_rate=_VOICE_SAMPLE_RATE,
    )


def _resolve_voice(preferred: str | None) -> VoiceOption:
    if not _VOICE_OPTIONS:
        raise HTTPException(status_code=503, detail="voice catalog unavailable")
    candidate = (preferred or _DEFAULT_VOICE or "").strip()
    if not candidate:
        return _VOICE_OPTIONS[0]
    option = _VOICE_LOOKUP.get(candidate.lower())
    if option is None:
        raise HTTPException(
            status_code=400, detail=f"voice {candidate!r} not available"
        )
    return option


def _strip_ssml(text: str) -> str:
    return _SSML_TAG_RE.sub("", text)


def _generate_silence_audio(sample_rate: int, duration: float = 1.0) -> bytes:
    """Generate a minimal WAV file with silence using standardized audio processing."""
    from services.common.audio import AudioProcessor

    processor = AudioProcessor("tts")

    try:
        # Generate silence data
        num_samples = int(sample_rate * duration)
        silence_data = b"\x00" * (num_samples * 2)  # 16-bit samples

        # Use standardized audio processing to create WAV
        wav_data = processor.pcm_to_wav(silence_data, sample_rate, 1, 2)
        return wav_data

    except Exception:
        # Fallback to original implementation
        import struct

        # Generate 1 second of silence
        num_samples = int(sample_rate * duration)
        silence_data = b"\x00" * (num_samples * 2)  # 16-bit samples

        # Create WAV header
        wav_header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + len(silence_data),
            b"WAVE",
            b"fmt ",
            16,  # fmt chunk size
            1,  # PCM format
            1,  # mono
            sample_rate,
            sample_rate * 2,  # byte rate
            2,  # block align
            16,  # bits per sample
            b"data",
            len(silence_data),
        )

        return wav_header + silence_data


def _synthesize_audio(
    text: str,
    *,
    is_ssml: bool,
    option: VoiceOption,
    length_scale: float,
    noise_scale: float,
    noise_w: float,
) -> tuple[bytes, int]:
    if _VOICE is None:
        # Return a minimal WAV file with silence when no model is loaded
        logger.warning("TTS model not loaded - returning silence audio")
        return _generate_silence_audio(_VOICE_SAMPLE_RATE), _VOICE_SAMPLE_RATE
    buffer = io.BytesIO()

    # The Piper library synthesize method only accepts text and optional syn_config
    # We need to use the synthesize method that returns an iterable of audio chunks
    audio_chunks = _VOICE.synthesize(text)

    # Write the audio chunks to the buffer
    for chunk in audio_chunks:
        buffer.write(chunk.audio_int16_bytes)
    audio_bytes = buffer.getvalue()
    if not audio_bytes:
        raise RuntimeError("Piper returned an empty audio buffer")
    return audio_bytes, getattr(_VOICE, "sample_rate", _VOICE_SAMPLE_RATE)


@app.on_event("startup")  # type: ignore[misc]
async def _startup() -> None:
    await asyncio.to_thread(_load_voice)
    logger.info(
        "tts.startup_complete",
        max_concurrency=_MAX_CONCURRENCY,
        rate_limit=_RATE_LIMIT_PER_MINUTE,
        auth_enabled=bool(_AUTH_TOKEN),
    )


@app.get("/health", response_model=HealthResponse)  # type: ignore[misc]
async def health() -> HealthResponse:
    status = "ok" if _VOICE is not None else "degraded"
    return HealthResponse(
        status=status,
        sample_rate=_VOICE_SAMPLE_RATE,
        max_concurrency=_MAX_CONCURRENCY,
    )


@app.get("/metrics")  # type: ignore[misc]
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/voices", response_model=VoiceListResponse)  # type: ignore[misc]
async def list_voices(_: None = Depends(_require_auth)) -> VoiceListResponse:
    if not _VOICE_OPTIONS:
        # Return a default voice option when no model is loaded
        default_voice = VoiceOption(key="default", speaker_id=None, language="en")
        voices = [default_voice.as_payload()]
    else:
        voices = [option.as_payload() for option in _VOICE_OPTIONS]
    return VoiceListResponse(sample_rate=_VOICE_SAMPLE_RATE, voices=voices)


@app.post("/synthesize")  # type: ignore[misc]
async def synthesize(
    payload: SynthesisRequest,
    _: None = Depends(_require_auth),
    __: None = Depends(_enforce_rate_limit),
) -> dict[str, Any]:
    start_time = time.perf_counter()

    text_source = payload.ssml if payload.ssml else payload.text or ""
    is_ssml = bool(payload.ssml)
    text_length = len(_strip_ssml(text_source)) if is_ssml else len(text_source)

    option = _resolve_voice(payload.voice)
    length_scale = payload.length_scale or _DEFAULT_LENGTH_SCALE
    noise_scale = payload.noise_scale or _DEFAULT_NOISE_SCALE
    noise_w = payload.noise_w or _DEFAULT_NOISE_W

    async with _CONCURRENCY_SEMAPHORE:
        try:
            audio_bytes, sample_rate = await asyncio.to_thread(
                _synthesize_audio,
                text_source,
                is_ssml=is_ssml,
                option=option,
                length_scale=length_scale,
                noise_scale=noise_scale,
                noise_w=noise_w,
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("tts.synthesize_failed", error=str(exc))
            _SYNTHESIS_COUNTER.labels(status="error").inc()
            raise HTTPException(
                status_code=500, detail="unable to synthesize audio"
            ) from exc

    size_bytes = len(audio_bytes)
    duration = time.perf_counter() - start_time
    _SYNTHESIS_DURATION.observe(duration)
    _SYNTHESIS_SIZE.observe(size_bytes)

    from services.common.correlation import generate_tts_correlation_id

    audio_id = payload.correlation_id or generate_tts_correlation_id()
    headers = {
        "X-Audio-Id": audio_id,
        "X-Audio-Voice": option.key,
        "X-Audio-Sample-Rate": str(sample_rate),
        "X-Audio-Size": str(size_bytes),
    }
    _SYNTHESIS_COUNTER.labels(status="success").inc()
    logger.info(
        "tts.synthesize_stream_success",
        audio_id=audio_id,
        voice=option.key,
        ssml=is_ssml,
        text_length=text_length,
        size_bytes=size_bytes,
        duration_ms=int(duration * 1000),
    )


    return StreamingResponse(  # type: ignore[no-any-return]
        iter([audio_bytes]), media_type="audio/wav", headers=headers
    )




__all__ = ["app"]
