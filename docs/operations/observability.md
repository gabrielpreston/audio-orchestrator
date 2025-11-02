---
title: Solo Observability Guide
author: Discord Voice Lab Team
status: active
last-updated: 2025-01-27
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Operations ▸ Solo Observability

# Solo Observability

This guide documents simplified logging and health check expectations for solo development.

## Logging

-  All Python services use `services.common.logging` to emit JSON-formatted logs.
-  Configure verbosity with `LOG_LEVEL` (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` - case-insensitive, accepts lowercase) in `.env.common`.
-  Toggle JSON output via `LOG_JSON`; switch to plain text when debugging locally.
-  Use `make logs SERVICE=<name>` to stream per-service output and correlate events across the stack.

## Simple Metrics (Optional)

-  Basic health checks are sufficient for solo development
-  No complex Prometheus metrics required
-  Focus on "does it work" over comprehensive monitoring

## Memory Metrics

All production services automatically export memory usage metrics using OpenTelemetry ObservableGauge pattern:

-  **Process Memory Usage**: Real-time memory usage in bytes (RSS - Resident Set Size)
-  **Memory Limits**: Docker container memory limits (when available, from cgroup)
-  **Memory Percentage**: Memory usage as percentage of limit (when limit available)

### Metrics Exported

-  `audio_orchestrator_process_memory_usage_bytes` - Current memory usage in bytes
-  `audio_orchestrator_process_memory_limit_bytes` - Memory limit in bytes (only if limit detected)
-  `audio_orchestrator_process_memory_usage_percent` - Memory usage as percentage (only if limit available)

### Implementation Details

-  **Pattern**: Uses ObservableGauge callbacks (pull-based, no background tasks)
-  **Collection Interval**: Metrics collected every 15 seconds via PeriodicExportingMetricReader
-  **Cgroup Detection**: Automatically detects Docker memory limits from cgroup v1/v2 files
-  **Graceful Fallback**: Metrics continue to work even if cgroup files unavailable (non-Docker environments)
-  **Service Labels**: All metrics include `service` label matching service name

### Grafana Dashboard

Memory metrics are visualized in the **"Service Memory Usage"** dashboard:

-  **Time Series**: Memory usage over time for all services
-  **Table**: Current memory usage with bytes, MB, limits, and percentage
-  **Bar Gauge**: Visual representation of current memory usage per service
-  **Comparison**: Memory usage vs limits (when limits available)
-  **Service Filter**: Dropdown to filter by specific service

Access via: Grafana → Dashboards → "Service Memory Usage"

### Service Integration

Memory metrics are automatically available for all production services:

-  orchestrator
-  stt
-  bark
-  flan
-  audio
-  discord
-  guardrails

No additional configuration required - metrics are initialized during service startup alongside other metrics.

### Technical Notes

-  Uses `psutil` library for process memory information
-  Memory limits read from cgroup files (`/sys/fs/cgroup/memory.max` or `/sys/fs/cgroup/memory/memory.limit_in_bytes`)
-  ObservableGauge callbacks are registered at creation time and persist independently
-  Metrics flow: Service → OpenTelemetry → Collector → Prometheus → Grafana

## Standardized Health Checks

All services now use the common health endpoints module for consistent health check implementation:

-  **GET /health/live**: Always returns 200 if process is alive
-  **GET /health/ready**: Returns detailed readiness status with component information
-  **GET /health/dependencies**: Returns dependency health status

### Common Health Check Implementation

```python
from services.common.health_endpoints import HealthEndpoints
from services.common.health import HealthManager

# Initialize health manager
_health_manager = HealthManager("service_name")

# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="service_name",
    health_manager=_health_manager,
    custom_components={
        "component_name": lambda: component_value,
        "another_component": lambda: another_value,
    },
    custom_dependencies={
        "dependency_name": dependency_check_function,
    }
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())
```

### Standardized Response Formats

All services return consistent health check responses:

#### `/health/live` Response

```json
{
    "status": "alive",
    "service": "service_name"
}
```

#### `/health/ready` Response

```json
{
    "status": "ready|degraded|not_ready",
    "service": "service_name",
    "components": {
        "startup_complete": true,
        "component_name": true,
        "another_component": false
    },
    "dependencies": {
        "dependency_name": {
            "status": "healthy|unhealthy|error",
            "available": true
        }
    },
    "health_details": {
        "startup_complete": true,
        "dependencies": {}
    }
}
```

### Basic Health Check Requirements

-  **Startup Management**: Track if service has completed initialization
-  **Basic Endpoints**: Implement `/health/live` and `/health/ready`
-  **Simple Status**: Return basic status information
-  **No Complex Metrics**: Keep it simple for solo development

## Unified Observability Middleware

All services now use a unified `ObservabilityMiddleware` that provides:

-  **Automatic Correlation ID Propagation**: Correlation IDs are automatically extracted from incoming requests or generated if missing
-  **Request/Response Logging**: All HTTP requests are automatically logged with method, path, status code, and duration
-  **Timing Metrics**: Request duration is measured and included in logs
-  **Health Check Filtering**: Health check endpoints (`/health/live`, `/health/ready`, `/metrics`) are excluded from verbose logging

### Correlation ID Flow

Correlation IDs automatically propagate through the entire request chain:

1.  **Incoming Request**: Middleware extracts `X-Correlation-ID` header or generates a UUID
2.  **Context Storage**: Correlation ID is stored in async context using `contextvars`
3.  **Automatic Logging**: All loggers automatically include the correlation ID (via `get_logger()`)
4.  **HTTP Client Propagation**: All HTTP clients automatically inject the correlation ID into outgoing requests
5.  **Response Headers**: Correlation ID is included in response headers for client tracing

### Request/Response Logging

The middleware automatically logs:

-  **Request Start**: `http.request.start` event with method, path, correlation_id
-  **Request Complete**: `http.request.complete` event with status_code, duration_ms, correlation_id
-  **Request Error**: `http.request.error` event with error details and timing

Example log entries:

```json
{
  "event": "http.request.start",
  "method": "POST",
  "path": "/api/v1/transcripts",
  "correlation_id": "abc123-def456-ghi789"
}
```

```json
{
  "event": "http.request.complete",
  "method": "POST",
  "path": "/api/v1/transcripts",
  "status_code": 200,
  "duration_ms": 45.23,
  "correlation_id": "abc123-def456-ghi789"
}
```

## Service Factory Pattern

All services now use the `create_service_app()` factory function for standardized FastAPI app creation:

```python
from services.common.app_factory import create_service_app
from services.common.tracing import get_observability_manager

async def _startup():
    # Observability is already setup by factory
    _observability_manager = get_observability_manager("service_name")

    # Create service-specific metrics
    _metrics = create_service_metrics(_observability_manager)

    # Set in health manager
    _health_manager.set_observability_manager(_observability_manager)

    # Service-specific initialization
    _health_manager.mark_startup_complete()

app = create_service_app(
    "service_name",
    "1.0.0",
    title="Service Title",
    startup_callback=_startup,
    shutdown_callback=_shutdown,
)
```

### Factory Benefits

-  **Automatic Observability Setup**: OpenTelemetry instrumentation configured before app starts
-  **Automatic Middleware**: `ObservabilityMiddleware` automatically registered
-  **Standardized Lifespan**: Consistent startup/shutdown pattern across all services
-  **No Boilerplate**: Eliminates repetitive observability setup code

### Accessing Observability Manager

Services access the observability manager using `get_observability_manager()`:

```python
from services.common.tracing import get_observability_manager

# Get the manager (created by factory during startup)
observability_manager = get_observability_manager("service_name")

# Create service-specific metrics
metrics = create_service_metrics(observability_manager)

# Set in health manager
health_manager.set_observability_manager(observability_manager)
```

## Exception Logging

Exception logging verbosity is configurable:

-  **Production (INFO+)**: Summary format (5-10 lines) using `format_exc_info` processor
-  **Debug (DEBUG)**: Full tracebacks (50-100+ lines) using `dict_tracebacks` processor

### Configuration

Configure exception logging via environment variable:

```bash
LOG_FULL_TRACEBACKS=true   # Force full tracebacks
LOG_FULL_TRACEBACKS=false  # Force summary format
# Omit variable for automatic level-based selection (full in DEBUG, summary in INFO+)
```

## Solo Development Summary

### Simplified Approach

-  **Basic functionality**: Service can handle requests
-  **Simple implementation**: No complex metrics or extensive dependency checking
-  **Solo development**: Optimized for rapid iteration and manual testing
-  **Essential coverage**: Critical paths covered without over-engineering
