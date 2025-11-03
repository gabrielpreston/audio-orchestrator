# FLAN-T5 LLM Service
from enum import Enum
import os
import time
from typing import Any

from fastapi import HTTPException
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from services.common.app_factory import create_service_app
from services.common.audio_metrics import (
    create_http_metrics,
    create_llm_metrics,
    create_system_metrics,
)
from services.common.config import (
    LoggingConfig,
    get_service_preset,
)
from services.common.gpu_utils import (
    get_full_device_info,
    get_pytorch_cuda_info,
    log_device_info,
)
from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints
from services.common.model_loader import BackgroundModelLoader
from services.common.model_utils import force_download_transformers
from services.common.structured_logging import configure_logging, get_logger
from services.common.tracing import get_observability_manager
from services.common.permissions import ensure_model_directory

# Load configuration using standard config classes
_config_preset = get_service_preset("flan")
_logging_config = LoggingConfig(**_config_preset["logging"])

# Configure logging using config class
configure_logging(
    _logging_config.level,
    json_logs=_logging_config.json_logs,
    service_name="flan",
)
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

# Cache configuration (migrated to HF_HOME per transformers v5 deprecation)
CACHE_DIR = os.getenv("HF_HOME", os.getenv("TRANSFORMERS_CACHE", "/app/models"))

# Global model and tokenizer (for backward compatibility)
model = None
tokenizer = None

# Model loader for background loading
_model_loader: BackgroundModelLoader | None = None

# Health manager and observability
_health_manager = HealthManager("flan")
_observability_manager = None
_llm_metrics = {}
_http_metrics = {}


def _load_from_cache() -> tuple[Any, Any] | None:
    """Try loading model and tokenizer from cache."""
    import time

    cache_start = time.time()
    logger.debug(
        "flan.cache_load_start",
        model_name=MODEL_NAME,
        cache_dir=CACHE_DIR,
        phase="cache_check",
    )

    try:
        model_start = time.time()
        logger.debug("flan.loading_model_from_cache", phase="model_cache_load")
        cached_model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL_NAME,
            cache_dir=CACHE_DIR,
            local_files_only=True,  # Only use local files
        )
        model_duration = time.time() - model_start

        tokenizer_start = time.time()
        logger.debug("flan.loading_tokenizer_from_cache", phase="tokenizer_cache_load")
        cached_tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME, cache_dir=CACHE_DIR, local_files_only=True
        )
        tokenizer_duration = time.time() - tokenizer_start
        total_duration = time.time() - cache_start

        # Move model to GPU if available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            logger.info("flan.moving_model_to_gpu", phase="gpu_migration")
            cached_model = cached_model.to(device)
            cached_model = cached_model.half()  # Use float16 on GPU

        # Apply torch.compile() if enabled
        from services.common.torch_compile import compile_model_if_enabled

        cached_model = compile_model_if_enabled(cached_model, "flan", "flan_t5", logger)

        # Get actual device information from the loaded model
        device_info = get_full_device_info(model=cached_model, intended_device=device)

        logger.info(
            "flan.model_loaded_from_cache",
            model_name=MODEL_NAME,
            cache_dir=CACHE_DIR,
            model_duration_ms=round(model_duration * 1000, 2),
            tokenizer_duration_ms=round(tokenizer_duration * 1000, 2),
            total_duration_ms=round(total_duration * 1000, 2),
            phase="cache_load_complete",
        )

        # Log device info in standardized format
        log_device_info(
            logger,
            "flan.model_loaded_from_cache",
            device_info,
            phase="cache_load_complete",
        )

        return (cached_model, cached_tokenizer)
    except (OSError, ImportError, RuntimeError) as e:
        total_duration = time.time() - cache_start
        logger.debug(
            "flan.cache_load_failed",
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=round(total_duration * 1000, 2),
            phase="cache_load_failed",
        )
        return None


def _load_with_download() -> tuple[Any, Any]:
    """Load model and tokenizer with download fallback."""
    import time

    download_start = time.time()

    # Check if force download is enabled
    force_download = False
    if _model_loader is not None:
        force_download = _model_loader.is_force_download()

    logger.info(
        "flan.download_load_start",
        model_name=MODEL_NAME,
        cache_dir=CACHE_DIR,
        force_download=force_download,
        phase="download_start",
    )

    # Log the exact parameters that will be used for loading
    model_params: dict[str, Any] = {
        "model_name": MODEL_NAME,
        "cache_dir": CACHE_DIR,
    }

    # Detect device (GPU if available, else CPU)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Get detailed CUDA info for logging using common utility
    cuda_info = get_pytorch_cuda_info()

    logger.info(
        "flan.device_detected",
        device=device,
        cuda_available=cuda_info["pytorch_cuda_available"],
        cuda_device_count=cuda_info["pytorch_cuda_device_count"],
        cuda_device_name=cuda_info["pytorch_cuda_device_name"],
        cuda_version=cuda_info.get("cuda_version"),
        phase="device_detection",
    )

    if force_download:
        model_params["force_download"] = True

    logger.debug(
        "flan.model_load_parameters",
        phase="model_load_params",
        model_parameters=model_params,
        tokenizer_parameters=model_params,
        message="Parameters for AutoModelForSeq2SeqLM and AutoTokenizer",
    )

    # Use force download helper if enabled
    if force_download:
        logger.info(
            "flan.force_download_enabled",
            model_name=MODEL_NAME,
            phase="force_download_prep",
        )
        model_start = time.time()
        downloaded_model = force_download_transformers(
            model_name=MODEL_NAME,
            cache_dir=CACHE_DIR,
            force=True,
            model_class=AutoModelForSeq2SeqLM,
        )
        model_duration = time.time() - model_start

        tokenizer_start = time.time()
        downloaded_tokenizer = force_download_transformers(
            model_name=MODEL_NAME,
            cache_dir=CACHE_DIR,
            force=True,
            model_class=AutoTokenizer,
        )
        tokenizer_duration = time.time() - tokenizer_start

        # Move model to GPU if available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            logger.info("flan.moving_model_to_gpu", phase="gpu_migration")
            downloaded_model = downloaded_model.to(device)
            downloaded_model = downloaded_model.half()  # Use float16 on GPU
    else:
        model_start = time.time()
        logger.debug("flan.downloading_model", phase="model_download")
        downloaded_model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL_NAME, cache_dir=CACHE_DIR
        )
        model_duration = time.time() - model_start

        tokenizer_start = time.time()
        logger.debug("flan.downloading_tokenizer", phase="tokenizer_download")
        downloaded_tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME, cache_dir=CACHE_DIR
        )
        tokenizer_duration = time.time() - tokenizer_start

        # Move model to GPU if available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            logger.info("flan.moving_model_to_gpu", phase="gpu_migration")
            downloaded_model = downloaded_model.to(device)
            downloaded_model = downloaded_model.half()  # Use float16 on GPU

    # Apply torch.compile() if enabled
    from services.common.torch_compile import compile_model_if_enabled

    downloaded_model = compile_model_if_enabled(
        downloaded_model, "flan", "flan_t5", logger
    )

    total_duration = time.time() - download_start

    # Get actual device information from the loaded model
    device_info = get_full_device_info(model=downloaded_model, intended_device=device)

    logger.info(
        "flan.model_downloaded_and_loaded",
        model_name=MODEL_NAME,
        cache_dir=CACHE_DIR,
        force_download=force_download,
        model_duration_ms=round(model_duration * 1000, 2),
        tokenizer_duration_ms=round(tokenizer_duration * 1000, 2),
        total_duration_ms=round(total_duration * 1000, 2),
        phase="download_complete",
    )

    # Log device info in standardized format
    log_device_info(
        logger,
        "flan.model_downloaded_and_loaded",
        device_info,
        phase="download_complete",
    )

    return (downloaded_model, downloaded_tokenizer)


async def _startup() -> None:
    """Load the FLAN-T5 model and tokenizer on startup."""
    global _model_loader, _observability_manager, _llm_metrics, _http_metrics

    try:
        # Get observability manager (factory already setup observability)
        _observability_manager = get_observability_manager("flan")

        # Create service-specific metrics
        _llm_metrics = create_llm_metrics(_observability_manager)
        _http_metrics = create_http_metrics(_observability_manager)
        _system_metrics = create_system_metrics(_observability_manager)

        # Set observability manager in health manager
        _health_manager.set_observability_manager(_observability_manager)

        # Ensure cache directory is writable
        if not ensure_model_directory(CACHE_DIR):
            logger.warning(
                "flan.cache_directory_not_writable",
                cache_dir=CACHE_DIR,
                message="Model loading may fail if cache directory is not writable",
            )

        logger.info(
            "Loading FLAN-T5 model", extra={"model": MODEL_NAME, "cache_dir": CACHE_DIR}
        )

        # Initialize model loader with cache-first + download fallback
        _model_loader = BackgroundModelLoader(
            cache_loader_func=_load_from_cache,
            download_loader_func=_load_with_download,
            logger=logger,
            loader_name="flan_t5",
        )

        # Start background loading (non-blocking)
        await _model_loader.initialize()
        logger.info("flan.model_loader_initialized", model_name=MODEL_NAME)

        # Register model loader as dependency for health checks
        # Models must be loaded AND not currently loading for service to be ready
        _health_manager.register_dependency(
            "flan_model",
            lambda: (
                _model_loader.is_loaded() and not _model_loader.is_loading()
                if _model_loader
                else False
            ),
        )

        # Mark startup complete
        _health_manager.mark_startup_complete()

        # Pre-warm models using unified pattern
        from services.common.prewarm import prewarm_if_enabled

        async def _prewarm_flan() -> None:
            """Pre-warm FLAN model by performing a generation."""
            if not _model_loader.is_loaded():
                return

            model_tokenizer_tuple = _model_loader.get_model()
            if model_tokenizer_tuple is None:
                return

            model, tokenizer = model_tokenizer_tuple
            device = "cuda" if torch.cuda.is_available() else "cpu"
            inputs = tokenizer("Hello", return_tensors="pt").to(device)
            with torch.no_grad():
                model.generate(**inputs, max_length=10, num_beams=1)

        await prewarm_if_enabled(
            _prewarm_flan,
            "flan",
            logger,
            model_loader=_model_loader,
            health_manager=_health_manager,
        )

    except (OSError, ImportError, RuntimeError) as e:
        logger.warning(
            "flan.model_loader_init_failed",
            error=str(e),
            error_type=type(e).__name__,
            note="Service will continue with graceful degradation",
        )
        # Mark startup complete even after error (graceful degradation)
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
        # Check model status before processing (non-blocking)
        if _model_loader is None:
            raise HTTPException(status_code=503, detail="Model loader not initialized")

        if _model_loader.is_loading():
            raise HTTPException(
                status_code=503,
                detail="Models are currently loading. Please try again shortly.",
            )

        if not _model_loader.is_loaded():
            status = _model_loader.get_status()
            error_msg = status.get("error", "Models not available")
            raise HTTPException(
                status_code=503, detail=f"Models not available: {error_msg}"
            )

        # Ensure models are loaded (may trigger lazy load if background failed)
        if not await _model_loader.ensure_loaded():
            status = _model_loader.get_status()
            error_msg = status.get("error", "Models not available")
            raise HTTPException(
                status_code=503, detail=f"Models not available: {error_msg}"
            )

        # Get model and tokenizer from loader (tuple return)
        model_tokenizer_tuple = _model_loader.get_model()
        if model_tokenizer_tuple is None:
            raise HTTPException(status_code=503, detail="Models not available")

        loaded_model, loaded_tokenizer = model_tokenizer_tuple

        # Update global variables for backward compatibility
        global model, tokenizer
        model = loaded_model
        tokenizer = loaded_tokenizer

        messages = request.get("messages", [])
        if not messages:
            raise HTTPException(status_code=400, detail="No messages provided")

        # Format prompt for FLAN-T5
        prompt = format_instruction_prompt(messages)
        if not prompt:
            raise HTTPException(status_code=400, detail="No valid user message found")

        # Move to device if GPU available
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # Get device info for logging using common utility
        device_info = get_full_device_info(model=model, intended_device=device)

        logger.info(
            "flan.inference_started",
            model=MODEL_NAME,
            prompt_length=len(prompt),
            phase="inference_start",
        )

        # Log device info in standardized format (without mismatch warning for inference)
        log_device_info(
            logger,
            "flan.inference_started",
            device_info,
            phase="inference_start",
            warn_on_mismatch=False,  # Don't warn on every inference
        )

        # Generate response
        inputs = tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=512
        ).to(device)

        inference_start = time.time()
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_length=512,  # Increased from 256 for better response quality
                num_beams=5,  # Increased from 4 for better quality
                early_stopping=False,  # Allow full generation
                do_sample=True,  # Enable sampling for more natural responses
                temperature=0.7,  # Add creativity
                top_k=50,  # Limit vocabulary
                top_p=0.9,  # Nucleus sampling
                repetition_penalty=1.1,  # Reduce repetition
            )
        inference_duration = time.time() - inference_start

        # Log successful inference with device confirmation
        logger.info(
            "flan.inference_completed",
            model=MODEL_NAME,
            inference_duration_ms=round(inference_duration * 1000, 2),
            phase="inference_complete",
        )

        # Log device info in standardized format
        log_device_info(
            logger,
            "flan.inference_completed",
            device_info,
            phase="inference_complete",
            warn_on_mismatch=False,
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
        raise HTTPException(status_code=500, detail=str(e)) from e


def _get_flan_device_info() -> dict[str, Any]:
    """Get current FLAN service device information for health checks."""
    # Detect intended device
    intended_device = "cuda" if torch.cuda.is_available() else "cpu"

    # Get actual device from loaded model
    loaded_model = None
    if _model_loader is not None and _model_loader.is_loaded():
        try:
            model_tokenizer_tuple = _model_loader.get_model()
            if model_tokenizer_tuple is not None:
                loaded_model, _ = model_tokenizer_tuple
        except Exception as e:
            logger.debug(
                "flan.device_info_model_load_failed",
                error=str(e),
                error_type=type(e).__name__,
                message="Failed to load model for device info, continuing",
            )

    # Use common utility to get full device info
    return get_full_device_info(model=loaded_model, intended_device=intended_device)


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="flan",
    health_manager=_health_manager,
    custom_components={
        "model_loaded": lambda: _model_loader.is_loaded() if _model_loader else False,
        "model_name": lambda: MODEL_NAME,
        "model_size": lambda: MODEL_SIZE.name,
        "device_info": _get_flan_device_info,  # Add device info component
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
