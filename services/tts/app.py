from __future__ import annotations

import asyncio
import io
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from piper import PiperVoice
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field, root_validator

from services.common.logging import configure_logging, get_logger


def _env_bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    value = default
    if raw is not None:
        try:
            value = int(raw)
        except ValueError:
            pass
    if value < minimum:
        value = minimum
    if value > maximum:
        value = maximum
    return value


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.getenv(name)
    value = default
    if raw is not None:
        try:
            value = float(raw)
        except ValueError:
            pass
    if value < minimum:
        value = minimum
    if value > maximum:
        value = maximum
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
_RATE_LIMIT_PER_MINUTE = _env_int("TTS_RATE_LIMIT_PER_MINUTE", 60, minimum=0, maximum=100000)
_AUTH_TOKEN = os.getenv("TTS_AUTH_TOKEN")
_DEFAULT_LENGTH_SCALE = _env_float("TTS_LENGTH_SCALE", 1.0, minimum=0.1, maximum=3.0)
_DEFAULT_NOISE_SCALE = _env_float("TTS_NOISE_SCALE", 0.667, minimum=0.0, maximum=2.0)
_DEFAULT_NOISE_W = _env_float("TTS_NOISE_W", 0.8, minimum=0.0, maximum=2.0)

_CONCURRENCY_SEMAPHORE = asyncio.Semaphore(_MAX_CONCURRENCY)
_RATE_LIMIT_LOCK = asyncio.Lock()
_RATE_LIMIT_STATE: Dict[str, Tuple[int, int]] = {}
_VOICE: Optional[PiperVoice] = None
_VOICE_SAMPLE_RATE: int = 0
_VOICE_OPTIONS: List["VoiceOption"] = []
_VOICE_LOOKUP: Dict[str, "VoiceOption"] = {}

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
    speaker_id: Optional[int]
    language: Optional[str]

    def as_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"id": self.key}
        if self.speaker_id is not None:
            payload["speaker_id"] = self.speaker_id
        if self.language:
            payload["language"] = self.language
        return payload


class SynthesisRequest(BaseModel):
    text: Optional[str] = Field(None, max_length=_MAX_TEXT_LENGTH)
    ssml: Optional[str] = Field(None, max_length=_MAX_TEXT_LENGTH)
    voice: Optional[str] = None
    length_scale: Optional[float] = Field(None, ge=0.1, le=3.0)
    noise_scale: Optional[float] = Field(None, ge=0.0, le=2.0)
    noise_w: Optional[float] = Field(None, ge=0.0, le=2.0)

    @root_validator(pre=False)
    def _check_text_or_ssml(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        text = (values.get("text") or "").strip()
        ssml = (values.get("ssml") or "").strip()
        if not text and not ssml:
            raise ValueError("either text or ssml must be provided")
        values["text"] = text or None
        values["ssml"] = ssml or None
        return values


class VoiceListResponse(BaseModel):
    sample_rate: int
    voices: List[Dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    sample_rate: int
    max_concurrency: int


async def _require_auth(authorization: Optional[str] = Header(None)) -> None:
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


def _read_voice_language(config_data: Dict[str, Any]) -> Optional[str]:
    frontend = config_data.get("frontend") or {}
    language = frontend.get("phoneme_language") or frontend.get("phonemeLanguage")
    return language


def _load_voice() -> None:
    global _VOICE, _VOICE_SAMPLE_RATE, _VOICE_OPTIONS, _VOICE_LOOKUP
    if not _MODEL_PATH or not os.path.exists(_MODEL_PATH):
        raise RuntimeError("TTS_MODEL_PATH is not set or the file does not exist")
    if not _MODEL_CONFIG_PATH or not os.path.exists(_MODEL_CONFIG_PATH):
        raise RuntimeError("TTS_MODEL_CONFIG_PATH is not set or the file does not exist")

    with open(_MODEL_PATH, "rb") as model_file:
        model_bytes = model_file.read()
    with open(_MODEL_CONFIG_PATH, "r", encoding="utf-8") as config_file:
        config_text = config_file.read()
    config_data = json.loads(config_text)

    _VOICE = PiperVoice.load(io.BytesIO(model_bytes), io.StringIO(config_text))
    sample_rate = (
        config_data.get("sample_rate")
        or config_data.get("sampleRate")
        or getattr(_VOICE, "sample_rate", None)
    )
    if not sample_rate:
        raise RuntimeError("Unable to determine Piper sample rate from config")
    _VOICE_SAMPLE_RATE = int(sample_rate)

    language = _read_voice_language(config_data)
    speaker_map = config_data.get("speaker_id_map") or config_data.get("speakerIdMap") or {}

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

    if _DEFAULT_VOICE:
        if _DEFAULT_VOICE.lower() not in _VOICE_LOOKUP:
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


def _resolve_voice(preferred: Optional[str]) -> VoiceOption:
    if not _VOICE_OPTIONS:
        raise HTTPException(status_code=503, detail="voice catalog unavailable")
    candidate = (preferred or _DEFAULT_VOICE or "").strip()
    if not candidate:
        return _VOICE_OPTIONS[0]
    option = _VOICE_LOOKUP.get(candidate.lower())
    if option is None:
        raise HTTPException(status_code=400, detail=f"voice {candidate!r} not available")
    return option


def _strip_ssml(text: str) -> str:
    return _SSML_TAG_RE.sub("", text)


def _synthesize_audio(
    text: str,
    *,
    is_ssml: bool,
    option: VoiceOption,
    length_scale: float,
    noise_scale: float,
    noise_w: float,
) -> Tuple[bytes, int]:
    if _VOICE is None:
        raise RuntimeError("Piper voice not initialized")
    buffer = io.BytesIO()
    _VOICE.synthesize(
        text,
        buffer,
        speaker_id=option.speaker_id,
        length_scale=length_scale,
        noise_scale=noise_scale,
        noise_w=noise_w,
        ssml=is_ssml,
    )
    audio_bytes = buffer.getvalue()
    if not audio_bytes:
        raise RuntimeError("Piper returned an empty audio buffer")
    return audio_bytes, getattr(_VOICE, "sample_rate", _VOICE_SAMPLE_RATE)


@app.on_event("startup")
async def _startup() -> None:
    await asyncio.to_thread(_load_voice)
    logger.info(
        "tts.startup_complete",
        max_concurrency=_MAX_CONCURRENCY,
        rate_limit=_RATE_LIMIT_PER_MINUTE,
        auth_enabled=bool(_AUTH_TOKEN),
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    status = "ok" if _VOICE is not None else "degraded"
    return HealthResponse(
        status=status,
        sample_rate=_VOICE_SAMPLE_RATE,
        max_concurrency=_MAX_CONCURRENCY,
    )


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/voices", response_model=VoiceListResponse)
async def list_voices(_: None = Depends(_require_auth)) -> VoiceListResponse:
    if not _VOICE_OPTIONS:
        raise HTTPException(status_code=503, detail="voice catalog unavailable")
    voices = [option.as_payload() for option in _VOICE_OPTIONS]
    return VoiceListResponse(sample_rate=_VOICE_SAMPLE_RATE, voices=voices)


@app.post("/synthesize")
async def synthesize(
    payload: SynthesisRequest,
    _: None = Depends(_require_auth),
    __: None = Depends(_enforce_rate_limit),
):
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
        except Exception as exc:  # noqa: BLE001
            logger.exception("tts.synthesize_failed", error=str(exc))
            _SYNTHESIS_COUNTER.labels(status="error").inc()
            raise HTTPException(status_code=500, detail="unable to synthesize audio") from exc

    size_bytes = len(audio_bytes)
    duration = time.perf_counter() - start_time
    _SYNTHESIS_DURATION.observe(duration)
    _SYNTHESIS_SIZE.observe(size_bytes)

    audio_id = uuid.uuid4().hex
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
    return StreamingResponse(iter([audio_bytes]), media_type="audio/wav", headers=headers)


__all__ = ["app"]
