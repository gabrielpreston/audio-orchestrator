"""
Guardrails Service

This service provides input/output validation, toxicity detection, PII detection,
and rate limiting for the audio orchestrator system.
"""

import hashlib
import re
import time
from typing import Any

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from services.common.config import (
    LoggingConfig,
    get_service_preset,
)
from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints
from services.common.model_loader import BackgroundModelLoader
from services.common.app_factory import create_service_app
from services.common.structured_logging import configure_logging, get_logger
from services.common.tracing import get_observability_manager
from services.common.permissions import (
    check_directory_permissions,
    ensure_model_directory,
)


# ML imports for toxicity detection
try:
    from transformers import pipeline

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

# Rate limiting imports
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address

    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False

# Load configuration using standard config classes
_config_preset = get_service_preset("guardrails")
_logging_config = LoggingConfig(**_config_preset["logging"])

# Configure logging using config class
configure_logging(
    _logging_config.level,
    json_logs=_logging_config.json_logs,
    service_name="guardrails",
)
logger = get_logger(__name__, service_name="guardrails")

# Health manager and observability
_health_manager = HealthManager("guardrails")
_observability_manager = None
_guardrails_metrics = {}
_http_metrics = {}

# Configuration
_toxicity_detector = None
_limiter = None
# Model loader for background loading
_model_loader: BackgroundModelLoader | None = None

# Toxicity result cache (simple in-memory cache for repeated inputs)
_toxicity_cache: dict[str, dict[str, Any]] = {}
_TOXICITY_CACHE_MAX_SIZE = 100  # Limit cache size to prevent memory issues

# PII patterns
PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
}

# Dangerous prompt patterns
DANGEROUS_PATTERNS = [
    "ignore previous",
    "system:",
    "assistant:",
    "[INST]",
    "forget everything",
    "new instructions",
    "override",
    "jailbreak",
    "roleplay",
    "pretend to be",
]


class ValidationRequest(BaseModel):
    text: str = Field(..., description="Text to validate")
    validation_type: str = Field(
        default="input", description="Type of validation (input/output)"
    )


class ValidationResponse(BaseModel):
    safe: bool = Field(..., description="Whether the text is safe")
    reason: str | None = Field(None, description="Reason if not safe")
    sanitized: str | None = Field(None, description="Sanitized version of text")
    filtered: str | None = Field(None, description="Filtered version of text")


class EscalationRequest(BaseModel):
    reason: str = Field(..., description="Reason for escalation")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context"
    )


class EscalationResponse(BaseModel):
    message: str = Field(..., description="Escalation response message")
    escalated: bool = Field(..., description="Whether escalation was successful")


def _load_toxicity_model() -> Any | None:
    """Load toxicity detection model (used by BackgroundModelLoader)."""
    if not TRANSFORMERS_AVAILABLE:
        logger.warning(
            "guardrails.transformers_unavailable", message="Transformers not available"
        )
        return None

    try:
        # Check if force download is enabled
        force_download = False
        if _model_loader is not None:
            force_download = _model_loader.is_force_download()

        # Load toxicity detection model
        # HuggingFace pipeline has built-in caching
        model_name = "unitary/toxic-bert"

        # Get cache directory from environment (migrated to HF_HOME per transformers v5 deprecation)
        import os
        import time

        load_start = time.time()
        cache_dir = os.getenv("HF_HOME", os.getenv("TRANSFORMERS_CACHE", "/app/models"))

        logger.info(
            "guardrails.model_load_start",
            model_name=model_name,
            cache_dir=cache_dir,
            force_download=force_download,
            phase="load_start",
        )

        # Ensure cache directory is writable
        if not ensure_model_directory(cache_dir):
            diagnostics = check_directory_permissions(cache_dir)
            logger.error(
                "guardrails.cache_directory_not_writable",
                cache_dir=cache_dir,
                diagnostics=diagnostics,
                user_id=os.getuid(),
                group_id=os.getgid(),
                phase="permission_check_failed",
            )
            return None

        # Log exact parameters that will be passed to pipeline
        pipeline_params: dict[str, Any] = {
            "task": "text-classification",
            "model": model_name,
        }
        if force_download:
            pipeline_params["model_kwargs"] = {
                "force_download": True,
                "cache_dir": cache_dir,
            }
        else:
            pipeline_params["model_kwargs"] = {"cache_dir": cache_dir}

        logger.debug(
            "guardrails.pipeline_parameters",
            phase="pipeline_params",
            pipeline_parameters=pipeline_params,
            message="Parameters for transformers pipeline",
        )

        # Pass force_download and cache_dir to pipeline if enabled
        pipeline_start = time.time()
        if force_download:
            logger.info(
                "guardrails.force_download_loading",
                model=model_name,
                cache_dir=cache_dir,
                phase="force_download",
            )
            detector = pipeline(
                "text-classification",
                model=model_name,
                model_kwargs={"force_download": True, "cache_dir": cache_dir},
            )
            pipeline_duration = time.time() - pipeline_start
            total_duration = time.time() - load_start

            logger.info(
                "guardrails.toxicity_model_loaded",
                model=model_name,
                force_download=True,
                cache_dir=cache_dir,
                pipeline_duration_ms=round(pipeline_duration * 1000, 2),
                total_duration_ms=round(total_duration * 1000, 2),
                phase="load_complete",
            )
        else:
            logger.debug(
                "guardrails.loading_model",
                model=model_name,
                cache_dir=cache_dir,
                phase="normal_load",
            )
            detector = pipeline(
                "text-classification",
                model=model_name,
                model_kwargs={"cache_dir": cache_dir},
            )
            pipeline_duration = time.time() - pipeline_start
            total_duration = time.time() - load_start

            logger.info(
                "guardrails.toxicity_model_loaded",
                model=model_name,
                cache_dir=cache_dir,
                pipeline_duration_ms=round(pipeline_duration * 1000, 2),
                total_duration_ms=round(total_duration * 1000, 2),
                phase="load_complete",
            )

        return detector
    except PermissionError as e:
        import os

        diagnostics = check_directory_permissions(
            os.getenv("HF_HOME", os.getenv("TRANSFORMERS_CACHE", "/app/models"))
        )
        logger.error(
            "guardrails.model_loading_permission_error",
            error=str(e),
            cache_dir=os.getenv(
                "HF_HOME", os.getenv("TRANSFORMERS_CACHE", "/app/models")
            ),
            diagnostics=diagnostics,
            user_id=os.getuid(),
            group_id=os.getgid(),
        )
        return None
    except Exception as e:
        logger.error("guardrails.model_loading_failed", error=str(e))
        return None


def initialize_rate_limiter(app_instance: Any) -> None:
    """Initialize rate limiter."""
    global _limiter

    if not SLOWAPI_AVAILABLE:
        logger.warning(
            "guardrails.slowapi_unavailable", message="SlowAPI not available"
        )
        return

    try:
        _limiter = Limiter(key_func=get_remote_address)
        app_instance.state.limiter = _limiter
        app_instance.add_exception_handler(429, _rate_limit_exceeded_handler)
        logger.info("guardrails.rate_limiter_initialized")
    except Exception as e:
        logger.error("guardrails.rate_limiter_failed", error=str(e))
        _limiter = None


async def _startup() -> None:
    """Initialize the guardrails service."""
    global \
        _toxicity_detector, \
        _model_loader, \
        _observability_manager, \
        _guardrails_metrics, \
        _http_metrics

    try:
        # Get observability manager (factory already setup observability)
        _observability_manager = get_observability_manager("guardrails")

        # Create service-specific metrics
        from services.common.audio_metrics import (
            create_guardrails_metrics,
            create_http_metrics,
            create_system_metrics,
        )

        _guardrails_metrics = create_guardrails_metrics(_observability_manager)
        _http_metrics = create_http_metrics(_observability_manager)
        _system_metrics = create_system_metrics(_observability_manager)

        # Set observability manager in health manager
        _health_manager.set_observability_manager(_observability_manager)

        # Initialize model loader (HuggingFace pipeline has built-in caching)
        # Use cache_loader_func=None since pipeline handles caching internally
        _model_loader = BackgroundModelLoader(
            cache_loader_func=None,  # Pipeline has built-in caching
            download_loader_func=_load_toxicity_model,
            logger=logger,
            loader_name="toxicity_model",
        )

        # Start background loading (non-blocking)
        await _model_loader.initialize()
        logger.info("guardrails.model_loader_initialized")

        # Get model from loader and set global for backward compatibility
        if _model_loader.is_loaded():
            _toxicity_detector = _model_loader.get_model()

        # Register dependencies
        # Models must be loaded AND not currently loading for service to be ready
        _health_manager.register_dependency(
            "toxicity_model",
            lambda: (
                _model_loader.is_loaded() and not _model_loader.is_loading()
                if _model_loader
                else False
            ),
        )
        # Rate limiter is optional - service can function without it (just won't rate limit)
        # Don't block readiness if rate limiter fails to initialize
        # _health_manager.register_dependency(
        #     "rate_limiter", lambda: _limiter is not None
        # )
        _health_manager.register_dependency(
            "transformers", lambda: TRANSFORMERS_AVAILABLE
        )
        _health_manager.register_dependency("slowapi", lambda: SLOWAPI_AVAILABLE)

        # Mark startup complete
        _health_manager.mark_startup_complete()

        logger.info(
            "guardrails.startup_complete",
            toxicity_available=_toxicity_detector is not None,
            rate_limiting_available=_limiter is not None,
        )

    except Exception as exc:
        logger.error("guardrails.startup_failed", error=str(exc))
        # Continue without crashing - service will report not_ready


async def _shutdown() -> None:
    """Cleanup on shutdown."""
    logger.info("guardrails.shutdown")


# Create app using factory pattern
app = create_service_app(
    "guardrails",
    "1.0.0",
    title="Guardrails Service",
    startup_callback=_startup,
    shutdown_callback=_shutdown,
)


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="guardrails",
    health_manager=_health_manager,
    custom_components={
        "toxicity_model_loaded": lambda: _model_loader.is_loaded()
        if _model_loader
        else False,
        "rate_limiter_available": lambda: _limiter is not None,
        "transformers_available": lambda: TRANSFORMERS_AVAILABLE,
        "slowapi_available": lambda: SLOWAPI_AVAILABLE,
    },
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())


@app.post("/validate/input")  # type: ignore[misc]
async def validate_input(
    request: ValidationRequest, http_request: Request
) -> ValidationResponse:
    """Validate input text for safety and compliance."""
    # Extract correlation ID from headers or context
    correlation_id: str | None = None
    try:
        from services.common.middleware import get_correlation_id

        correlation_id = get_correlation_id()
    except ImportError:
        pass

    # Fallback to extracting from Request headers
    if not correlation_id:
        correlation_id = http_request.headers.get("X-Correlation-ID")

    start_time = time.time()

    try:
        text = request.text

        # Length check
        if len(text) > 1000:
            # Record metrics
            processing_time = time.time() - start_time
            if _guardrails_metrics:
                if "validation_requests" in _guardrails_metrics:
                    _guardrails_metrics["validation_requests"].add(
                        1,
                        attributes={
                            "type": "input",
                            "status": "blocked",
                            "reason": "too_long",
                        },
                    )
                if "validation_duration" in _guardrails_metrics:
                    _guardrails_metrics["validation_duration"].record(
                        processing_time,
                        attributes={"type": "input", "status": "blocked"},
                    )

            return ValidationResponse(
                safe=False, reason="too_long", sanitized=text[:1000] + "..."
            )

        # Prompt injection detection
        text_lower = text.lower()
        for pattern in DANGEROUS_PATTERNS:
            if pattern in text_lower:
                # Record metrics
                processing_time = time.time() - start_time
                if _guardrails_metrics:
                    if "validation_requests" in _guardrails_metrics:
                        _guardrails_metrics["validation_requests"].add(
                            1,
                            attributes={
                                "type": "input",
                                "status": "blocked",
                                "reason": "prompt_injection",
                            },
                        )
                    if "validation_duration" in _guardrails_metrics:
                        _guardrails_metrics["validation_duration"].record(
                            processing_time,
                            attributes={"type": "input", "status": "blocked"},
                        )

                return ValidationResponse(
                    safe=False, reason="prompt_injection", sanitized=text
                )

        # Basic content filtering
        sanitized = _sanitize_text(text)

        # Record success metrics
        processing_time = time.time() - start_time
        if _guardrails_metrics:
            if "validation_requests" in _guardrails_metrics:
                _guardrails_metrics["validation_requests"].add(
                    1, attributes={"type": "input", "status": "success"}
                )
            if "validation_duration" in _guardrails_metrics:
                _guardrails_metrics["validation_duration"].record(
                    processing_time, attributes={"type": "input", "status": "success"}
                )

        return ValidationResponse(
            safe=True, sanitized=sanitized, filtered=None, reason=None
        )

    except Exception as e:
        # Record error metrics
        processing_time = time.time() - start_time
        if _guardrails_metrics:
            if "validation_requests" in _guardrails_metrics:
                _guardrails_metrics["validation_requests"].add(
                    1, attributes={"type": "input", "status": "error"}
                )
            if "validation_duration" in _guardrails_metrics:
                _guardrails_metrics["validation_duration"].record(
                    processing_time, attributes={"type": "input", "status": "error"}
                )

        logger.error(
            "guardrails.input_validation_failed",
            error=str(e),
            text=request.text[:100],
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Input validation failed: {str(e)}"
        ) from e


@app.post("/validate/output")  # type: ignore[misc]
async def validate_output(
    request: ValidationRequest, http_request: Request
) -> ValidationResponse:
    """Validate output text for toxicity and PII."""
    # Extract correlation ID from headers or context
    correlation_id: str | None = None
    try:
        from services.common.middleware import get_correlation_id

        correlation_id = get_correlation_id()
    except ImportError:
        pass

    # Fallback to extracting from Request headers
    if not correlation_id:
        correlation_id = http_request.headers.get("X-Correlation-ID")

    start_time = time.time()

    try:
        text = request.text

        # Check model status and get detector (non-blocking)
        model_check_start = time.time()
        global _toxicity_detector
        if _model_loader is None:
            logger.debug(
                "guardrails.model_loader_not_initialized",
                correlation_id=correlation_id,
            )
            # Continue without toxicity check
            detector = None
        elif _model_loader.is_loading():
            logger.debug(
                "guardrails.model_loading",
                skipping_check=True,
                correlation_id=correlation_id,
            )
            # Continue without toxicity check
            detector = None
        elif not _model_loader.is_loaded():
            # Ensure model is loaded (may trigger lazy load)
            if await _model_loader.ensure_loaded():
                detector = _model_loader.get_model()
                _toxicity_detector = detector
            else:
                detector = None
        else:
            detector = _model_loader.get_model()
            _toxicity_detector = detector
        model_check_time = (time.time() - model_check_start) * 1000
        logger.info(
            "guardrails.model_check_completed",
            duration_ms=round(model_check_time, 2),
            detector_available=detector is not None,
            correlation_id=correlation_id,
        )

        # Toxicity check with caching
        if detector is not None:
            try:
                # Create cache key from text hash
                text_hash = hashlib.sha256(text.encode()).hexdigest()
                cache_key = f"toxicity:{text_hash}"

                # Check cache first
                cached_result = _toxicity_cache.get(cache_key)
                if cached_result is not None:
                    logger.info(
                        "guardrails.toxicity_cache_hit",
                        duration_ms=0.0,  # Cache hit is instantaneous
                        label=cached_result["label"],
                        score=cached_result["score"],
                        correlation_id=correlation_id,
                        cache_size=len(_toxicity_cache),
                    )
                    result = cached_result
                else:
                    # Cache miss - run inference
                    toxicity_check_start = time.time()
                    result = detector(text)[0]
                    toxicity_check_time = (time.time() - toxicity_check_start) * 1000

                    # Cache result (with size limit)
                    if len(_toxicity_cache) >= _TOXICITY_CACHE_MAX_SIZE:
                        # Remove oldest entry (simple FIFO eviction)
                        oldest_key = next(iter(_toxicity_cache))
                        del _toxicity_cache[oldest_key]
                        logger.debug(
                            "guardrails.toxicity_cache_evicted",
                            evicted_key=oldest_key,
                            cache_size=len(_toxicity_cache),
                        )
                    _toxicity_cache[cache_key] = result

                    logger.info(
                        "guardrails.toxicity_inference_completed",
                        duration_ms=round(toxicity_check_time, 2),
                        label=result["label"],
                        score=result["score"],
                        correlation_id=correlation_id,
                        cache_hit=False,
                        cache_size=len(_toxicity_cache),
                    )

                # Record toxicity check metric
                if _guardrails_metrics and "toxicity_checks" in _guardrails_metrics:
                    _guardrails_metrics["toxicity_checks"].add(
                        1, attributes={"result": result["label"]}
                    )

                if result["label"] == "toxic" and result["score"] > 0.7:
                    # Record blocked metrics
                    processing_time = time.time() - start_time
                    if _guardrails_metrics:
                        if "validation_requests" in _guardrails_metrics:
                            _guardrails_metrics["validation_requests"].add(
                                1,
                                attributes={
                                    "type": "output",
                                    "status": "blocked",
                                    "reason": "toxic_content",
                                },
                            )
                        if "validation_duration" in _guardrails_metrics:
                            _guardrails_metrics["validation_duration"].record(
                                processing_time,
                                attributes={"type": "output", "status": "blocked"},
                            )

                    logger.info(
                        "guardrails.toxic_content_blocked",
                        label=result["label"],
                        score=result["score"],
                        correlation_id=correlation_id,
                    )
                    return ValidationResponse(
                        safe=False, reason="toxic_content", filtered=text
                    )
            except Exception as e:
                logger.warning(
                    "guardrails.toxicity_check_failed",
                    error=str(e),
                    correlation_id=correlation_id,
                )

        # PII detection and redaction
        pii_redaction_start = time.time()
        filtered_text = _redact_pii(text)
        pii_redaction_time = (time.time() - pii_redaction_start) * 1000
        logger.info(
            "guardrails.pii_redaction_completed",
            duration_ms=round(pii_redaction_time, 2),
            text_changed=filtered_text != text,
            correlation_id=correlation_id,
        )

        # Record PII detection metrics
        original_text = text
        if filtered_text != original_text:
            # PII was detected and redacted
            for pii_type in PII_PATTERNS:
                if (
                    f"[{pii_type.upper()}_REDACTED]" in filtered_text
                    and _guardrails_metrics
                    and "pii_detections" in _guardrails_metrics
                ):
                    _guardrails_metrics["pii_detections"].add(
                        1, attributes={"type": pii_type}
                    )

        # Record success metrics
        processing_time = time.time() - start_time
        if _guardrails_metrics:
            if "validation_requests" in _guardrails_metrics:
                _guardrails_metrics["validation_requests"].add(
                    1, attributes={"type": "output", "status": "success"}
                )
            if "validation_duration" in _guardrails_metrics:
                _guardrails_metrics["validation_duration"].record(
                    processing_time, attributes={"type": "output", "status": "success"}
                )

        return ValidationResponse(
            safe=True, filtered=filtered_text, sanitized=None, reason=None
        )

    except Exception as e:
        # Record error metrics
        processing_time = time.time() - start_time
        if _guardrails_metrics:
            if "validation_requests" in _guardrails_metrics:
                _guardrails_metrics["validation_requests"].add(
                    1, attributes={"type": "output", "status": "error"}
                )
            if "validation_duration" in _guardrails_metrics:
                _guardrails_metrics["validation_duration"].record(
                    processing_time, attributes={"type": "output", "status": "error"}
                )

        logger.error(
            "guardrails.output_validation_failed",
            error=str(e),
            text=request.text[:100],
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Output validation failed: {str(e)}"
        ) from e


@app.post("/escalate")  # type: ignore[misc]
async def escalate_to_human(request: EscalationRequest) -> EscalationResponse:
    """Escalate request to human review."""
    try:
        # Record escalation metric
        if _guardrails_metrics and "escalations" in _guardrails_metrics:
            _guardrails_metrics["escalations"].add(
                1, attributes={"reason": request.reason}
            )

        # Log for human review
        logger.warning(
            "guardrails.escalation_required",
            reason=request.reason,
            context=request.context,
        )

        return EscalationResponse(
            message="This request requires human review.", escalated=True
        )

    except Exception as e:
        logger.error("guardrails.escalation_failed", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Escalation failed: {str(e)}"
        ) from e


def _sanitize_text(text: str) -> str:
    """Sanitize text by removing potentially dangerous content."""
    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text.strip())

    # Remove control characters
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)

    return text


def _redact_pii(text: str) -> str:
    """Detect and redact PII from text."""
    filtered_text = text

    for pii_type, pattern in PII_PATTERNS.items():
        if re.search(pattern, filtered_text):
            # Redact PII
            filtered_text = re.sub(
                pattern, f"[{pii_type.upper()}_REDACTED]", filtered_text
            )

    return filtered_text
