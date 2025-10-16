---
title: Runtime Quickstart
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-16
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Getting Started ▸ Runtime Quickstart

# Runtime Quickstart

Launch the full Discord Voice Lab stack via Docker Compose.

## Build & Run

```bash
make run
```

- Builds service images (Discord, STT, LLM, TTS) if they are not cached.
- Starts containers with environment files from `.env.common`, `.env.docker`, and `services/**/.env.service`.
- Streams logs to stdout; use `Ctrl+C` to exit or `make stop` from a separate shell.

## Monitoring

- `make logs` — Tail all services.
- `make logs SERVICE=discord` — Focus on the Discord bot; useful for wake phrase debugging.
- `make logs SERVICE=stt` — Inspect faster-whisper initialization and transcription speed.
- `make logs SERVICE=llm` — Review LLM service reasoning and API requests.
- `make logs SERVICE=orchestrator` — Review orchestrator coordination and MCP tool calls.
- `make logs SERVICE=tts` — Validate synthesis timing and concurrency.

## Shutdown & Cleanup

- `make stop` — Gracefully stop containers.
- `make docker-clean` — Remove containers, networks, and volumes when resetting the environment.

## Next Steps

Continue with [local development workflows](local-development.md) for linting and testing guidance or
jump to the [operations runbook](../operations/runbooks/discord-voice.md) for production routines.
