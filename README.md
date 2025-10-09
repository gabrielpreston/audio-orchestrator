# Discord Voice Lab — Quickstart

This repository provides a Python-based Discord voice agent alongside supporting services for speech-to-text (STT) and lightweight orchestration. The Python bot handles audio capture, wake-word filtering, transcription requests, and exposes Discord control tools over the Model Context Protocol (MCP).

## Prerequisites

- make
- Docker and `docker-compose`
- A Discord bot token

## Environment files (recommended)

The stack now separates shared defaults from service-specific configuration:

- `.env.common` — logging defaults applied across every Python process.
- `services/discord/.env.service` — Discord bot credentials and audio/STT tuning.
- `services/stt/.env.service` — faster-whisper model selection.
- `services/llm/.env.service` — llama.cpp runtime configuration and auth.
- `.env.docker` — Docker-only overrides such as UID/GID ownership.
- Copy the relevant blocks from `.env.sample` into each file before running the stack.

## Structured logging

All Python services share the `services.common.logging` helpers to emit JSON logs to stdout by default. Configure verbosity with `LOG_LEVEL` (e.g., `DEBUG`, `INFO`) and toggle JSON output via `LOG_JSON`. Docker Compose surfaces these logs through `docker-compose logs`, making it easy to aggregate or ship them to your preferred observability stack.

## Voice connection tuning

The Discord bot now retries voice handshakes automatically if the gateway or media edge takes too long
to respond. Adjust retry behavior with `DISCORD_VOICE_CONNECT_TIMEOUT`, `DISCORD_VOICE_CONNECT_ATTEMPTS`,
`DISCORD_VOICE_RECONNECT_BASE_DELAY`, and `DISCORD_VOICE_RECONNECT_MAX_DELAY` in
`services/discord/.env.service`.

## Wake phrase detection

Wake phrase matching now tolerates extra punctuation or spacing in STT transcripts, and ignored
segments log a short `transcript_preview` so you can inspect what was heard without cranking global
log levels.

## Quickstart — Docker Compose services

Populate each `services/**/.env.service` file (see `.env.sample`) with production-ready values, then adjust `.env.docker` if you need custom UID/GID ownership for mounted volumes. When everything is in place, build and run the stack:

```bash
make run
```

This brings up the Discord bot, STT, and orchestrator containers defined in `docker-compose.yml`. Use `make logs` to follow their output and `make stop` to tear them down.

## Where to look next

- `services/discord/` — Python Discord interface packages (audio pipeline, wake detection, transcription client, MCP server, Discord client wiring).
- `services/stt/` — FastAPI-based STT service using faster-whisper.
- `services/llm/` — lightweight orchestrator service exposing OpenAI-compatible APIs.
- `docs/` — architecture and development guides shared between runtimes.

That's all you need to get started. Update environment defaults and documentation in tandem with any behavior changes to keep the project consistent.
