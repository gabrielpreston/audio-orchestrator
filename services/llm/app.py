from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
import time
from pydantic import BaseModel
import os
import uvicorn
import subprocess
import shutil
from typing import Optional

from services.common.logging import configure_logging, get_logger

app = FastAPI(title="Local Orchestrator / OpenAI-compatible LLM")

# Local OpenAI-compatible endpoint: /v1/chat/completions

# Minimal OpenAI-compatible chat completions endpoint
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

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest, authorization: str | None = Header(None)):
    # Top-level timing for request (includes prompt build + local model invocation)
    req_start = time.time()

    # Optional auth enforcement
    expected = os.getenv("ORCH_AUTH_TOKEN")
    if expected:
        if not authorization or not authorization.startswith("Bearer ") or authorization.split(" ", 1)[1] != expected:
            logger.warning(
                "llm.unauthorized_request",
                extra={"has_header": authorization is not None},
            )
            raise HTTPException(status_code=401, detail="unauthorized")
    # Very small local "model": try to invoke a local llama CLI if available,
    # otherwise fall back to a simple echo.
    if not req.messages:
        logger.warning("llm.bad_request", extra={"reason": "messages_missing"})
        raise HTTPException(status_code=400, detail="messages required")

    # Build a simple prompt from messages (system -> user/assistant sequence)
    parts = []
    for m in req.messages:
        role = m.role or "user"
        parts.append(f"[{role}] {m.content}")
    prompt = "\n".join(parts)

    # Try to use LLAMA_BIN if configured and model file exists
    llm_bin = os.getenv("LLAMA_BIN")
    model_path = os.getenv("LLAMA_MODEL_PATH", "/app/models/llama2-7b.gguf")
    content: Optional[str] = None
    prompt_bytes = len(prompt.encode('utf-8')) if prompt else 0
    logger.info(
        "llm.request_received",
        extra={
            "model": req.model,
            "messages": len(req.messages),
            "prompt_bytes": prompt_bytes,
        },
    )
    if llm_bin:
        try:
            # Validate binary exists and is executable
            if shutil.which(llm_bin) or os.path.isfile(llm_bin):
                # Try common flag forms: --model/--prompt and -m/-p
                tries = [
                    [llm_bin, "--model", model_path, "--prompt", prompt, "--n_predict", str(req.max_tokens or 256)],
                    [llm_bin, "-m", model_path, "-p", prompt, "-n", str(req.max_tokens or 256)],
                ]
                for args in tries:
                    try:
                        proc = subprocess.run(args, capture_output=True, text=True, timeout=60)
                        if proc.returncode == 0 and proc.stdout:
                            # crude cleanup of output
                            out = proc.stdout.strip()
                            content = out
                            break
                        else:
                            logger.debug(
                                "llm.cli_failed",
                                extra={
                                    "args": args,
                                    "returncode": proc.returncode,
                                    "stderr": proc.stderr,
                                },
                            )
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("llm.cli_exception", extra={"args": args, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            logger.exception("llm.cli_setup_failed", extra={"error": str(exc)})

    if content is None:
        # fallback: echo the last message prefixed
        last = req.messages[-1]
        content = f"(local-model) {last.content}"
    # model selection/metadata
    model_name = req.model or "local-orch"

    req_end = time.time()
    total_ms = int((req_end - req_start) * 1000)
    # for local/non-llama runs we don't have separate inference timing; approximate with total_ms
    processing_ms = total_ms

    logger.info(
        "llm.response_ready",
        extra={
            "model": model_name,
            "processing_ms": processing_ms,
            "prompt_bytes": prompt_bytes,
            "used_cli": llm_bin is not None and content is not None,
        },
    )

    # OpenAI-compatible response shape (minimal)
    resp = {
        "id": "local-1",
        "object": "chat.completion",
        "created": 0,
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
    # attach metadata
    resp["processing_ms"] = processing_ms
    resp["total_ms"] = total_ms
    resp["prompt_bytes"] = prompt_bytes

    headers = {"X-Processing-Time-ms": str(processing_ms), "X-Total-Time-ms": str(total_ms), "X-Prompt-Bytes": str(prompt_bytes)}
    return JSONResponse(resp, headers=headers)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
