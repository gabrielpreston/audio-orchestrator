from __future__ import annotations

import asyncio
import io
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from piper import PiperVoice

# Prometheus metrics removed
from pydantic import BaseModel, Field, model_validator

from services.common.audio_pipeline import create_audio_pipeline
from services.common.debug import get_debug_manager
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

# Debug manager for saving debug files
_debug_manager = get_debug_manager("tts")

# Canonical audio pipeline for TTS processing
_canonical_pipeline = create_audio_pipeline("tts")

# Prometheus metrics removed

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
    correlation_id: Optional[str] = None

    @model_validator(mode="before")
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
    with open(_MODEL_CONFIG_PATH, "r", encoding="utf-8") as config_file:
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
) -> Tuple[bytes, int]:
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


# Metrics endpoint removed


@app.get("/voices", response_model=VoiceListResponse)
async def list_voices(_: None = Depends(_require_auth)) -> VoiceListResponse:
    if not _VOICE_OPTIONS:
        # Return a default voice option when no model is loaded
        default_voice = VoiceOption(key="default", speaker_id=None, language="en")
        voices = [default_voice.as_payload()]
    else:
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
            # Metrics removed
            raise HTTPException(status_code=500, detail="unable to synthesize audio") from exc

    size_bytes = len(audio_bytes)
    duration = time.perf_counter() - start_time
    # Metrics removed

    from services.common.correlation import generate_tts_correlation_id

    audio_id = payload.correlation_id or generate_tts_correlation_id()
    headers = {
        "X-Audio-Id": audio_id,
        "X-Audio-Voice": option.key,
        "X-Audio-Sample-Rate": str(sample_rate),
        "X-Audio-Size": str(size_bytes),
    }
    # Metrics removed
    logger.info(
        "tts.synthesize_stream_success",
        audio_id=audio_id,
        voice=option.key,
        ssml=is_ssml,
        text_length=text_length,
        size_bytes=size_bytes,
        duration_ms=int(duration * 1000),
    )

    # Save debug data for TTS synthesis
    _save_debug_synthesis(
        audio_id=audio_id,
        text_source=text_source,
        is_ssml=is_ssml,
        text_length=text_length,
        option=option,
        length_scale=length_scale,
        noise_scale=noise_scale,
        noise_w=noise_w,
        audio_bytes=audio_bytes,
        sample_rate=sample_rate,
        size_bytes=size_bytes,
        duration=duration,
    )

    return StreamingResponse(iter([audio_bytes]), media_type="audio/wav", headers=headers)


@app.post("/synthesize-canonical")
async def synthesize_canonical(
    payload: SynthesisRequest,
    _: None = Depends(_require_auth),
    __: None = Depends(_enforce_rate_limit),
):
    """
    Synthesize TTS audio using canonical audio pipeline.

    This endpoint processes TTS audio through the canonical audio pipeline
    with proper loudness normalization and 48kHz mono framing.
    """
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
            # First synthesize using Piper
            audio_bytes, sample_rate = await asyncio.to_thread(
                _synthesize_audio,
                text_source,
                is_ssml=is_ssml,
                option=option,
                length_scale=length_scale,
                noise_scale=noise_scale,
                noise_w=noise_w,
            )

            # Process through canonical audio pipeline
            canonical_frames = _canonical_pipeline.process_tts_audio(
                audio_bytes=audio_bytes, input_format="wav"
            )

            if not canonical_frames:
                logger.warning("tts.canonical_processing_failed", audio_id=payload.correlation_id)
                # Fallback to original audio
                canonical_audio_bytes = audio_bytes
            else:
                # Convert back to WAV format for response
                canonical_audio_bytes = _canonical_pipeline.frames_to_discord_playback(
                    canonical_frames
                )

                # Convert to WAV format
                import io
                import wave

                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, "wb") as wav_file:
                    wav_file.setnchannels(1)  # mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(48000)  # 48kHz
                    wav_file.writeframes(canonical_audio_bytes)
                canonical_audio_bytes = wav_buffer.getvalue()

        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("tts.canonical_synthesize_failed", error=str(exc))
            # Metrics removed
            raise HTTPException(status_code=500, detail="unable to synthesize audio") from exc

    size_bytes = len(canonical_audio_bytes)
    duration = time.perf_counter() - start_time
    # Metrics removed

    from services.common.correlation import generate_tts_correlation_id

    audio_id = payload.correlation_id or generate_tts_correlation_id()
    headers = {
        "X-Audio-Id": audio_id,
        "X-Audio-Voice": option.key,
        "X-Audio-Sample-Rate": "48000",  # Canonical sample rate
        "X-Audio-Size": str(size_bytes),
        "X-Audio-Format": "canonical",
    }
    # Metrics removed
    logger.info(
        "tts.canonical_synthesize_success",
        audio_id=audio_id,
        voice=option.key,
        ssml=is_ssml,
        text_length=text_length,
        size_bytes=size_bytes,
        duration_ms=int(duration * 1000),
        canonical_frames=len(canonical_frames) if canonical_frames else 0,
    )

    # Save debug data for canonical TTS synthesis
    _save_debug_canonical_synthesis(
        audio_id=audio_id,
        text_source=text_source,
        is_ssml=is_ssml,
        text_length=text_length,
        option=option,
        length_scale=length_scale,
        noise_scale=noise_scale,
        noise_w=noise_w,
        audio_bytes=canonical_audio_bytes,
        canonical_frames=canonical_frames,
        size_bytes=size_bytes,
        duration=duration,
    )

    return StreamingResponse(iter([canonical_audio_bytes]), media_type="audio/wav", headers=headers)


def _save_debug_synthesis(
    audio_id: str,
    text_source: str,
    is_ssml: bool,
    text_length: int,
    option: "VoiceOption",
    length_scale: float,
    noise_scale: float,
    noise_w: float,
    audio_bytes: bytes,
    sample_rate: int,
    size_bytes: int,
    duration: float,
) -> None:
    """Save debug data for TTS synthesis requests."""
    try:
        # Use audio_id as correlation_id for TTS debug files
        correlation_id = audio_id

        # Save input text/SSML
        _debug_manager.save_text_file(
            correlation_id=correlation_id,
            content=f"TTS Input ({'SSML' if is_ssml else 'Text'}):\n{text_source}",
            filename_prefix="tts_input",
        )

        # Save generated audio
        _debug_manager.save_audio_file(
            correlation_id=correlation_id,
            audio_data=audio_bytes,
            filename_prefix="tts_output",
        )

        # Save synthesis parameters
        _debug_manager.save_json_file(
            correlation_id=correlation_id,
            data={
                "audio_id": audio_id,
                "text_source": text_source,
                "is_ssml": is_ssml,
                "text_length": text_length,
                "voice_key": option.key,
                "voice_speaker_id": option.speaker_id,
                "voice_language": option.language,
                "length_scale": length_scale,
                "noise_scale": noise_scale,
                "noise_w": noise_w,
                "sample_rate": sample_rate,
                "size_bytes": size_bytes,
                "duration_seconds": duration,
                "model_path": _MODEL_PATH,
                "model_config_path": _MODEL_CONFIG_PATH,
            },
            filename_prefix="tts_parameters",
        )

        # Save manifest
        files = {}
        audio_file = _debug_manager.save_audio_file(
            correlation_id=correlation_id,
            audio_data=audio_bytes,
            filename_prefix="tts_output",
        )
        if audio_file:
            files["tts_output"] = str(audio_file)

        _debug_manager.save_manifest(
            correlation_id=correlation_id,
            metadata={
                "service": "tts",
                "event": "synthesis_complete",
                "audio_id": audio_id,
                "voice": option.key,
                "is_ssml": is_ssml,
            },
            files=files,
            stats={
                "text_length": text_length,
                "size_bytes": size_bytes,
                "duration_seconds": duration,
                "sample_rate": sample_rate,
            },
        )

    except Exception as exc:
        logger.error(
            "tts.debug_synthesis_save_failed",
            audio_id=audio_id,
            error=str(exc),
        )


def _save_debug_canonical_synthesis(
    audio_id: str,
    text_source: str,
    is_ssml: bool,
    text_length: int,
    option: "VoiceOption",
    length_scale: float,
    noise_scale: float,
    noise_w: float,
    audio_bytes: bytes,
    canonical_frames,
    size_bytes: int,
    duration: float,
) -> None:
    """Save debug data for canonical TTS synthesis requests."""
    try:
        # Use audio_id as correlation_id for TTS debug files
        correlation_id = audio_id

        # Save input text/SSML
        _debug_manager.save_text_file(
            correlation_id=correlation_id,
            content=f"Canonical TTS Input ({'SSML' if is_ssml else 'Text'}):\n{text_source}",
            filename_prefix="tts_canonical_input",
        )

        # Save generated audio
        _debug_manager.save_audio_file(
            correlation_id=correlation_id,
            audio_data=audio_bytes,
            filename_prefix="tts_canonical_output",
        )

        # Save canonical frames info
        _debug_manager.save_json_file(
            correlation_id=correlation_id,
            data={
                "audio_id": audio_id,
                "text_source": text_source,
                "is_ssml": is_ssml,
                "text_length": text_length,
                "voice_key": option.key,
                "voice_speaker_id": option.speaker_id,
                "voice_language": option.language,
                "length_scale": length_scale,
                "noise_scale": noise_scale,
                "noise_w": noise_w,
                "canonical_frames": len(canonical_frames) if canonical_frames else 0,
                "frame_duration_ms": 20.0,
                "sample_rate": 48000,
                "channels": 1,
                "size_bytes": size_bytes,
                "duration_seconds": duration,
                "model_path": _MODEL_PATH,
                "model_config_path": _MODEL_CONFIG_PATH,
            },
            filename_prefix="tts_canonical_parameters",
        )

        # Save manifest
        files = {}
        audio_file = _debug_manager.save_audio_file(
            correlation_id=correlation_id,
            audio_data=audio_bytes,
            filename_prefix="tts_canonical_output",
        )
        if audio_file:
            files["tts_canonical_output"] = str(audio_file)

        _debug_manager.save_manifest(
            correlation_id=correlation_id,
            metadata={
                "service": "tts",
                "event": "canonical_synthesis_complete",
                "audio_id": audio_id,
                "voice": option.key,
                "is_ssml": is_ssml,
                "canonical_format": True,
            },
            files=files,
            stats={
                "text_length": text_length,
                "size_bytes": size_bytes,
                "duration_seconds": duration,
                "canonical_frames": len(canonical_frames) if canonical_frames else 0,
                "sample_rate": 48000,
            },
        )

    except Exception as exc:
        logger.error(
            "tts.debug_canonical_synthesis_save_failed",
            audio_id=audio_id,
            error=str(exc),
        )


__all__ = ["app"]
