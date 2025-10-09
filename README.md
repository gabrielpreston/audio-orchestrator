# Discord Voice Lab — Quickstart

This repository provides a Python-based Discord voice agent alongside supporting services for speech-to-text (STT) and lightweight orchestration. The Python bot handles audio capture, wake-word filtering, transcription requests, and exposes Discord control tools over the Model Context Protocol (MCP).

## Prerequisites

- make
- Python 3.10+
- Docker (optional, for containerized STT/LLM services)
- A Discord bot token

## Environment files (recommended)

Use environment files to avoid exporting variables manually:

- `.env.local` — sourced by local development targets such as `make dev-discord` and `make dev-stt`.
- `.env.docker` — consumed by Docker Compose services.

Copy `.env.sample` to either location and update the placeholders before running the bot.

## Essential environment variables (examples)

```env
# .env.local or .env.docker
DISCORD_BOT_TOKEN=your_token_here
DISCORD_GUILD_ID=123456789012345678
DISCORD_VOICE_CHANNEL_ID=987654321098765432
DISCORD_AUTO_JOIN=true
STT_BASE_URL=http://localhost:9000
WAKE_PHRASES=hey atlas,ok atlas
AUDIO_ALLOWLIST=12345,67890
LOG_LEVEL=INFO
LOG_JSON=true
```

## Quickstart — Python voice bot

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

Create `.env.docker` in the repository root (see example above). Populate it with the Discord credentials (`DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `DISCORD_VOICE_CHANNEL_ID`) alongside the STT settings before starting the stack. Then build and run the services:

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
