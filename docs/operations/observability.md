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

- Each service responds to `GET /health` with a readiness indicator.
- Configure Compose or external orchestrators to restart unhealthy containers automatically.

## Tracing & Correlation

- All services use the unified correlation ID system (`services.common.correlation`) for end-to-end tracing.
- Correlation IDs are automatically generated and propagated through the voice pipeline.
- Use `make logs SERVICE=<name>` to follow specific correlation IDs across services.
- Include MCP tool names and request IDs in logs to track automation paths end-to-end.
- Capture incident-specific traces in the [reports](../reports/README.md) section for retrospective analysis.

