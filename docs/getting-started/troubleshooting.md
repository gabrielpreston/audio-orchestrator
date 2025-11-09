---
title: Troubleshooting Checklist
author: Discord Voice Lab Team
status: active
last-updated: 2024-07-05
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Getting Started ▸ Troubleshooting

# Troubleshooting

Use this checklist to resolve the most common setup issues when running the stack locally.

## Docker & Compose

| Symptom | Resolution |
| --- | --- |
| Containers exit immediately | Run `docker compose logs` to capture stack traces; confirm `.env.service` files exist. |
| Permission denied on mounted volumes | Set `PUID`/`PGID` in `.env.docker` to match your host user ID and rerun `make run`. |
| Network ports already in use | Stop conflicting services or update exposed ports in `docker-compose.yml`. |

## Audio & Voice Pipeline

| Symptom | Resolution |
| --- | --- |
| Bot fails to join a voice channel | Verify `DISCORD_VOICE_CHANNEL_ID` and guild permissions; check for stale voice connections in Discord. |
| Wake phrase never triggers | Confirm `WAKE_THRESHOLD` and model configuration; inspect logs for detection scores. |
| STT requests time out | Ensure `STT_BASE_URL` points to the Compose service (`http://stt:9000`) and that the STT container is healthy. |

## Tooling & Credentials

| Symptom | Resolution |
| --- | --- |
| Tools unavailable | Populate tool configuration in `services/discord/.env.service` and restart the bot. |
| TTS responses missing | Confirm the TTS container is running and `TTS_AUTH_TOKEN` matches the orchestrator configuration. |
| Lint target fails on Markdown | Run `make lint-fix` or format manually; Markdown lint rules live in the lint container image. |

## Support

Capture failing commands and relevant log excerpts, then open an issue or drop them into the
[reports index](../reports/README.md) if the problem uncovered new operational insights.
