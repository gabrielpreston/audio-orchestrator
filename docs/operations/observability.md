---
title: Observability Guide
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-18
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
  - Includes service-specific readiness details

### Readiness Criteria by Service

- **STT**: Model loaded and initialized
- **LLM**: Model loaded (if applicable)
- **TTS**: Voice model loaded
- **Orchestrator**: MCP clients initialized
- **Discord**: Bot connected to Discord gateway

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
