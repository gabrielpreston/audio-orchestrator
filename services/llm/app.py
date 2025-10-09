from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from llama_cpp import Llama
from pydantic import BaseModel

from services.common.logging import configure_logging, get_logger

app = FastAPI(title="Local Orchestrator / OpenAI-compatible LLM")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    max_tokens: int | None = None


def _env_bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


configure_logging(
    os.getenv("LOG_LEVEL", "INFO"),
    json_logs=_env_bool("LOG_JSON", "true"),
    service_name="llm",
)
logger = get_logger(__name__, service_name="llm")

_LLAMA: Optional[Llama] = None
_LLAMA_INFO: Dict[str, Any] = {}


def _load_llama() -> Optional[Llama]:
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
        _LLAMA = Llama(model_path=model_path, n_ctx=ctx, n_threads=threads)
        _LLAMA_INFO = {"model_path": model_path, "ctx": ctx, "threads": threads}
        logger.info("llm.model_loaded", model_path=model_path, ctx=ctx, threads=threads)
    except Exception as exc:  # noqa: BLE001
        logger.critical("llm.model_load_failed", model_path=model_path, error=str(exc))
        _LLAMA = None
        raise RuntimeError(f"Failed to load LLM model from {model_path}")
    return _LLAMA


@app.post("/v1/chat/completions")
async def chat_completions(
    req: ChatRequest,
    authorization: str | None = Header(None),
):
    req_start = time.time()

    expected = os.getenv("ORCH_AUTH_TOKEN")
    if expected:
        if (
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

    prompt_bytes = len("\n".join(message.content for message in req.messages).encode("utf-8"))
    logger.debug(
        "llm.request_received",
        model=req.model,
        messages=len(req.messages),
        prompt_bytes=prompt_bytes,
    )

    llama = _load_llama()
    content: Optional[str] = None
    usage: Dict[str, Any] = {}
    used_model = req.model or _LLAMA_INFO.get("model_path", "local-llama")
    processing_ms: Optional[int] = None

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
        except Exception as exc:  # noqa: BLE001
            logger.exception("llm.generation_failed", error=str(exc))

    if content is None:
        fallback = req.messages[-1].content if req.messages else ""
        content = f"(local-model) {fallback}"

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

    headers = {
        "X-Processing-Time-ms": str(processing_ms),
        "X-Total-Time-ms": str(total_ms),
        "X-Prompt-Bytes": str(prompt_bytes),
    }
    return JSONResponse(response, headers=headers)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
