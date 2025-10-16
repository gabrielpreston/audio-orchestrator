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

## Debug Management

The system includes comprehensive debug capabilities for troubleshooting and analysis:

- **Debug Data Collection**: Enable with service-specific `*_DEBUG_SAVE=true` environment variables.
- **Hierarchical Storage**: Debug files organized by date (`debug/YYYY/MM/DD/correlation_id/`).
- **Consolidated Logs**: Single `debug_log.json` per correlation ID for complete pipeline visibility.
- **Audio Preservation**: Separate WAV files for playback and analysis.
- **Maintenance Tools**: Use `scripts/debug_manager.py` for storage management and cleanup.

### Debug Service Variables

- `DISCORD_DEBUG_SAVE=true` — Save voice segments, wake detection, and MCP calls
- `STT_DEBUG_SAVE=true` — Save input audio, transcription results, and metadata
- `TTS_DEBUG_SAVE=true` — Save synthesis requests, generated audio, and parameters
- `ORCHESTRATOR_DEBUG_SAVE=true` — Save LLM responses, MCP tool calls, and TTS integration

### Debug Management Commands

```bash
# Show debug statistics
python3 scripts/debug_manager.py --stats

# Archive data older than 30 days
python3 scripts/debug_manager.py --archive 30

# Remove empty directories
python3 scripts/debug_manager.py --cleanup
```
