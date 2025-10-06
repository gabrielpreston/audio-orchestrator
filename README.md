# Discord Voice Lab — Quickstart

A minimal Go scaffold for a Discord voice agent (audio → STT → orchestrator). This README provides the fastest path to run and test the project.

Prerequisites

- make
- Docker (optional, for image build/run)
- A Discord bot token (required)

Environment files (recommended)

This project supports loading environment variables from files instead of manual "export" commands. Use:

- `.env.local` — for local development (used by `make dev-bot` / `make dev-stt` which source this file when present)
- `.env.docker` — for containers (referenced by `docker-compose.yml` via the `env_file` field)

Essential environment variables (examples)

Create a `.env.local` for local runs or `.env.docker` for docker runs. Example contents:

```env
# .env.local or .env.docker
DISCORD_BOT_TOKEN=your_token_here
GUILD_ID=123456789012345678
VOICE_CHANNEL_ID=987654321098765432
WHISPER_URL=http://localhost:9000
LOG_LEVEL=info
DETAILED_EVENTS=false
ALLOWED_USER_IDS=12345,67890
# Optional: save decoded audio
SAVE_AUDIO_DIR_HOST=/tmp/discord-voice-audio
SAVE_AUDIO_DIR_CONTAINER=/app/wavs
```

Quickstart — local development

1. Run tests

```bash
make test
```

1. Build the binary

```bash
make build
# binary: bin/bot
```

1. Run the bot (local)

For a fast local developer experience, create a `.env.local` file (example above) and run the dev helper which will source that file automatically:

```bash
# start the bot binary in background (dev-friendly)
make dev-bot

# or run the STT service locally (dev helper will source .env.local if present)
make dev-stt
```

To run the full stack via Docker Compose, create a `.env.docker` (example above) and then:

```bash
make run
# the compose files use ./.env.docker via the `env_file` setting
```

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

- `cmd/bot/main.go` — app entry, env config, Discord session and handlers
- `internal/voice/*` — audio pipeline, opus decode, POSTs to STT (WHISPER_URL)
- `docs/` — architecture and development guides

That's all you need to get started. For changes to runtime behavior, update env defaults in `cmd/bot/main.go` and the docs as appropriate.
