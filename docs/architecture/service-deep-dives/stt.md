---
title: STT Service Deep Dive
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-18
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Architecture ▸ Service Deep Dives ▸ STT Service

# Speech-to-Text Service

The STT service exposes an HTTP transcription API optimized for low-latency streaming workloads.

## Responsibilities

-  Accept audio payloads from the Discord bot and return text transcripts.
-  Manage faster-whisper model loading, device selection, and compute parameters.
-  Provide health and readiness endpoints for Compose orchestrations.
-  Emit structured logs summarizing transcription performance.

## API Surface

-  `POST /asr` — Main transcription route used by the Discord service.
-  `POST /transcribe` — Alternative transcription endpoint.
-  `GET /health/live` — Liveness check used by Docker Compose and external monitors.
-  `GET /health/ready` — Readiness check for service availability.

## Configuration Highlights

-  `FW_MODEL` — faster-whisper model name (e.g., `medium.en`).
-  `FW_DEVICE` — Execution target (`cpu`, `cuda`).
-  `FW_COMPUTE_TYPE` — Precision trade-off (`int8`, `float16`, etc.).
-  Shared logging controlled via `.env.common`.

## Observability

-  Structured logs capture transcription duration and detected language codes.
-  Use `make logs SERVICE=stt` to confirm model warmup and request throughput.
-  Monitor `/metrics` for latency histograms if Prometheus scraping is enabled.

## Dependencies

-  Receives audio from `services/discord` and returns transcripts to `services/orchestrator` via the bot.
-  Requires the faster-whisper model files bundled in the Docker image or mounted volume.
