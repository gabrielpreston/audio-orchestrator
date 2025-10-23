"""
Guardrails Service

This service provides input/output validation, toxicity detection, PII detection,
and rate limiting for the audio orchestrator system.
"""

import re
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.common.health import HealthManager, HealthStatus
from services.common.logging import get_logger

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

logger = get_logger(__name__)
app = FastAPI(title="Guardrails Service", version="1.0.0")

# Health manager
_health_manager = HealthManager("guardrails")

# Configuration
_toxicity_detector = None
_limiter = None

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


def initialize_models() -> None:
    """Initialize ML models for toxicity detection."""
    global _toxicity_detector

    if not TRANSFORMERS_AVAILABLE:
        logger.warning(
            "guardrails.transformers_unavailable", message="Transformers not available"
        )
        return

    try:
        # Load toxicity detection model
        model_name = "unitary/toxic-bert"
        _toxicity_detector = pipeline("text-classification", model=model_name)
        logger.info("guardrails.toxicity_model_loaded", model=model_name)
    except Exception as e:
        logger.error("guardrails.model_loading_failed", error=str(e))
        _toxicity_detector = None


def initialize_rate_limiter() -> None:
    """Initialize rate limiter."""
    global _limiter

    if not SLOWAPI_AVAILABLE:
        logger.warning(
            "guardrails.slowapi_unavailable", message="SlowAPI not available"
        )
        return

    try:
        _limiter = Limiter(key_func=get_remote_address)
        app.state.limiter = _limiter
        app.add_exception_handler(429, _rate_limit_exceeded_handler)
        logger.info("guardrails.rate_limiter_initialized")
    except Exception as e:
        logger.error("guardrails.rate_limiter_failed", error=str(e))
        _limiter = None


@app.on_event("startup")  # type: ignore[misc]
async def startup() -> None:
    """Initialize the guardrails service."""
    try:
        # Initialize models
        initialize_models()
        initialize_rate_limiter()

        # Register dependencies
        _health_manager.register_dependency(
            "toxicity_model", lambda: _toxicity_detector is not None
        )
        _health_manager.register_dependency(
            "rate_limiter", lambda: _limiter is not None
        )
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


@app.on_event("shutdown")  # type: ignore[misc]
async def shutdown() -> None:
    """Cleanup on shutdown."""
    logger.info("guardrails.shutdown")


@app.get("/health/live")  # type: ignore[misc]
async def health_live() -> dict[str, str]:
    """Liveness check."""
    return {"status": "alive", "service": "guardrails"}


@app.get("/health/ready")  # type: ignore[misc]
async def health_ready() -> dict[str, Any]:
    """Readiness check with component status."""
    health_status = await _health_manager.get_health_status()

    # Determine status string
    if not health_status.ready:
        status_str = (
            "degraded" if health_status.status == HealthStatus.DEGRADED else "not_ready"
        )
    else:
        status_str = "ready"

    return {
        "status": status_str,
        "service": "guardrails",
        "components": {
            "toxicity_model_loaded": _toxicity_detector is not None,
            "rate_limiter_available": _limiter is not None,
            "transformers_available": TRANSFORMERS_AVAILABLE,
            "slowapi_available": SLOWAPI_AVAILABLE,
            "startup_complete": _health_manager._startup_complete,
        },
        "dependencies": health_status.details.get("dependencies", {}),
        "health_details": health_status.details,
    }


@app.post("/validate/input")  # type: ignore[misc]
async def validate_input(request: ValidationRequest) -> ValidationResponse:
    """Validate input text for safety and compliance."""
    try:
        text = request.text

        # Length check
        if len(text) > 1000:
            return ValidationResponse(
                safe=False, reason="too_long", sanitized=text[:1000] + "..."
            )

        # Prompt injection detection
        text_lower = text.lower()
        for pattern in DANGEROUS_PATTERNS:
            if pattern in text_lower:
                return ValidationResponse(
                    safe=False, reason="prompt_injection", sanitized=text
                )

        # Basic content filtering
        sanitized = _sanitize_text(text)

        return ValidationResponse(
            safe=True, sanitized=sanitized, filtered=None, reason=None
        )

    except Exception as e:
        logger.error(
            "guardrails.input_validation_failed", error=str(e), text=request.text[:100]
        )
        raise HTTPException(
            status_code=500, detail=f"Input validation failed: {str(e)}"
        ) from e


@app.post("/validate/output")  # type: ignore[misc]
async def validate_output(request: ValidationRequest) -> ValidationResponse:
    """Validate output text for toxicity and PII."""
    try:
        text = request.text

        # Toxicity check
        if _toxicity_detector is not None:
            try:
                result = _toxicity_detector(text)[0]
                if result["label"] == "toxic" and result["score"] > 0.7:
                    return ValidationResponse(
                        safe=False, reason="toxic_content", filtered=text
                    )
            except Exception as e:
                logger.warning("guardrails.toxicity_check_failed", error=str(e))

        # PII detection and redaction
        filtered_text = _redact_pii(text)

        return ValidationResponse(
            safe=True, filtered=filtered_text, sanitized=None, reason=None
        )

    except Exception as e:
        logger.error(
            "guardrails.output_validation_failed", error=str(e), text=request.text[:100]
        )
        raise HTTPException(
            status_code=500, detail=f"Output validation failed: {str(e)}"
        ) from e


@app.post("/escalate")  # type: ignore[misc]
async def escalate_to_human(request: EscalationRequest) -> EscalationResponse:
    """Escalate request to human review."""
    try:
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


@app.get("/metrics")  # type: ignore[misc]
async def get_metrics() -> dict[str, Any]:
    """Get service metrics."""
    return {
        "service": "guardrails",
        "uptime_seconds": time.time() - _health_manager._startup_time,
        "toxicity_model_available": _toxicity_detector is not None,
        "rate_limiter_available": _limiter is not None,
        "pii_patterns_count": len(PII_PATTERNS),
        "dangerous_patterns_count": len(DANGEROUS_PATTERNS),
    }


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
