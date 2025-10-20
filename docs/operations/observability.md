---
title: Observability Guide
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-20
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Operations ▸ Observability

# Observability

This guide documents logging, metrics, and tracing expectations for the voice lab services.

## Logging

- All Python services use `services.common.logging` to emit JSON-formatted logs.
- Configure verbosity with `LOG_LEVEL` (`debug`, `info`, `warning`) in `.env.common`.
- Toggle JSON output via `LOG_JSON`; switch to plain text when debugging locally.
- Use `make logs SERVICE=<name>` to stream per-service output and correlate events across the stack.

## Metrics

- STT, LLM, and TTS services expose `/metrics` endpoints compatible with Prometheus.
- Scrape latency histograms and request counters to detect regressions.
- Export metrics dashboards tracking wake-to-response latency, TTS queue depth, and MCP tool error rates.

## Health Checks

Each service exposes two health check endpoints following Kubernetes best practices:

- **GET /health/live**: Liveness probe - returns 200 if process is alive
- **GET /health/ready**: Readiness probe - returns 200 when service can handle requests
  - Returns 503 during startup or when critical dependencies unavailable
  - Includes detailed component status and dependency health

### Health Check Response Format

The `/health/ready` endpoint returns a structured response with component-level health status:

```json
{
  "status": "ready|degraded|not_ready",
  "service": "service-name",
  "components": {
    "component_name": true|false,
    "startup_complete": true|false
  },
  "dependencies": {
    "dependency_name": true|false
  },
  "health_details": {
    "startup_complete": true|false,
    "dependencies": {
      "dependency_name": true|false
    }
  }
}
```

### Status Values

- **ready**: Service is fully operational and all dependencies are healthy
- **degraded**: Service is operational but some dependencies are unhealthy
- **not_ready**: Service cannot serve requests (startup incomplete or critical failures)

### Component-Level Health Status

Each service reports detailed component status:

- **STT**: `model_loaded`, `model_name`, `startup_complete`
- **TTS**: `voice_loaded`, `sample_rate`, `max_concurrency`, `startup_complete`
- **LLM**: `llm_loaded`, `tts_available`, `startup_complete`
- **Orchestrator**: `orchestrator_active`, `llm_available`, `tts_available`, `mcp_clients`, `startup_complete`
- **Discord**: `bot_connected`, `mode`, `startup_complete`

### Dependency Health Tracking

Services register and monitor their critical dependencies:

- **LLM**: Monitors TTS service (optional)
- **Orchestrator**: Monitors LLM and TTS services
- **Discord**: Monitors STT and Orchestrator services

### Status Transitions

- **Healthy → Degraded**: Occurs when a non-critical dependency becomes unhealthy
- **Degraded → Unhealthy**: Occurs when a critical dependency becomes unhealthy
- **Unhealthy → Healthy**: Occurs when all dependencies become healthy

### Circuit Breakers

Circuit breaker functionality is implemented in `services.common.circuit_breaker` to protect against cascading failures.

**Features**:

- Opens after configurable consecutive failures (default: 5)
- Remains open for configurable timeout with exponential backoff (default: 30s)
- Half-opens to test recovery after timeout
- Closes after configurable consecutive successes (default: 2)

**Configuration**:

Circuit breakers are configured programmatically using `CircuitBreakerConfig`:

```python
from services.common.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

config = CircuitBreakerConfig(
    failure_threshold=5,
    success_threshold=2,
    timeout_seconds=30.0,
    max_timeout_seconds=300.0
)

breaker = CircuitBreaker("service_name", config)
```

**Usage**:

## Prometheus Metrics

All services expose health check metrics via `/metrics` endpoints for monitoring and alerting.

### Health Check Metrics

The following metrics are automatically exposed by all services:

#### health_check_duration_seconds

- **Type**: Histogram
- **Description**: Health check execution duration
- **Labels**: `service`, `check_type`
- **Buckets**: Default Prometheus buckets

#### service_health_status

- **Type**: Gauge
- **Description**: Current service health status
- **Labels**: `service`, `component`
- **Values**: 1=healthy, 0.5=degraded, 0=unhealthy

#### service_dependency_health

- **Type**: Gauge
- **Description**: Dependency health status
- **Labels**: `service`, `dependency`
- **Values**: 1=healthy, 0=unhealthy

### Example Metrics Queries

```promql
# Service health status
service_health_status{component="overall"}

# Dependency health
service_dependency_health

# Health check duration
histogram_quantile(0.95, health_check_duration_seconds_bucket)

# Service availability
avg_over_time(service_health_status{component="overall"}[5m])
```

### Alerting Rules

```yaml
# Alert when service becomes degraded
- alert: ServiceDegraded
  expr: service_health_status{component="overall"} < 1
  for: 1m
  labels:
    severity: warning
  annotations:
    summary: "Service {{ $labels.service }} is degraded"

# Alert when dependency becomes unhealthy
- alert: DependencyUnhealthy
  expr: service_dependency_health < 1
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Dependency {{ $labels.dependency }} is unhealthy for service {{ $labels.service }}"
```

### Dashboard Queries

```promql
# Service health overview
service_health_status{component="overall"}

# Dependency health matrix
service_dependency_health

# Health check performance
histogram_quantile(0.95, health_check_duration_seconds_bucket)

# Service availability over time
avg_over_time(service_health_status{component="overall"}[5m])
```

Services can use circuit breakers to protect external service calls:

```python
if breaker.is_available():
    try:
        result = await external_service.call()
        breaker.record_success()
    except Exception as e:
        breaker.record_failure()
        raise
```

## Tracing & Correlation

- All services use the unified correlation ID system (`services.common.correlation`) for end-to-end tracing.
- Correlation IDs are automatically generated and propagated through the voice pipeline.
- Use `make logs SERVICE=<name>` to follow specific correlation IDs across services.
- Include MCP tool names and request IDs in logs to track automation paths end-to-end.
- Capture incident-specific traces in the [reports](../reports/README.md) section for retrospective analysis.
