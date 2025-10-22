"""Prometheus metrics for audio orchestrator services.

This module provides standardized metrics collection across all services
in the audio orchestrator platform.
"""

import time
import inspect
from functools import wraps
from collections.abc import Callable
from typing import Any

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    start_http_server,
    REGISTRY,
)

# Track created metrics to avoid duplicate registration
_created_metrics: dict[str, Any] = {}


def _get_or_create_metric(
    metric_class: type, name: str, description: str, **kwargs: Any
) -> Any:
    """Get existing metric or create new one to avoid duplicate registration."""
    if name in _created_metrics:
        return _created_metrics[name]

    # Create new metric using default registry
    metric = metric_class(name, description, **kwargs)
    _created_metrics[name] = metric
    return metric


# Lazy initialization of metrics to avoid conflicts
_metrics_created = False


def _ensure_metrics_created() -> None:
    """Ensure metrics are created only once."""
    global _metrics_created
    if _metrics_created:
        return
    _metrics_created = True


# Service Information
service_info = _get_or_create_metric(Info, "service_info", "Service information")
service_health = _get_or_create_metric(
    Gauge, "service_health", "Service health status (1=healthy, 0=unhealthy)"
)

# Audio Processing Metrics
audio_chunks_processed_total = _get_or_create_metric(
    Counter,
    "audio_chunks_processed_total",
    "Total audio chunks processed through pipeline",
    labelnames=["service", "adapter_type"],
)

audio_processing_duration_seconds = _get_or_create_metric(
    Histogram,
    "audio_processing_duration_seconds",
    "Audio processing duration in seconds",
    labelnames=["service", "stage"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

audio_quality_score = _get_or_create_metric(
    Histogram,
    "audio_quality_score",
    "Audio quality score (0-1)",
    labelnames=["service", "quality_type"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# Agent Metrics
agent_invocations_total = _get_or_create_metric(
    Counter,
    "agent_invocations_total",
    "Total agent invocations",
    labelnames=["service", "agent_name", "status"],
)

agent_execution_duration_seconds = _get_or_create_metric(
    Histogram,
    "agent_execution_duration_seconds",
    "Agent execution duration in seconds",
    labelnames=["service", "agent_name"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

agent_response_size_bytes = _get_or_create_metric(
    Histogram,
    "agent_response_size_bytes",
    "Agent response size in bytes",
    labelnames=["service", "agent_name"],
    buckets=[100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000],
)

# STT Metrics
stt_requests_total = _get_or_create_metric(
    Counter,
    "stt_requests_total",
    "Total STT requests",
    labelnames=["service", "status"],
)

stt_processing_duration_seconds = _get_or_create_metric(
    Histogram,
    "stt_processing_duration_seconds",
    "STT processing duration in seconds",
    labelnames=["service"],
    buckets=[0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

stt_audio_duration_seconds = _get_or_create_metric(
    Histogram,
    "stt_audio_duration_seconds",
    "Duration of audio sent to STT in seconds",
    labelnames=["service"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# TTS Metrics
tts_requests_total = _get_or_create_metric(
    Counter,
    "tts_requests_total",
    "Total TTS requests",
    labelnames=["service", "status"],
)

tts_synthesis_duration_seconds = _get_or_create_metric(
    Histogram,
    "tts_synthesis_duration_seconds",
    "TTS synthesis duration in seconds",
    labelnames=["service"],
    buckets=[0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

tts_text_length_chars = _get_or_create_metric(
    Histogram,
    "tts_text_length_chars",
    "Length of text sent to TTS in characters",
    labelnames=["service"],
    buckets=[10, 50, 100, 500, 1000, 5000, 10000],
)

# LLM Metrics
llm_requests_total = _get_or_create_metric(
    Counter,
    "llm_requests_total",
    "Total LLM requests",
    labelnames=["service", "model", "status"],
)

llm_processing_duration_seconds = _get_or_create_metric(
    Histogram,
    "llm_processing_duration_seconds",
    "LLM processing duration in seconds",
    labelnames=["service", "model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

llm_tokens_total = _get_or_create_metric(
    Counter,
    "llm_tokens_total",
    "Total LLM tokens processed",
    labelnames=["service", "model", "token_type"],
)

# End-to-End Metrics
end_to_end_response_duration_seconds = _get_or_create_metric(
    Histogram,
    "end_to_end_response_duration_seconds",
    "Total response time from input to output in seconds",
    labelnames=["service"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

wake_detection_duration_seconds = _get_or_create_metric(
    Histogram,
    "wake_detection_duration_seconds",
    "Wake phrase detection duration in seconds",
    labelnames=["service"],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0],
)

# Context and Session Metrics
context_operations_total = _get_or_create_metric(
    Counter,
    "context_operations_total",
    "Total context operations",
    labelnames=["service", "operation_type", "status"],
)

session_duration_seconds = _get_or_create_metric(
    Histogram,
    "session_duration_seconds",
    "Session duration in seconds",
    labelnames=["service"],
    buckets=[10, 30, 60, 300, 600, 1800, 3600, 7200],
)

active_sessions = _get_or_create_metric(
    Gauge, "active_sessions", "Number of active sessions", labelnames=["service"]
)

# Error Metrics
errors_total = _get_or_create_metric(
    Counter,
    "errors_total",
    "Total errors by type",
    labelnames=["service", "error_type", "component"],
)

# Resource Metrics
memory_usage_bytes = _get_or_create_metric(
    Gauge, "memory_usage_bytes", "Memory usage in bytes", labelnames=["service"]
)

cpu_usage_percent = _get_or_create_metric(
    Gauge, "cpu_usage_percent", "CPU usage percentage", labelnames=["service"]
)

# HTTP Metrics
http_requests_total = _get_or_create_metric(
    Counter,
    "http_requests_total",
    "Total HTTP requests",
    labelnames=["service", "method", "endpoint", "status_code"],
)

http_request_duration_seconds = _get_or_create_metric(
    Histogram,
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=["service", "method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# MCP Metrics
mcp_tool_calls_total = _get_or_create_metric(
    Counter,
    "mcp_tool_calls_total",
    "Total MCP tool calls",
    labelnames=["service", "tool_name", "status"],
)

mcp_tool_duration_seconds = _get_or_create_metric(
    Histogram,
    "mcp_tool_duration_seconds",
    "MCP tool execution duration in seconds",
    labelnames=["service", "tool_name"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)


class MetricsCollector:
    """Centralized metrics collection for audio orchestrator services."""

    def __init__(self, service_name: str, service_version: str = "1.0.0"):
        """Initialize metrics collector for a service.

        Args:
            service_name: Name of the service (e.g., 'discord', 'stt', 'orchestrator')
            service_version: Version of the service
        """
        self.service_name = service_name
        self.service_version = service_version

        # Set service info (Info metrics don't need labels)
        service_info.info({"service": service_name, "version": service_version})

        # Initialize health status
        service_health.labels(service=service_name).set(1)

    def track_audio_processing(
        self, stage: str, duration: float, adapter_type: str = "unknown"
    ) -> None:
        """Track audio processing metrics."""
        audio_chunks_processed_total.labels(
            service=self.service_name, adapter_type=adapter_type
        ).inc()

        audio_processing_duration_seconds.labels(
            service=self.service_name, stage=stage
        ).observe(duration)

    def track_audio_quality(self, quality_type: str, score: float) -> None:
        """Track audio quality metrics."""
        audio_quality_score.labels(
            service=self.service_name, quality_type=quality_type
        ).observe(score)

    def track_agent_execution(
        self,
        agent_name: str,
        duration: float,
        status: str = "success",
        response_size: int = 0,
    ) -> None:
        """Track agent execution metrics."""
        agent_invocations_total.labels(
            service=self.service_name, agent_name=agent_name, status=status
        ).inc()

        agent_execution_duration_seconds.labels(
            service=self.service_name, agent_name=agent_name
        ).observe(duration)

        if response_size > 0:
            agent_response_size_bytes.labels(
                service=self.service_name, agent_name=agent_name
            ).observe(response_size)

    def track_stt_request(
        self, duration: float, audio_duration: float, status: str = "success"
    ) -> None:
        """Track STT request metrics."""
        stt_requests_total.labels(service=self.service_name, status=status).inc()

        stt_processing_duration_seconds.labels(service=self.service_name).observe(
            duration
        )

        stt_audio_duration_seconds.labels(service=self.service_name).observe(
            audio_duration
        )

    def track_tts_request(
        self, duration: float, text_length: int, status: str = "success"
    ) -> None:
        """Track TTS request metrics."""
        tts_requests_total.labels(service=self.service_name, status=status).inc()

        tts_synthesis_duration_seconds.labels(service=self.service_name).observe(
            duration
        )

        tts_text_length_chars.labels(service=self.service_name).observe(text_length)

    def track_llm_request(
        self,
        model: str,
        duration: float,
        input_tokens: int,
        output_tokens: int,
        status: str = "success",
    ) -> None:
        """Track LLM request metrics."""
        llm_requests_total.labels(
            service=self.service_name, model=model, status=status
        ).inc()

        llm_processing_duration_seconds.labels(
            service=self.service_name, model=model
        ).observe(duration)

        llm_tokens_total.labels(
            service=self.service_name,
            model=model,
            token_type="input",  # noqa: S106
        ).inc(input_tokens)

        llm_tokens_total.labels(
            service=self.service_name,
            model=model,
            token_type="output",  # noqa: S106
        ).inc(output_tokens)

    def track_end_to_end_response(self, duration: float) -> None:
        """Track end-to-end response time."""
        end_to_end_response_duration_seconds.labels(service=self.service_name).observe(
            duration
        )

    def track_wake_detection(self, duration: float) -> None:
        """Track wake phrase detection time."""
        wake_detection_duration_seconds.labels(service=self.service_name).observe(
            duration
        )

    def track_context_operation(
        self, operation_type: str, status: str = "success"
    ) -> None:
        """Track context operations."""
        context_operations_total.labels(
            service=self.service_name, operation_type=operation_type, status=status
        ).inc()

    def track_session(self, duration: float) -> None:
        """Track session duration."""
        session_duration_seconds.labels(service=self.service_name).observe(duration)

    def set_active_sessions(self, count: int) -> None:
        """Set number of active sessions."""
        active_sessions.labels(service=self.service_name).set(count)

    def track_error(self, error_type: str, component: str) -> None:
        """Track errors."""
        errors_total.labels(
            service=self.service_name, error_type=error_type, component=component
        ).inc()

    def set_health_status(self, is_healthy: bool) -> None:
        """Set service health status."""
        service_health.labels(service=self.service_name).set(1 if is_healthy else 0)

    def track_http_request(
        self, method: str, endpoint: str, duration: float, status_code: int
    ) -> None:
        """Track HTTP request metrics."""
        http_requests_total.labels(
            service=self.service_name,
            method=method,
            endpoint=endpoint,
            status_code=str(status_code),
        ).inc()

        http_request_duration_seconds.labels(
            service=self.service_name, method=method, endpoint=endpoint
        ).observe(duration)

    def track_mcp_tool_call(
        self, tool_name: str, duration: float, status: str = "success"
    ) -> None:
        """Track MCP tool call metrics."""
        mcp_tool_calls_total.labels(
            service=self.service_name, tool_name=tool_name, status=status
        ).inc()

        mcp_tool_duration_seconds.labels(
            service=self.service_name, tool_name=tool_name
        ).observe(duration)


def track_latency(
    histogram: Histogram, labels: dict[str, str] | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to track function execution latency.

    Args:
        histogram: Prometheus histogram to record metrics
        labels: Optional labels to add to the histogram
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if labels:
                    histogram.labels(**labels).observe(duration)
                else:
                    histogram.observe(duration)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if labels:
                    histogram.labels(**labels).observe(duration)
                else:
                    histogram.observe(duration)

        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def init_metrics_registry(
    service_name: str, service_version: str = "1.0.0"
) -> MetricsCollector:
    """Initialize metrics registry for a service.

    Args:
        service_name: Name of the service
        service_version: Version of the service

    Returns:
        MetricsCollector instance for the service
    """
    return MetricsCollector(service_name, service_version)


def start_metrics_server(port: int = 8000) -> None:
    """Start Prometheus metrics server.

    Args:
        port: Port to serve metrics on
    """
    start_http_server(port)
    print(f"Metrics server started on port {port}")


def get_metrics() -> str:
    """Get current metrics in Prometheus format.

    Returns:
        Metrics in Prometheus exposition format
    """
    return str(generate_latest(REGISTRY).decode("utf-8"))
