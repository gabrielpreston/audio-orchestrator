"""OpenTelemetry distributed tracing for audio orchestrator services.

This module provides standardized tracing setup and utilities across all services
in the audio orchestrator platform.
"""

import inspect
import os
import uuid
from typing import Any

from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

from .structured_logging import get_logger

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
        self._fastapi_instrumented = False
        self._http_clients_instrumented = False

    def setup_tracing(self) -> None:
        """Set up OpenTelemetry tracing for the service."""
        if os.getenv("OTEL_ENABLED", "false").lower() != "true":
            logger.info("tracing.disabled", service=self.service_name)
            return

        try:
            # Get existing tracer provider or create new one
            current_provider = trace.get_tracer_provider()

            # Only set new provider if it's the default NoOpTracerProvider
            # (checking by type name to avoid importing NoOpTracerProvider)
            provider_created = False
            if type(current_provider).__name__ == "NoOpTracerProvider":
                # Create resource with service information
                resource = Resource.create(
                    {
                        "service.name": self.service_name,
                        "service.version": self.service_version,
                        "service.namespace": "audio-orchestrator",
                    }
                )
                # Set up tracer provider (only if not already set)
                trace.set_tracer_provider(TracerProvider(resource=resource))
                provider_created = True
                logger.info(
                    "tracing.tracer_provider_created", service=self.service_name
                )
            else:
                # Provider already exists, use it
                logger.debug(
                    "tracing.using_existing_provider", service=self.service_name
                )

            # Configure exporters based on environment
            # Pass provider_created flag so exporter setup knows if we can add processors
            self._setup_exporters(provider_created=provider_created)

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

    def _setup_exporters(self, *, provider_created: bool = False) -> None:
        """Set up trace exporters based on configuration.

        Args:
            provider_created: True if this service created the provider, False if using existing
        """
        tracer_provider = trace.get_tracer_provider()

        # OTLP exporter (for Jaeger, Zipkin, etc.)
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            # Ensure endpoint has http:// prefix for HTTP protocol
            if not otlp_endpoint.startswith(("http://", "https://")):
                otlp_endpoint = f"http://{otlp_endpoint}"
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            otlp_processor = BatchSpanProcessor(otlp_exporter)

            # Only add processor if:
            # 1. We created the provider (first service), OR
            # 2. Provider is SDK TracerProvider (not ProxyTracerProvider/NoOpTracerProvider)
            # ProxyTracerProvider wraps SDK provider for thread-safety but doesn't expose add_span_processor
            if provider_created or isinstance(tracer_provider, TracerProvider):
                try:
                    tracer_provider.add_span_processor(otlp_processor)
                    logger.info(
                        "tracing.otlp_exporter_configured", endpoint=otlp_endpoint
                    )
                except AttributeError:
                    # Provider doesn't support add_span_processor (ProxyTracerProvider)
                    logger.debug(
                        "tracing.provider_does_not_support_processors",
                        provider_type=type(tracer_provider).__name__,
                        service=self.service_name,
                    )
            else:
                # Provider is ProxyTracerProvider or NoOpTracerProvider - exporter will still work
                # via the proxy, but we can't add processors directly
                logger.debug(
                    "tracing.provider_is_proxy",
                    provider_type=type(tracer_provider).__name__,
                    service=self.service_name,
                )

        # Jaeger exporter removed due to gRPC compatibility issues

    def instrument_fastapi(self, app: Any) -> None:
        """Instrument FastAPI application for tracing."""
        if not self._tracer or self._fastapi_instrumented:
            return

        try:
            FastAPIInstrumentor.instrument_app(app)
            self._fastapi_instrumented = True
            logger.info("tracing.fastapi_instrumented", service=self.service_name)
        except Exception as exc:
            logger.error(
                "tracing.fastapi_instrumentation_failed",
                service=self.service_name,
                error=str(exc),
            )

    def instrument_http_clients(self) -> None:
        """Instrument HTTP clients for tracing."""
        if self._http_clients_instrumented:
            return

        try:
            HTTPXClientInstrumentor().instrument()
            RequestsInstrumentor().instrument()
            self._http_clients_instrumented = True
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

                    # Handle async functions
                    if inspect.iscoroutine(result):

                        async def async_wrapper() -> Any:
                            try:
                                result_value = await result
                                span.set_attribute("status", "success")
                                return result_value
                            except Exception as exc:
                                span.set_attribute("status", "error")
                                span.set_attribute("error.message", str(exc))
                                span.set_attribute("error.type", type(exc).__name__)
                                raise

                        return async_wrapper()
                    else:
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

                    # Handle async functions
                    if inspect.iscoroutine(result):

                        async def async_wrapper() -> Any:
                            try:
                                result_value = await result
                                span.set_attribute("status", "success")
                                return result_value
                            except Exception as exc:
                                span.set_attribute("status", "error")
                                span.set_attribute("error.message", str(exc))
                                span.set_attribute("error.type", type(exc).__name__)
                                raise

                        return async_wrapper()
                    else:
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


class ObservabilityManager(TracingManager):
    """Enhanced manager that handles both tracing and metrics."""

    def __init__(self, service_name: str, service_version: str = "1.0.0"):
        super().__init__(service_name, service_version)
        self._meter: metrics.Meter | None = None
        self._metrics_enabled = False

    def setup_observability(self) -> None:
        """Setup both tracing and metrics for the service."""
        # Setup tracing (existing functionality)
        self.setup_tracing()

        # Setup metrics (new functionality)
        self._setup_metrics()

    def _setup_metrics(self) -> None:
        """Set up OpenTelemetry metrics for the service."""
        if os.getenv("OTEL_ENABLED", "false").lower() != "true":
            logger.info("metrics.disabled", service=self.service_name)
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

            # Get existing meter provider or create new one
            current_meter_provider = metrics.get_meter_provider()

            # Only set new provider if it's the default NoOpMeterProvider
            # OpenTelemetry MeterProvider doesn't support adding readers after creation,
            # so only the first service creates the provider with a reader.
            # All services share the same provider and export metrics via the single reader.
            if type(current_meter_provider).__name__ == "NoOpMeterProvider":
                # Only create reader and provider for the first service
                # Setup OTLP metric exporter
                # Use same endpoint as traces (port 4318 for HTTP protocol)
                otlp_endpoint = os.getenv(
                    "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318"
                )
                # Use HTTP endpoint format for insecure connections
                # For HTTP protocol, use http:// instead of https:// for insecure
                if not otlp_endpoint.startswith(("http://", "https://")):
                    # If no protocol specified, default to HTTP on port 4318
                    if ":4317" in otlp_endpoint:
                        # Replace gRPC port with HTTP port
                        otlp_endpoint = otlp_endpoint.replace(":4317", ":4318")
                    otlp_endpoint = f"http://{otlp_endpoint}"
                metric_reader = PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=otlp_endpoint),
                    export_interval_millis=15000,
                )
                meter_provider = MeterProvider(
                    resource=resource, metric_readers=[metric_reader]
                )
                metrics.set_meter_provider(meter_provider)
                logger.info("metrics.meter_provider_created", service=self.service_name)
            else:
                # Meter provider already exists - all services share the same provider
                # Each service creates its own meter via get_meter(), and all metrics
                # are collected by the shared provider's reader(s)
                # DO NOT create a MetricReader here - it will trigger warnings because
                # PeriodicExportingMetricReader starts a background thread that calls collect()
                logger.debug(
                    "metrics.using_existing_provider", service=self.service_name
                )

            # Get meter
            self._meter = metrics.get_meter(self.service_name, self.service_version)
            self._metrics_enabled = True

            logger.info("metrics.initialized", service=self.service_name)

        except Exception as exc:
            logger.error(
                "metrics.setup_failed", service=self.service_name, error=str(exc)
            )
            self._meter = None

    def get_meter(self) -> metrics.Meter | None:
        """Get the configured meter."""
        return self._meter

    def create_counter(
        self, name: str, description: str, unit: str = "1"
    ) -> Any | None:
        """Create a counter metric."""
        if not self._meter:
            return None
        return self._meter.create_counter(name, unit=unit, description=description)

    def create_histogram(
        self, name: str, description: str, unit: str = "1"
    ) -> Any | None:
        """Create a histogram metric."""
        if not self._meter:
            return None
        return self._meter.create_histogram(name, unit=unit, description=description)

    def create_up_down_counter(
        self, name: str, description: str, unit: str = "1"
    ) -> Any | None:
        """Create an up-down counter (gauge) metric."""
        if not self._meter:
            return None
        return self._meter.create_up_down_counter(
            name, unit=unit, description=description
        )


# Global observability manager instances
_observability_managers: dict[str, ObservabilityManager] = {}


def get_observability_manager(
    service_name: str, service_version: str = "1.0.0"
) -> ObservabilityManager:
    """Get or create an observability manager for a service."""
    if service_name not in _observability_managers:
        _observability_managers[service_name] = ObservabilityManager(
            service_name, service_version
        )
    return _observability_managers[service_name]


def setup_service_observability(
    service_name: str, service_version: str = "1.0.0"
) -> ObservabilityManager:
    """Set up observability for a service and return the manager."""
    manager = get_observability_manager(service_name, service_version)
    manager.setup_observability()
    manager.instrument_http_clients()
    return manager
