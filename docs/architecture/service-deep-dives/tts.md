---
title: TTS Service Deep Dive
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-18
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Architecture ▸ Service Deep Dives ▸ TTS Service

# Text-to-Speech Service

The TTS service streams Piper-generated audio in response to orchestrator requests.

## Responsibilities

-  Expose `/synthesize` for streaming WAV responses to orchestrator calls.
-  Manage Piper model loading, concurrency limits, and SSML parameterization.
-  Provide `/voices`, `/health`, and `/metrics` endpoints for discovery and monitoring.
-  Enforce bearer authentication and per-minute rate limits to protect resources.

## API Surface

-  `POST /synthesize` — Main synthesis endpoint for text-to-speech conversion.
-  `GET /voices` — List available voice options.
-  `GET /health/live` — Liveness check for container health.
-  `GET /health/ready` — Readiness check for service availability.
-  `GET /metrics` — Prometheus metrics when enabled.

## Configuration Highlights

-  `TTS_MODEL_PATH`, `TTS_MODEL_CONFIG_PATH` — Primary Piper assets.
-  `TTS_DEFAULT_VOICE`, `TTS_LENGTH_SCALE`, `TTS_NOISE_SCALE`, `TTS_NOISE_W` — Voice tuning.
-  `TTS_MAX_CONCURRENCY`, `TTS_RATE_LIMIT_PER_MINUTE` — Throughput controls.
-  `TTS_AUTH_TOKEN` — Bearer token required by orchestrator calls.

## Observability

-  Structured logs capture synthesis duration, payload size, and voice selection.
-  `/metrics` exposes request counters, latencies, and queue depth when enabled.
-  Use `make logs SERVICE=tts` while replaying orchestrator prompts to validate timing.

## Dependencies

-  Receives requests from the orchestrator and streams audio URLs back to the Discord bot.
-  Requires Piper model files available inside the container image or mounted volume.
