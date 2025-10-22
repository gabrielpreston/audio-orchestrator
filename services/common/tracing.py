"""OpenTelemetry distributed tracing for audio orchestrator services.

This module provides standardized tracing setup and utilities across all services
in the audio orchestrator platform.
"""

import os
import uuid
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource

from .logging import get_logger

logger = get_logger(__name__)


class TracingManager:
    """Manages OpenTelemetry tracing configuration and instrumentation."""

    def __init__(self, service_name: str, service_version: str = "1.0.0"):
        """Initialize tracing manager for a service.

        Args:
            service_name: Name of the service (e.g., 'discord', 'stt', 'orchestrator')
            service_version: Version of the service
        """
        self.service_name = service_name
        self.service_version = service_version
        self._tracer: trace.Tracer | None = None
        self._instrumented = False

    def setup_tracing(self) -> None:
        """Set up OpenTelemetry tracing for the service."""
        if os.getenv("OTEL_ENABLED", "false").lower() != "true":
            logger.info("tracing.disabled", service=self.service_name)
            return

        try:
            # Create resource with service information
            resource = Resource.create(
                {
                    "service.name": self.service_name,
                    "service.version": self.service_version,
                    "service.namespace": "audio-orchestrator",
                }
            )

            # Set up tracer provider
            trace.set_tracer_provider(TracerProvider(resource=resource))

            # Configure exporters based on environment
            self._setup_exporters()

            # Get tracer
            self._tracer = trace.get_tracer(self.service_name, self.service_version)

            logger.info(
                "tracing.initialized",
                service=self.service_name,
                version=self.service_version,
            )

        except Exception as exc:
            logger.error(
                "tracing.setup_failed", service=self.service_name, error=str(exc)
            )
            # Continue without tracing if setup fails
            self._tracer = None

    def _setup_exporters(self) -> None:
        """Set up trace exporters based on configuration."""
        tracer_provider = trace.get_tracer_provider()

        # OTLP exporter (for Jaeger, Zipkin, etc.)
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            otlp_processor = BatchSpanProcessor(otlp_exporter)
            tracer_provider.add_span_processor(otlp_processor)
            logger.info("tracing.otlp_exporter_configured", endpoint=otlp_endpoint)

        # Jaeger exporter (fallback)
        jaeger_endpoint = os.getenv("JAEGER_ENDPOINT")
        if jaeger_endpoint:
            jaeger_exporter = JaegerExporter(
                agent_host_name=jaeger_endpoint.split(":")[0],
                agent_port=int(jaeger_endpoint.split(":")[1])
                if ":" in jaeger_endpoint
                else 14268,
            )
            jaeger_processor = BatchSpanProcessor(jaeger_exporter)
            tracer_provider.add_span_processor(jaeger_processor)
            logger.info("tracing.jaeger_exporter_configured", endpoint=jaeger_endpoint)

    def instrument_fastapi(self, app: Any) -> None:
        """Instrument FastAPI application for tracing."""
        if not self._tracer or self._instrumented:
            return

        try:
            FastAPIInstrumentor.instrument_app(app)
            self._instrumented = True
            logger.info("tracing.fastapi_instrumented", service=self.service_name)
        except Exception as exc:
            logger.error(
                "tracing.fastapi_instrumentation_failed",
                service=self.service_name,
                error=str(exc),
            )

    def instrument_http_clients(self) -> None:
        """Instrument HTTP clients for tracing."""
        if self._instrumented:
            return

        try:
            HTTPXClientInstrumentor().instrument()
            RequestsInstrumentor().instrument()
            self._instrumented = True
            logger.info("tracing.http_clients_instrumented", service=self.service_name)
        except Exception as exc:
            logger.error(
                "tracing.http_instrumentation_failed",
                service=self.service_name,
                error=str(exc),
            )

    def get_tracer(self) -> trace.Tracer | None:
        """Get the configured tracer."""
        return self._tracer

    def create_span(self, name: str, **kwargs: Any) -> Any:
        """Create a new span with the service tracer."""
        if not self._tracer:
            return trace.NoOpTracer().start_span(name)
        return self._tracer.start_span(name, **kwargs)


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing."""
    return str(uuid.uuid4())


def get_correlation_id_from_context() -> str | None:
    """Extract correlation ID from OpenTelemetry context."""
    span = trace.get_current_span()
    if span and span.is_recording():
        return str(span.get_span_context().trace_id.hex)
    return None


def set_correlation_id_attribute(correlation_id: str) -> None:
    """Set correlation ID as a span attribute."""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.set_attribute("correlation_id", correlation_id)


def trace_audio_processing(operation_name: str) -> Any:
    """Decorator to trace audio processing operations."""

    def decorator(func: Any) -> Any:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get tracer from the first argument (usually self)
            tracer = None
            if args and hasattr(args[0], "_tracing_manager"):
                tracer = args[0]._tracing_manager.get_tracer()

            if not tracer:
                return func(*args, **kwargs)

            with tracer.start_as_current_span(operation_name) as span:
                span.set_attribute("operation", operation_name)
                span.set_attribute(
                    "service", getattr(args[0], "service_name", "unknown")
                )

                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("status", "success")
                    return result
                except Exception as exc:
                    span.set_attribute("status", "error")
                    span.set_attribute("error.message", str(exc))
                    span.set_attribute("error.type", type(exc).__name__)
                    raise

        return wrapper

    return decorator


def trace_service_call(service_name: str, operation: str) -> Any:
    """Decorator to trace cross-service calls."""

    def decorator(func: Any) -> Any:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = trace.get_tracer(__name__)

            with tracer.start_as_current_span(f"{service_name}.{operation}") as span:
                span.set_attribute("service.name", service_name)
                span.set_attribute("service.operation", operation)
                span.set_attribute("span.kind", "client")

                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("status", "success")
                    return result
                except Exception as exc:
                    span.set_attribute("status", "error")
                    span.set_attribute("error.message", str(exc))
                    span.set_attribute("error.type", type(exc).__name__)
                    raise

        return wrapper

    return decorator


# Global tracing manager instances
_tracing_managers: dict[str, TracingManager] = {}


def get_tracing_manager(
    service_name: str, service_version: str = "1.0.0"
) -> TracingManager:
    """Get or create a tracing manager for a service."""
    if service_name not in _tracing_managers:
        _tracing_managers[service_name] = TracingManager(service_name, service_version)
    return _tracing_managers[service_name]


def setup_service_tracing(
    service_name: str, service_version: str = "1.0.0"
) -> TracingManager:
    """Set up tracing for a service and return the manager."""
    manager = get_tracing_manager(service_name, service_version)
    manager.setup_tracing()
    manager.instrument_http_clients()
    return manager
