"""Standardized audio pipeline metrics using OpenTelemetry."""

from enum import Enum
from pathlib import Path
from typing import Any
from collections.abc import Callable

from opentelemetry.metrics import Observation

from services.common.tracing import ObservabilityManager


class MetricKind(str, Enum):
    """Enumeration of supported metric types for service registration."""

    AUDIO = "audio"
    STT = "stt"
    TTS = "tts"
    LLM = "llm"
    HTTP = "http"
    SYSTEM = "system"
    GUARDRAILS = "guardrails"


def register_service_metrics(
    observability_manager: ObservabilityManager,
    kinds: list[MetricKind],
) -> dict[str, dict[str, Any]]:
    """Register metrics for a service based on requested metric kinds.

    This helper function centralizes metric registration to reduce boilerplate
    in service startup callbacks. It wraps existing `create_*_metrics()` functions
    and returns a structured dictionary keyed by metric group name.

    Args:
        observability_manager: ObservabilityManager instance for the service
        kinds: List of MetricKind enum values specifying which metric groups to create

    Returns:
        Dictionary keyed by metric group name (e.g., "audio", "stt", "system")
        containing the metric dicts returned by each creation function.

    Raises:
        ValueError: If an unknown metric kind is provided

    Example:
        ```python
        from services.common.audio_metrics import MetricKind, register_service_metrics

        metrics = register_service_metrics(
            observability_manager,
            kinds=[MetricKind.AUDIO, MetricKind.SYSTEM]
        )
        # Access metrics by group
        audio_metrics = metrics["audio"]
        system_metrics = metrics["system"]
        ```

    Note:
        HTTP metrics are automatically created by `app_factory.py` and stored in
        `app.state.http_metrics`. Services should reuse those metrics rather than
        creating new ones unless they need local copies for specific reasons.
    """
    from .structured_logging import get_logger

    logger = get_logger(__name__)

    # Validate metric kinds
    valid_kinds = {kind.value for kind in MetricKind}
    provided_kinds = {
        kind.value if isinstance(kind, MetricKind) else kind for kind in kinds
    }

    invalid_kinds = provided_kinds - valid_kinds
    if invalid_kinds:
        raise ValueError(
            f"Invalid metric kinds: {invalid_kinds}. Valid kinds are: {sorted(valid_kinds)}"
        )

    # Map metric kinds to creation functions
    metric_creators: dict[str, Callable[[ObservabilityManager], dict[str, Any]]] = {
        MetricKind.AUDIO.value: create_audio_metrics,
        MetricKind.STT.value: create_stt_metrics,
        MetricKind.TTS.value: create_tts_metrics,
        MetricKind.LLM.value: create_llm_metrics,
        MetricKind.HTTP.value: create_http_metrics,
        MetricKind.SYSTEM.value: create_system_metrics,
        MetricKind.GUARDRAILS.value: create_guardrails_metrics,
    }

    # Create metrics for each requested kind
    result: dict[str, dict[str, Any]] = {}
    unique_kinds = {
        kind.value if isinstance(kind, MetricKind) else kind for kind in kinds
    }

    for kind_value in unique_kinds:
        creator = metric_creators[kind_value]
        try:
            metrics = creator(observability_manager)
            result[kind_value] = metrics
            logger.debug(
                "metrics.registered",
                service=observability_manager.service_name,
                kind=kind_value,
                metric_count=len(metrics),
            )
        except Exception as exc:
            logger.warning(
                "metrics.registration_failed",
                service=observability_manager.service_name,
                kind=kind_value,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            # Continue with other metrics even if one fails
            result[kind_value] = {}

    return result


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
    from .structured_logging import get_logger

    logger = get_logger(__name__)
    meter = observability_manager.get_meter()
    if not meter:
        logger.warning(
            "http_metrics.no_meter", service=observability_manager.service_name
        )
        return {}

    try:
        metrics = {
            "http_requests": meter.create_counter(
                "http_requests_total", unit="1", description="Total HTTP requests"
            ),
            "http_request_duration": meter.create_histogram(
                "http_request_duration_seconds",
                unit="s",
                description="HTTP request duration",
            ),
        }
        logger.debug(
            "http_metrics.created",
            service=observability_manager.service_name,
            metrics=list(metrics.keys()),
        )
        return metrics
    except Exception as exc:
        logger.exception(
            "http_metrics.creation_failed",
            service=observability_manager.service_name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return {}


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


def _read_cgroup_memory_limit() -> int | None:
    """Read Docker memory limit from cgroup files.

    Supports both cgroup v1 and v2.

    Returns:
        Memory limit in bytes, or None if not available or unlimited
    """
    try:
        # Try cgroup v2 first (modern Docker)
        cgroup_v2_path = Path("/sys/fs/cgroup/memory.max")
        if cgroup_v2_path.exists():
            with cgroup_v2_path.open(encoding="utf-8") as f:
                value = f.read().strip()
                if value == "max":
                    return None  # Unlimited
                try:
                    return int(value)
                except ValueError:
                    return None

        # Try cgroup v1 (older Docker)
        cgroup_v1_path = Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")
        if cgroup_v1_path.exists():
            with cgroup_v1_path.open(encoding="utf-8") as f:
                value = f.read().strip()
                try:
                    limit = int(value)
                    # cgroup v1 returns a very large number (9223372036854771712) for unlimited
                    if limit > 9223372036854770000:
                        return None  # Unlimited
                    return limit
                except ValueError:
                    return None
    except OSError:
        # File doesn't exist or can't be read (not in Docker, no limits)
        return None

    return None


def create_system_metrics(
    observability_manager: ObservabilityManager,
) -> dict[str, Any]:
    """Create system-level metrics (memory usage, limits).

    Uses ObservableGauge for callback-based metric collection.
    Metrics are automatically collected every 15 seconds via PeriodicExportingMetricReader.

    Args:
        observability_manager: ObservabilityManager instance for the service

    Returns:
        Dictionary (may be empty - callbacks are registered at creation time)
    """
    meter = observability_manager.get_meter()
    if not meter:
        return {}

    try:
        import psutil
    except ImportError:
        from .structured_logging import get_logger

        logger = get_logger(__name__)
        logger.warning(
            "system_metrics.psutil_not_available",
            service=observability_manager.service_name,
            message="psutil not available - memory metrics will not be exported",
        )
        return {}

    process = psutil.Process()
    service_name = observability_manager.service_name

    # Read memory limit once (may not be available in all environments)
    memory_limit_bytes = _read_cgroup_memory_limit()

    def memory_usage_callback(_callback_options: Any) -> list[Observation]:
        """Callback to observe memory usage in bytes."""
        try:
            memory_info = process.memory_info()
            memory_bytes = memory_info.rss  # Resident Set Size
            return [Observation(memory_bytes, {"service": service_name})]
        except Exception:
            # Silently fail - return empty list to prevent iteration errors
            return []

    def memory_limit_callback(_callback_options: Any) -> list[Observation]:
        """Callback to observe memory limit in bytes (if available)."""
        if memory_limit_bytes is not None:
            try:
                return [Observation(memory_limit_bytes, {"service": service_name})]
            except Exception:
                return []
        return []

    def memory_percent_callback(_callback_options: Any) -> list[Observation]:
        """Callback to observe memory usage as percentage of limit (if limit available)."""
        try:
            memory_info = process.memory_info()
            memory_bytes = memory_info.rss

            if memory_limit_bytes is not None and memory_limit_bytes > 0:
                memory_percent = (memory_bytes / memory_limit_bytes) * 100.0
                return [Observation(memory_percent, {"service": service_name})]
        except Exception as exc:
            # Log exception but return empty list to prevent iteration errors
            from .structured_logging import get_logger

            logger = get_logger(__name__)
            logger.debug(
                "system_metrics.memory_percent_callback_error",
                service=service_name,
                error=str(exc),
                error_type=type(exc).__name__,
            )
        return []

    # Create ObservableGauge instruments with callbacks
    try:
        meter.create_observable_gauge(
            "process_memory_usage_bytes",
            unit="By",
            description="Process memory usage in bytes (RSS)",
            callbacks=[memory_usage_callback],
        )

        # Only create limit gauge if limit is available
        if memory_limit_bytes is not None:
            meter.create_observable_gauge(
                "process_memory_limit_bytes",
                unit="By",
                description="Process memory limit in bytes (from cgroup)",
                callbacks=[memory_limit_callback],
            )

            meter.create_observable_gauge(
                "process_memory_usage_percent",
                unit="1",
                description="Process memory usage as percentage of limit",
                callbacks=[memory_percent_callback],
            )
    except Exception as exc:
        from .structured_logging import get_logger

        logger = get_logger(__name__)
        logger.exception(
            "system_metrics.creation_failed",
            service=observability_manager.service_name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return {}

    # ObservableGauge callbacks are registered at creation time
    # Return empty dict or metadata (callbacks persist independently)
    return {}
