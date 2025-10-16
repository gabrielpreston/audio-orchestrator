---
title: Environment Configuration
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-16
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Getting Started ▸ Environment Configuration

# Environment Configuration

This guide explains how to provision the `.env` files required by the Discord bot,
supporting services, and Docker Compose stack.

## Required Files

| Path | Purpose | Source |
| --- | --- | --- |
| `.env.common` | Shared logging defaults consumed by every Python service. | Copy from `.env.sample`. |
| `.env.docker` | Container-specific overrides such as UID/GID and timezone. | Copy from `.env.sample`. |
| `services/discord/.env.service` | Discord token, wake phrase settings, STT endpoint, MCP manifests. | Copy from `.env.sample`. |
| `services/stt/.env.service` | faster-whisper model, device, and compute type. | Copy from `.env.sample`. |
| `services/llm/.env.service` | Orchestrator auth token, llama.cpp configuration, downstream TTS URL. | Copy from `.env.sample`. |
| `services/tts/.env.service` | Piper model paths, voice defaults, auth token, rate limiting. | Copy from `.env.sample`. |

## Setup Steps

1. Use the automated script to generate environment files from `.env.sample`:
   ```bash
   python3 scripts/prepare_env_files.py
   ```
2. Populate secrets (Discord bot token, auth tokens) with production-ready values in the generated `.env.service` files.
3. Verify configuration using the new configuration library (see [Configuration Library Reference](../reference/configuration-library.md)).
4. Commit `.env.sample` changes when you introduce new keys so contributors can refresh their local files.

## Best Practices

- Keep sensitive secrets out of version control; rely on deployment tooling or password managers.
- Align defaults across `.env.sample`, `.env.common`, and service `.env.service` files whenever you rename keys.
- Document any new environment variable in the [configuration catalog](../reference/configuration-catalog.md).
- Use the new configuration library for type-safe configuration management (see [Configuration Library Reference](../reference/configuration-library.md)).
- Use `.env.docker` to resolve file-permission issues by matching host UID/GID when mounting volumes.

## Validation Checklist

- [ ] `make run` succeeds with your environment files in place.
- [ ] `make logs SERVICE=discord` shows the bot connecting to Discord without authentication errors.
- [ ] `make logs SERVICE=stt` confirms the chosen faster-whisper model loaded successfully.
