from __future__ import annotations

import base64
import os
import time
import uuid
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from llama_cpp import Llama
from pydantic import BaseModel

from services.common.health import HealthManager
from services.common.logging import configure_logging, get_logger

app = FastAPI(title="Local LLM Service")

configure_logging(
    os.getenv("LOG_LEVEL", "INFO"),
    json_logs=os.getenv("LOG_JSON", "true").lower() in {"1", "true", "yes", "on"},
    service_name="llm",
)
logger = get_logger(__name__, service_name="llm")

_LLAMA: Llama | None = None
_LLAMA_INFO: dict[str, Any] = {}
_TTS_CLIENT: httpx.AsyncClient | None = None
_health_manager = HealthManager("llm")

_TTS_BASE_URL = os.getenv("TTS_BASE_URL")
_TTS_VOICE = os.getenv("TTS_VOICE")
_TTS_AUTH_TOKEN = os.getenv("TTS_AUTH_TOKEN")


def _env_bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


def _tts_timeout() -> float:
    try:
        return float(os.getenv("TTS_TIMEOUT", "30"))
    except ValueError:
        return 30.0


def _load_llama() -> Llama | None:
    global _LLAMA, _LLAMA_INFO
    if _LLAMA is not None:
        return _LLAMA

    model_path = os.getenv("LLAMA_MODEL_PATH", "/app/models/llama2-7b.gguf")
    if not os.path.exists(model_path):
        logger.critical("llm.model_missing", model_path=model_path)
        raise RuntimeError(f"LLM model not found at {model_path}")

    try:
        ctx = int(os.getenv("LLAMA_CTX", "2048"))
    except ValueError:
        ctx = 2048
    try:
        threads = int(os.getenv("LLAMA_THREADS", str(max(os.cpu_count() or 1, 1))))
    except ValueError:
        threads = max(os.cpu_count() or 1, 1)

    try:
        _LLAMA = Llama(
            model_path=model_path,
            n_ctx=ctx,
            n_threads=threads,
            verbose=False,  # Reduce verbose output
        )
        _LLAMA_INFO = {"model_path": model_path, "ctx": ctx, "threads": threads}
        logger.info("llm.model_loaded", model_path=model_path, ctx=ctx, threads=threads)
    except Exception as exc:
        logger.critical("llm.model_load_failed", model_path=model_path, error=str(exc))
        _LLAMA = None
        raise RuntimeError(f"Failed to load LLM model from {model_path}") from exc
    return _LLAMA


async def _ensure_tts_client() -> httpx.AsyncClient | None:
    global _TTS_CLIENT
    if not _TTS_BASE_URL:
        return None
    if _TTS_CLIENT is None:
        timeout_value = _tts_timeout()
        timeout = httpx.Timeout(
            connect=5.0,
            read=timeout_value,
            write=timeout_value,
            pool=timeout_value,
        )
        _TTS_CLIENT = httpx.AsyncClient(base_url=_TTS_BASE_URL, timeout=timeout)
    return _TTS_CLIENT


async def _synthesize_tts(text: str) -> dict[str, Any] | None:
    client = await _ensure_tts_client()
    if not client:
        return None
    payload: dict[str, Any] = {"text": text}
    if _TTS_VOICE:
        payload["voice"] = _TTS_VOICE
    headers: dict[str, str] = {}
    if _TTS_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {_TTS_AUTH_TOKEN}"
    try:
        async with client.stream(
            "POST",
            "/synthesize",
            json=payload,
            headers=headers,
        ) as response:
            response.raise_for_status()
            audio_bytes = await response.aread()
            headers = response.headers
    except Exception as exc:
        logger.warning("llm.tts_failed", error=str(exc))
        return None
    if not audio_bytes:
        logger.warning("llm.tts_empty_audio")
        return None
    audio_id = headers.get("X-Audio-Id") or uuid.uuid4().hex
    voice = headers.get("X-Audio-Voice")
    sample_rate_header = headers.get("X-Audio-Sample-Rate")
    try:
        sample_rate = int(sample_rate_header) if sample_rate_header else 0
    except ValueError:
        sample_rate = 0
    size_bytes = len(audio_bytes)
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    content_type = headers.get("content-type", "audio/wav")
    return {
        "audio_id": audio_id,
        "voice": voice,
        "sample_rate": sample_rate,
        "size_bytes": size_bytes,
        "content_type": content_type,
        "base64": audio_b64,
        "text_length": len(text),
        "url": None,
    }


@app.on_event("startup")  # type: ignore[misc]
async def _startup_event() -> None:
    """Initialize LLM model on startup."""
    try:
        llama = _load_llama()
        if llama:
            logger.info("llm.initialized")
        else:
            logger.warning("llm.model_unavailable")

    except Exception as exc:
        logger.error("llm.startup_failed", error=str(exc))
        # Continue without model for compatibility


@app.on_event("shutdown")  # type: ignore[misc]
async def _shutdown_event() -> None:
    """Shutdown LLM service."""
    global _TTS_CLIENT

    if _TTS_CLIENT is not None:
        await _TTS_CLIENT.aclose()
        _TTS_CLIENT = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    max_tokens: int | None = None


@app.post("/v1/chat/completions")  # type: ignore[misc]
async def chat_completions(
    req: ChatRequest,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    req_start = time.time()

    expected = os.getenv("LLM_AUTH_TOKEN")
    if expected and (
        not authorization
        or not authorization.startswith("Bearer ")
        or authorization.split(" ", 1)[1] != expected
    ):
        logger.warning(
            "llm.unauthorized_request",
            has_header=authorization is not None,
        )
        raise HTTPException(status_code=401, detail="unauthorized")

    if not req.messages:
        logger.warning("llm.bad_request", reason="messages_missing")
        raise HTTPException(status_code=400, detail="messages required")

    prompt_bytes = len(
        "\n".join(message.content for message in req.messages).encode("utf-8")
    )
    logger.debug(
        "llm.request_received",
        model=req.model,
        messages=len(req.messages),
        prompt_bytes=prompt_bytes,
    )

    llama = _load_llama()
    content: str | None = None
    usage: dict[str, Any] = {}
    used_model = req.model or _LLAMA_INFO.get("model_path", "local-llama")
    processing_ms: int | None = None
    audio: dict[str, Any] | None = None

    if llama is not None:
        try:
            infer_start = time.time()
            completion = llama.create_chat_completion(
                messages=[{"role": m.role, "content": m.content} for m in req.messages],
                max_tokens=req.max_tokens or 256,
            )
            infer_end = time.time()
            processing_ms = int((infer_end - infer_start) * 1000)
            choices = completion.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content") or ""
            usage = completion.get("usage", {})
            used_model = completion.get("model", used_model)
        except Exception as exc:
            logger.exception("llm.generation_failed", error=str(exc))

    if content is None:
        fallback = req.messages[-1].content if req.messages else ""
        content = f"(local-model) {fallback}"

    if content and _TTS_BASE_URL:
        audio = await _synthesize_tts(content)
        if audio:
            logger.info(
                "llm.tts_ready",
                audio_id=audio.get("audio_id"),
                size_bytes=audio.get("size_bytes"),
            )
        else:
            logger.warning("llm.tts_unavailable")

    total_ms = int((time.time() - req_start) * 1000)
    if processing_ms is None:
        processing_ms = total_ms

    logger.info(
        "llm.response_ready",
        model=used_model,
        processing_ms=processing_ms,
        total_ms=total_ms,
        prompt_bytes=prompt_bytes,
        text_length=len(content or ""),
    )
    logger.debug("llm.response_text", text=content)

    usage_payload = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }

    response = {
        "id": "local-1",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": used_model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": usage_payload,
        "processing_ms": processing_ms,
        "total_ms": total_ms,
        "prompt_bytes": prompt_bytes,
    }

    if audio:
        response["audio"] = audio

    headers = {
        "X-Processing-Time-ms": str(processing_ms),
        "X-Total-Time-ms": str(total_ms),
        "X-Prompt-Bytes": str(prompt_bytes),
    }
    if audio and audio.get("audio_id"):
        headers["X-Audio-Id"] = str(audio["audio_id"])
    if audio and audio.get("sample_rate"):
        headers["X-Audio-Sample-Rate"] = str(audio["sample_rate"])
    if audio and audio.get("size_bytes"):
        headers["X-Audio-Size"] = str(audio["size_bytes"])
    if audio and audio.get("content_type"):
        headers["X-Audio-Content-Type"] = str(audio["content_type"])
    return JSONResponse(response, headers=headers)  # type: ignore[no-any-return]


@app.get("/health/live")  # type: ignore[misc]
async def health_live() -> dict[str, str]:
    """Liveness check - is process running."""
    return {"status": "alive", "service": "llm"}


@app.get("/health/ready")  # type: ignore[misc]
async def health_ready() -> dict[str, Any]:
    """Readiness check - can serve requests."""
    if _LLAMA is None:
        raise HTTPException(status_code=503, detail="LLM model not loaded")

    health_status = await _health_manager.get_health_status()
    return {
        "status": "ready",
        "service": "llm",
        "llm_loaded": _LLAMA is not None,
        "tts_available": _TTS_BASE_URL is not None,
        "health_details": health_status.details,
    }


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
