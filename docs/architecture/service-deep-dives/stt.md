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
-  `FW_COMPUTE_TYPE` — Precision trade-off (`int8` for CPU, `float16` for CUDA/GPU). Note: `float16` is not supported on CPU and will be automatically corrected to `int8`.
-  Shared logging controlled via `.env.common`.

## Observability

-  **Unified Middleware**: Uses `ObservabilityMiddleware` for automatic correlation ID propagation and request/response logging
-  **Service Factory**: Uses `create_service_app()` factory for standardized observability setup
-  **Correlation IDs**: Automatically extracted from incoming requests and propagated to downstream services
-  Structured logs capture transcription duration and detected language codes.
-  Use `make logs SERVICE=stt` to confirm model warmup and request throughput.
-  Monitor `/metrics` for latency histograms if Prometheus scraping is enabled.

## Audio Processing

The STT service processes incoming WAV audio using temporary files with automatic cleanup:

-  **In-Memory Buffer Approach**: Incoming WAV bytes are written to temporary files using `NamedTemporaryFile` with automatic deletion (`delete=True`)
-  **Automatic Cleanup**: Files are automatically deleted when the context manager exits, even on exceptions, eliminating manual cleanup code
-  **Optimized I/O**: File size is calculated from the input buffer rather than filesystem stat calls for improved performance
-  **Model Compatibility**: faster-whisper requires file paths (not file-like objects), so temporary files are necessary but cleaned up efficiently

## Dependencies

-  Receives audio from `services/discord` and returns transcripts to `services/orchestrator` via the bot.
-  Requires the faster-whisper model files bundled in the Docker image or mounted volume.
