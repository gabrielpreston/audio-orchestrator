# Discord Voice Lab — Quickstart

This repository now contains both the original Go-based Discord voice gateway and a new Python implementation that mirrors the same audio → wake-word → STT → orchestration loop. This README highlights the fastest path to run and test the Python bot.

Prerequisites

- make
- Docker (optional, for image build/run)
- A Discord bot token (required)

Environment files (recommended)

This project supports loading environment variables from files instead of manual "export" commands. Use:

- `.env.local` — for local development (used by `make dev-bot` / `make dev-stt` which source this file when present)
- `.env.docker` — for containers (referenced by `docker-compose.yml` via the `env_file` field)

Essential environment variables (examples)

Create a `.env.local` for local runs or `.env.docker` for docker runs. Example contents for the Python bot:

```env
# .env.local or .env.docker
DISCORD_BOT_TOKEN=your_token_here
DISCORD_GUILD_ID=123456789012345678
DISCORD_VOICE_CHANNEL_ID=987654321098765432
DISCORD_AUTO_JOIN=true
STT_BASE_URL=http://localhost:9000
ORCHESTRATOR_BASE_URL=http://localhost:9100
ORCHESTRATOR_WAKE_PHRASES=hey atlas,ok atlas
AUDIO_ALLOWLIST=12345,67890
LOG_LEVEL=info
LOG_JSON=true
```

Quickstart — Python voice bot

1. Install dependencies (ideally inside a virtualenv):

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r services/pybot/requirements.txt
```

2. Export environment variables (or rely on `.env.local` sourced beforehand) and run the bot:

```bash
python -m services.pybot.main
```

The Python bot automatically loads manifests declared via `MCP_MANIFESTS`, coordinates with the faster-whisper STT service, performs wake-word filtering before invoking the orchestrator, and plays TTS audio responses when available.

Quickstart — Docker image

Make sure `.env.docker` exists in the repo root (see example above). Then build/push images:

```bash
make build-image IMAGE_TAG=latest
make push-image IMAGE_TAG=latest   # pushes multi-arch image (requires buildx)
```

Troubleshooting — save decoded audio

To save WAVs written by the processor for STT debugging, set the save paths in your `.env.local` or `.env.docker`:

```env
SAVE_AUDIO_DIR_HOST=/tmp/discord-voice-audio
SAVE_AUDIO_DIR_CONTAINER=/app/wavs
```

If you run with Docker Compose the compose file mounts `./logs` and `./.wavs` by default; ensure `SAVE_AUDIO_DIR_HOST` points to a host directory you want to collect.

WAVs are written per flush with names like: 20250101T123456.000Z_ssrc12345_username.wav

Where to look next

- `services/pybot/` — Python bot packages (audio pipeline, wake detection, transcription, orchestrator bridge, MCP integration, Discord client wiring).
- `services/bot/` — Original Go implementation retained for reference.
- `docs/` — architecture and development guides shared between runtimes.

That's all you need to get started. For changes to runtime behavior, update env defaults in both the Python and Go entrypoints and keep the docs in sync.
