"""Standardized audio pipeline metrics using OpenTelemetry."""

from typing import Any
from services.common.tracing import ObservabilityManager


def create_audio_metrics(observability_manager: ObservabilityManager) -> dict[str, Any]:
    """Create standardized audio pipeline metrics for services.

    Args:
        observability_manager: ObservabilityManager instance for the service

    Returns:
        Dictionary of metric instruments keyed by metric name
    """
    meter = observability_manager.get_meter()
    if not meter:
        return {}

    return {
        "audio_processing_duration": meter.create_histogram(
            "audio_processing_duration_seconds",
            unit="s",
            description="Audio processing duration by stage",
        ),
        "audio_quality_score": meter.create_histogram(
            "audio_quality_score", unit="1", description="Audio quality score (0-1)"
        ),
        "audio_chunks_processed": meter.create_counter(
            "audio_chunks_processed_total",
            unit="1",
            description="Total audio chunks processed",
        ),
        "wake_detection_duration": meter.create_histogram(
            "wake_detection_duration_seconds",
            unit="s",
            description="Wake phrase detection duration",
        ),
        "end_to_end_latency": meter.create_histogram(
            "end_to_end_response_duration_seconds",
            unit="s",
            description="Voice input to response latency",
        ),
        "active_sessions": meter.create_up_down_counter(
            "active_sessions", unit="1", description="Number of active voice sessions"
        ),
    }


def create_stt_metrics(observability_manager: ObservabilityManager) -> dict[str, Any]:
    """Create STT-specific metrics (replaces Discord Prometheus metrics)."""
    meter = observability_manager.get_meter()
    if not meter:
        return {}

    return {
        "stt_requests": meter.create_counter(
            "stt_requests_total", unit="1", description="Total STT requests by status"
        ),
        "stt_latency": meter.create_histogram(
            "stt_latency_seconds", unit="s", description="STT processing latency"
        ),
        "pre_stt_encode": meter.create_histogram(
            "pre_stt_encode_seconds", unit="s", description="Pre-STT encoding duration"
        ),
        "stt_audio_duration": meter.create_histogram(
            "stt_audio_duration_seconds",
            unit="s",
            description="Duration of audio sent to STT",
        ),
    }


def create_llm_metrics(observability_manager: ObservabilityManager) -> dict[str, Any]:
    """Create LLM-specific metrics."""
    meter = observability_manager.get_meter()
    if not meter:
        return {}

    return {
        "llm_requests": meter.create_counter(
            "llm_requests_total",
            unit="1",
            description="Total LLM requests by model and status",
        ),
        "llm_latency": meter.create_histogram(
            "llm_processing_duration_seconds",
            unit="s",
            description="LLM processing duration",
        ),
        "llm_tokens": meter.create_counter(
            "llm_tokens_total",
            unit="1",
            description="Total LLM tokens processed by type (prompt/completion)",
        ),
    }


def create_tts_metrics(observability_manager: ObservabilityManager) -> dict[str, Any]:
    """Create TTS-specific metrics."""
    meter = observability_manager.get_meter()
    if not meter:
        return {}

    return {
        "tts_requests": meter.create_counter(
            "tts_requests_total", unit="1", description="Total TTS requests by status"
        ),
        "tts_synthesis_duration": meter.create_histogram(
            "tts_synthesis_duration_seconds",
            unit="s",
            description="TTS synthesis duration",
        ),
        "tts_text_length": meter.create_histogram(
            "tts_text_length_chars", unit="1", description="Length of text sent to TTS"
        ),
    }


def create_http_metrics(observability_manager: ObservabilityManager) -> dict[str, Any]:
    """Create HTTP-specific metrics."""
    meter = observability_manager.get_meter()
    if not meter:
        return {}

    return {
        "http_requests": meter.create_counter(
            "http_requests_total", unit="1", description="Total HTTP requests"
        ),
        "http_request_duration": meter.create_histogram(
            "http_request_duration_seconds",
            unit="s",
            description="HTTP request duration",
        ),
    }


def create_guardrails_metrics(
    observability_manager: ObservabilityManager,
) -> dict[str, Any]:
    """Create guardrails-specific metrics."""
    meter = observability_manager.get_meter()
    if not meter:
        return {}

    return {
        "validation_requests": meter.create_counter(
            "guardrails_validation_requests_total",
            unit="1",
            description="Total validation requests by type and status",
        ),
        "validation_duration": meter.create_histogram(
            "guardrails_validation_duration_seconds",
            unit="s",
            description="Validation processing duration",
        ),
        "toxicity_checks": meter.create_counter(
            "guardrails_toxicity_checks_total",
            unit="1",
            description="Total toxicity checks performed",
        ),
        "pii_detections": meter.create_counter(
            "guardrails_pii_detections_total",
            unit="1",
            description="Total PII detections by type",
        ),
        "rate_limit_hits": meter.create_counter(
            "guardrails_rate_limit_hits_total",
            unit="1",
            description="Total rate limit hits",
        ),
        "escalations": meter.create_counter(
            "guardrails_escalations_total",
            unit="1",
            description="Total escalations to human review",
        ),
    }
