---
title: Observability Guide
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-16
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

HTTP clients use per-service circuit breakers to prevent cascading failures:

- Opens after 5 consecutive failures (configurable)
- Remains open for 30 seconds with exponential backoff
- Half-opens to test recovery after timeout
- Closes after 2 consecutive successes

### Service Resilience Configuration

Add these environment variables to `.env.common` for resilience tuning:

```bash
# Service Resilience Configuration
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_SUCCESS_THRESHOLD=2
CIRCUIT_BREAKER_TIMEOUT_SECONDS=30
SERVICE_STARTUP_TIMEOUT_SECONDS=300
HEALTH_CHECK_INTERVAL_SECONDS=10
```

## Tracing & Correlation

- All services use the unified correlation ID system (`services.common.correlation`) for end-to-end tracing.
- Correlation IDs are automatically generated and propagated through the voice pipeline.
- Use `make logs SERVICE=<name>` to follow specific correlation IDs across services.
- Include MCP tool names and request IDs in logs to track automation paths end-to-end.
- Capture incident-specific traces in the [reports](../reports/README.md) section for retrospective analysis.
