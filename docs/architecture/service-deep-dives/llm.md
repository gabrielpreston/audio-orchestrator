---
title: Orchestrator Service Deep Dive
author: Discord Voice Lab Team
status: active
last-updated: 2024-07-05
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Architecture ▸ Service Deep Dives ▸ Orchestrator

# LLM Orchestrator Service

The orchestrator mediates between Discord transcripts, llama.cpp completions, and MCP tooling.

## Responsibilities

- Accept OpenAI-compatible chat/completions requests from the Discord bot.
- Invoke llama.cpp for local reasoning or route prompts to remote endpoints when configured.
- Coordinate MCP tool calls and merge their outputs into model responses.
- Provide bearer-authenticated APIs for downstream callers.

## API Surface

- `POST /v1/chat/completions` — Primary route used by the Discord service.
- `POST /v1/completions` — Compatibility endpoint for legacy clients.
- `GET /health` — Container health check.
- `GET /metrics` — Prometheus metrics when enabled.

## Configuration Highlights

- `LLAMA_BIN`, `LLAMA_MODEL_PATH`, `LLAMA_CTX`, `LLAMA_THREADS` — llama.cpp runtime controls.
- `ORCH_AUTH_TOKEN` — Bearer token required for incoming requests.
- `TTS_BASE_URL`, `TTS_TIMEOUT`, `TTS_VOICE` — Downstream TTS integration defaults.
- Logging inherits from `.env.common`.

## Observability

- Structured logs track request IDs, MCP tool invocations, and latency breakdowns.
- `/metrics` exposes request counters and duration histograms when scraped.
- Use `make logs SERVICE=llm` to monitor orchestrated tool chains and llama.cpp output.

## Dependencies

- Receives transcripts from the Discord bot and optional MCP tool manifests.
- Calls the TTS service to synthesize spoken responses.
- May depend on additional capability servers registered through MCP manifests.
