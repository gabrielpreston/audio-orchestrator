# FLAN-T5 LLM Service
import os
import time
from enum import Enum
from typing import Any

import torch
from fastapi import HTTPException
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from services.common.audio_metrics import create_http_metrics, create_llm_metrics
from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints
from services.common.app_factory import create_service_app
from services.common.structured_logging import configure_logging, get_logger
from services.common.tracing import get_observability_manager

# Configure logging
configure_logging("info", json_logs=True, service_name="flan")
logger = get_logger(__name__, service_name="flan")


class ModelSize(Enum):
    BASE = "google/flan-t5-base"  # 1GB RAM
    LARGE = "google/flan-t5-large"  # 8GB RAM
    XL = "google/flan-t5-xl"  # 16GB RAM


# Configurable model selection
model_size_env = os.getenv("FLAN_T5_MODEL_SIZE", "LARGE")
# Handle both enum names and full model names
if model_size_env.startswith("google/flan-t5-"):
    MODEL_SIZE = ModelSize(model_size_env)
else:
    # Map enum names to enum values
    enum_mapping = {
        "BASE": ModelSize.BASE,
        "LARGE": ModelSize.LARGE,
        "XL": ModelSize.XL,
    }
    MODEL_SIZE = enum_mapping.get(model_size_env, ModelSize.LARGE)
MODEL_NAME = MODEL_SIZE.value

# Cache configuration
CACHE_DIR = os.getenv("TRANSFORMERS_CACHE", "/app/models")

# Global model and tokenizer
model = None
tokenizer = None

# Health manager and observability
_health_manager = HealthManager("flan")
_observability_manager = None
_llm_metrics = {}
_http_metrics = {}


async def _startup() -> None:
    """Load the FLAN-T5 model and tokenizer on startup."""
    global model, tokenizer, _observability_manager, _llm_metrics, _http_metrics

    try:
        # Get observability manager (factory already setup observability)
        _observability_manager = get_observability_manager("flan")

        # Create service-specific metrics
        _llm_metrics = create_llm_metrics(_observability_manager)
        _http_metrics = create_http_metrics(_observability_manager)

        # Set observability manager in health manager
        _health_manager.set_observability_manager(_observability_manager)

        logger.info(
            "Loading FLAN-T5 model", extra={"model": MODEL_NAME, "cache_dir": CACHE_DIR}
        )

        # Try to load from cache first
        model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL_NAME,
            cache_dir=CACHE_DIR,
            local_files_only=True,  # Only use local files
        )
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME, cache_dir=CACHE_DIR, local_files_only=True
        )
        logger.info("FLAN-T5 model loaded successfully from cache")

        # Mark startup complete
        _health_manager.mark_startup_complete()

    except Exception as e:
        logger.error(f"Failed to load FLAN-T5 model from cache: {e}")
        # Fallback to downloading if cache miss
        logger.info("Attempting to download model...")
        model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        logger.info("FLAN-T5 model downloaded and loaded successfully")

        # Mark startup complete even after fallback
        _health_manager.mark_startup_complete()


# Create app using factory pattern
app = create_service_app(
    "flan",
    "1.0.0",
    title="FLAN-T5 LLM Service",
    startup_callback=_startup,
)


def format_instruction_prompt(messages: list[dict[str, str]]) -> str:
    """Format messages into proper FLAN-T5 instruction prompt."""
    if not messages:
        return ""

    # Build conversation context
    conversation = []
    for msg in messages:
        if msg["role"] == "user":
            conversation.append(f"Human: {msg['content']}")
        elif msg["role"] == "assistant":
            conversation.append(f"Assistant: {msg['content']}")

    # Use proper FLAN-T5 format with context
    if len(conversation) > 1:
        context = "\n".join(conversation[:-1])
        last_message = conversation[-1]
        return f"{context}\n{last_message}\nAssistant:"
    else:
        # Single message format
        last_message = conversation[-1] if conversation else ""
        return f"{last_message}\nAssistant:"


@app.post("/v1/chat/completions")  # type: ignore[misc]
async def chat_completions(request: dict[str, Any]) -> dict[str, Any]:
    """OpenAI-compatible chat completions endpoint."""
    start_time = time.time()

    try:
        if model is None or tokenizer is None:
            raise HTTPException(status_code=503, detail="Model not loaded")

        messages = request.get("messages", [])
        if not messages:
            raise HTTPException(status_code=400, detail="No messages provided")

        # Format prompt for FLAN-T5
        prompt = format_instruction_prompt(messages)
        if not prompt:
            raise HTTPException(status_code=400, detail="No valid user message found")

        # Generate response
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_length=256,  # Reduced for faster responses
                num_beams=4,
                early_stopping=False,  # Allow full generation
                do_sample=True,  # Enable sampling for more natural responses
                temperature=0.7,  # Add creativity
                top_k=50,  # Limit vocabulary
                top_p=0.9,  # Nucleus sampling
                repetition_penalty=1.1,  # Reduce repetition
            )

        response = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Clean up response more reliably
        if "Assistant:" in response:
            response = response.split("Assistant:")[-1].strip()
        elif "Human:" in response:
            response = response.split("Human:")[0].strip()

        # Remove any remaining prompt artifacts
        response = response.replace("Answer this question:", "").strip()

        # Ensure we have a meaningful response
        if not response or response == prompt:
            response = (
                "I'm sorry, I couldn't generate a proper response to that question."
            )

        # Record metrics
        processing_time = time.time() - start_time
        prompt_tokens = len(inputs["input_ids"][0])
        completion_tokens = len(outputs[0])

        if _llm_metrics:
            if "llm_requests" in _llm_metrics:
                _llm_metrics["llm_requests"].add(
                    1, attributes={"model": MODEL_NAME, "status": "success"}
                )
            if "llm_latency" in _llm_metrics:
                _llm_metrics["llm_latency"].record(
                    processing_time, attributes={"model": MODEL_NAME}
                )
            if "llm_tokens" in _llm_metrics:
                _llm_metrics["llm_tokens"].add(
                    prompt_tokens, attributes={"model": MODEL_NAME, "type": "prompt"}
                )
                _llm_metrics["llm_tokens"].add(
                    completion_tokens,
                    attributes={"model": MODEL_NAME, "type": "completion"},
                )

        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": response},
                    "finish_reason": "stop",
                }
            ],
            "model": MODEL_NAME,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    except Exception as e:
        # Record error metrics
        processing_time = time.time() - start_time
        if _llm_metrics and "llm_requests" in _llm_metrics:
            _llm_metrics["llm_requests"].add(
                1, attributes={"model": MODEL_NAME, "status": "error"}
            )
        if _llm_metrics and "llm_latency" in _llm_metrics:
            _llm_metrics["llm_latency"].record(
                processing_time, attributes={"model": MODEL_NAME, "status": "error"}
            )

        logger.error(f"Error in chat completions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="flan",
    health_manager=_health_manager,
    custom_components={
        "model_loaded": lambda: model is not None and tokenizer is not None,
        "model_name": lambda: MODEL_NAME,
        "model_size": lambda: MODEL_SIZE.name,
    },
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())


@app.get("/models")  # type: ignore[misc]
async def list_models() -> dict[str, list[dict[str, Any]]]:
    """List available models."""
    return {
        "data": [
            {
                "id": MODEL_NAME,
                "object": "model",
                "created": 1640995200,  # Placeholder timestamp
                "owned_by": "google",
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8100)
