---
title: Environment Configuration
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-18
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
| `services/discord/.env.service` | Discord token, wake phrase settings, STT endpoint. | Copy from `.env.sample`. |
| `services/stt/.env.service` | faster-whisper model, device, and compute type. | Copy from `.env.sample`. |
| `services/flan/.env.service` | FLAN-T5 model size, generation parameters, Hugging Face cache settings. | Copy from `.env.sample`. |
| `services/orchestrator/.env.service` | Orchestrator configuration, LLM/TTS client settings, LangChain config. | Copy from `.env.sample`. |
| `services/tts/.env.service` | Piper model paths, voice defaults, auth token, rate limiting. | Copy from `.env.sample`. |

## Setup Steps

-  Use the automated script to generate environment files from `.env.sample`:

   ```bash
   python3 scripts/prepare_env_files.py
   ```

-  Populate secrets (Discord bot token, auth tokens) with production-ready values in the generated `.env.service` files.
-  Verify configuration using the new configuration library (see [Configuration Library Reference](../reference/configuration-library.md)).
-  Commit `.env.sample` changes when you introduce new keys so contributors can refresh their local files.

## Configuration Pattern

The project follows a unified configuration pattern aligned with 12-Factor App principles:

### Configuration Variables → `.env.*` Files

All configuration variables (model paths, optimization flags, cache settings, force download flags) are stored in `.env.*` files:

-  **`.env.common`**: Shared defaults (logging, service URLs)
-  **`.env.docker`**: Container-specific overrides (UID/GID, timezone)
-  **`services/*/.env.service`**: Service-specific configuration (model settings, optimization flags)

### Runtime-Only Variables → Inline in `docker-compose.yml`

Only truly runtime-only container variables remain inline in `docker-compose.yml`:

-  Service binding addresses (e.g., `GRADIO_SERVER_NAME=0.0.0.0`)
-  Container-specific ports
-  Variables only needed at container startup time

### Precedence Hierarchy

Environment variables are loaded in the following order (highest to lowest precedence):

1.  **Shell environment variables** (set before `docker compose up`)
2.  **`.env` file** (root directory, if present)
3.  **`.env.common`** (shared defaults)
4.  **`.env.docker`** (container-specific)
5.  **`services/*/.env.service`** (service-specific)
6.  **`docker-compose.yml` inline `environment:` blocks** (runtime-only)
7.  **Dockerfile `ENV` directives** (image defaults)

Higher precedence sources override lower precedence sources. This allows for flexible configuration across different environments (development, testing, production).

## Best Practices

-  Keep sensitive secrets out of version control; rely on deployment tooling or password managers.
-  Align defaults across `.env.sample`, `.env.common`, and service `.env.service` files whenever you rename keys. Ensure new keys like `DISCORD_HTTP_MODE` and `ORCH_TIMEOUT` are present where applicable.
-  Document any new environment variable in the [configuration catalog](../reference/configuration-catalog.md).
-  Use the new configuration library for type-safe configuration management (see [Configuration Library Reference](../reference/configuration-library.md)).
-  Use `.env.docker` to resolve file-permission issues by matching host UID/GID when mounting volumes.
-  **Add new configuration variables to `.env.sample`** - never add them directly to `docker-compose.yml` inline `environment:` blocks unless they are truly runtime-only container settings.

## Validation Checklist

-  [ ] `make run` succeeds with your environment files in place.
-  [ ] `make logs SERVICE=discord` shows the bot connecting to Discord without authentication errors.
-  [ ] `make logs SERVICE=stt` confirms the chosen faster-whisper model loaded successfully.
