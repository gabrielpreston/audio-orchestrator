# FLAN-T5 LLM Service
import logging
import os
from enum import Enum
from typing import Any

import torch
from fastapi import FastAPI, HTTPException
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FLAN-T5 LLM Service", version="1.0.0")


class ModelSize(Enum):
    BASE = "google/flan-t5-base"  # 1GB RAM
    LARGE = "google/flan-t5-large"  # 8GB RAM
    XL = "google/flan-t5-xl"  # 16GB RAM


# Configurable model selection
MODEL_SIZE = ModelSize(os.getenv("FLAN_T5_MODEL_SIZE", "LARGE"))
MODEL_NAME = MODEL_SIZE.value

# Cache configuration
CACHE_DIR = os.getenv("TRANSFORMERS_CACHE", "/app/models")

# Global model and tokenizer
model = None
tokenizer = None


@app.on_event("startup")  # type: ignore[misc]
async def load_model() -> None:
    """Load the FLAN-T5 model and tokenizer on startup."""
    global model, tokenizer
    try:
        logger.info(f"Loading FLAN-T5 model: {MODEL_NAME} from cache: {CACHE_DIR}")

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
    except Exception as e:
        logger.error(f"Failed to load FLAN-T5 model from cache: {e}")
        # Fallback to downloading if cache miss
        logger.info("Attempting to download model...")
        model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        logger.info("FLAN-T5 model downloaded and loaded successfully")


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

        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": response},
                    "finish_reason": "stop",
                }
            ],
            "model": MODEL_NAME,
            "usage": {
                "prompt_tokens": len(inputs["input_ids"][0]),
                "completion_tokens": len(outputs[0]),
                "total_tokens": len(inputs["input_ids"][0]) + len(outputs[0]),
            },
        }

    except Exception as e:
        logger.error(f"Error in chat completions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health/ready")  # type: ignore[misc]
async def health_ready() -> dict[str, Any]:
    """Health check endpoint."""
    try:
        if model is None or tokenizer is None:
            return {"status": "not_ready", "error": "Model not loaded"}

        # Simple health check without model inference to avoid timeout
        return {"status": "ready", "model": MODEL_NAME, "model_size": MODEL_SIZE.name}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}


@app.get("/health/live")  # type: ignore[misc]
async def health_live() -> dict[str, str]:
    """Liveness check endpoint."""
    return {"status": "alive"}


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
