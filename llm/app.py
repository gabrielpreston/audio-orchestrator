from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
import time
import logging
from pythonjsonlogger import jsonlogger
import sys
from pydantic import BaseModel
import os
import uvicorn
import subprocess
import shutil
from typing import Optional

app = FastAPI(title="Local Orchestrator / OpenAI-compatible LLM")

# --- JSON logging setup ---
def _setup_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    try:
        lvl = getattr(logging, level)
    except Exception:
        lvl = logging.INFO

    handler = logging.StreamHandler(stream=sys.stdout)
    # use python-json-logger for structured JSON logs
    fmt = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.handlers = []
    root.addHandler(handler)
    root.setLevel(lvl)


_setup_logging()
logger = logging.getLogger("llm.app")

# /orchestrate has been removed: this service provides OpenAI-compatible
# endpoints under /v1/chat/completions. Clients should POST chat requests
# directly to that endpoint and extract assistant text from
# choices[0].message.content in the response.

# Minimal OpenAI-compatible chat completions endpoint
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    max_tokens: int | None = None

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest, authorization: str | None = Header(None)):
    # Top-level timing for request (includes prompt build + local model invocation)
    req_start = time.time()

    # Optional auth enforcement
    expected = os.getenv("ORCH_AUTH_TOKEN")
    if expected:
        if not authorization or not authorization.startswith("Bearer ") or authorization.split(" ", 1)[1] != expected:
            logger.warning("unauthorized request", extra={"extra": {"event": "auth", "status": "unauthorized"}})
            raise HTTPException(status_code=401, detail="unauthorized")
    # Very small local "model": try to invoke a local llama CLI if available,
    # otherwise fall back to a simple echo.
    if not req.messages:
        logger.warning("bad request: messages required", extra={"extra": {"event": "bad_request"}})
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
                            logger.debug("llama cli failed", extra={"extra": {"args": args, "rc": proc.returncode, "stderr": proc.stderr}})
                            pass
                    except Exception:
                        logger.exception("llama invocation error", extra={"extra": {"args": args}})
                        pass
        except Exception:
            logger.exception("LLAMA_BIN check failed")
            pass

    if content is None:
        # fallback: echo the last message prefixed
        last = req.messages[-1]
        content = f"(local-model) {last.content}"
    # model selection/metadata
    model_name = req.model or "local-orch"
    logger.info("completion generated", extra={"extra": {"model": model_name, "id": "local-1", "prompt_bytes": prompt_bytes}})

    req_end = time.time()
    total_ms = int((req_end - req_start) * 1000)
    # for local/non-llama runs we don't have separate inference timing; approximate with total_ms
    processing_ms = total_ms

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
