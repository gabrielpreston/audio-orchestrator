---
title: LLM Service Deep Dive
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-18
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Architecture ▸ Service Deep Dives ▸ LLM Service

# LLM Service

The LLM service provides OpenAI-compatible completions and reasoning capabilities for the orchestrator service.

## Responsibilities

- Provide OpenAI-compatible API endpoints for chat completions and text generation.
- Execute llama.cpp inference for local reasoning tasks.
- Handle authentication and request validation.
- Expose health and metrics endpoints for monitoring.

## API Surface

- `POST /v1/chat/completions` — Primary route used by the orchestrator service.
- `GET /health/live` — Liveness check for container health.
- `GET /health/ready` — Readiness check for service availability.

## Configuration Highlights

- `LLAMA_BIN`, `LLAMA_MODEL_PATH`, `LLAMA_CTX`, `LLAMA_THREADS` — llama.cpp runtime controls.
- `LLM_AUTH_TOKEN` — Bearer token required for incoming requests.
- `TTS_BASE_URL`, `TTS_TIMEOUT`, `TTS_VOICE` — Downstream TTS integration defaults.
- Logging inherits from `.env.common`.

## Observability

- Structured logs track request IDs, model inference times, and response generation.
- `/metrics` exposes request counters and duration histograms when scraped.
- Use `make logs SERVICE=llm` to monitor llama.cpp output and API request handling.

## Dependencies

- Receives reasoning requests from the orchestrator service.
- Requires llama.cpp model files available in the container or mounted volume.
- May call TTS service for spoken responses when configured.
