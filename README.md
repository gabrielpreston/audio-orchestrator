# Discord Voice Lab — Quickstart

This repository provides a Python-based Discord voice agent alongside supporting services for speech-to-text (STT) and lightweight orchestration. The Python bot handles audio capture, wake-word filtering, transcription requests, and exposes Discord control tools over the Model Context Protocol (MCP).

## Prerequisites

- make
- Python 3.10+
- Docker (optional, for containerized STT/LLM services)
- A Discord bot token

## Environment files (recommended)

The stack now separates shared defaults from service-specific configuration:

- `.env.common` — logging defaults applied across every Python process.
- `services/discord/.env.service` — Discord bot credentials and audio/STT tuning.
- `services/stt/.env.service` — faster-whisper model selection.
- `services/llm/.env.service` — llama.cpp runtime configuration and auth.
- `.env.docker` — Docker-only overrides such as UID/GID ownership.
- `.env.local` (optional) — local overrides loaded by `make dev-*`.

Copy the relevant blocks from `.env.sample` into each file before running locally or via Docker Compose.

## Quickstart — Python voice bot

Before you start the bot, update `services/discord/.env.service` with your Discord credentials and point `STT_BASE_URL` at a running transcription service. Adjust the llama and STT service files as needed for your environment.

1. Install dependencies (ideally inside a virtual environment):

   ```bash
   python -m venv .venv
   . .venv/bin/activate
   pip install -r services/discord/requirements.txt
   ```

2. Source environment variables (or rely on `.env.local`) and run the bot:

   ```bash
   make dev-discord
   ```

   The bot exposes itself as an MCP server over stdio, coordinates with the faster-whisper STT service, performs wake-word filtering, and streams transcript notifications plus Discord control tools (join, leave, play audio, send message) to downstream orchestrators.

## Structured logging

All Python services share the `services.common.logging` helpers to emit JSON logs to stdout by default. Configure verbosity with `LOG_LEVEL` (e.g., `DEBUG`, `INFO`) and toggle JSON output via `LOG_JSON`. Docker Compose surfaces these logs through `docker compose logs`, making it easy to aggregate or ship them to your preferred observability stack.

## Quickstart — Docker Compose services

Populate each `services/**/.env.service` file (see `.env.sample`) with production-ready values, then adjust `.env.docker` if you need custom UID/GID ownership for mounted volumes. When everything is in place, build and run the stack:

```bash
make run
```

This brings up the Discord bot, STT, and orchestrator containers defined in `docker-compose.yml`. Use `make logs` to follow their output and `make stop` to tear them down. The bot container reads the same environment variables as the local `make dev-discord` workflow.

## Where to look next

- `services/discord/` — Python Discord interface packages (audio pipeline, wake detection, transcription client, MCP server, Discord client wiring).
- `services/stt/` — FastAPI-based STT service using faster-whisper.
- `services/llm/` — lightweight orchestrator service exposing OpenAI-compatible APIs.
- `docs/` — architecture and development guides shared between runtimes.

That's all you need to get started. Update environment defaults and documentation in tandem with any behavior changes to keep the project consistent.
