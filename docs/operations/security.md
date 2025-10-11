---
title: Security Guidelines
author: Discord Voice Lab Team
status: active
last-updated: 2024-07-05
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Operations ▸ Security

# Security Guidelines

Adopt these practices to protect credentials, audio data, and automation tooling while operating the
voice lab stack.

## Credential Management

- Store Discord bot tokens, orchestrator auth tokens, and MCP secrets outside version control.
- Rotate tokens whenever access is revoked or incidents occur; update `.env.service` files accordingly.
- Limit Discord bot scopes to required intents (`guilds`, `guild_voice_states`).

## Network & Access Control

- Restrict MCP WebSocket endpoints with authentication and TLS (`wss://`).
- Keep Docker networks private; expose only required ports to the host.
- Enable firewall rules that limit inbound access to orchestrator and TTS services.

## Data Handling

- Avoid persisting raw audio unless debugging requires it; prefer ephemeral streams.
- Scrub personally identifiable information from logs before sharing incident reports.
- Use the [reports](../reports/README.md) section to document investigations without leaking secrets.

## Compliance Checklist

- [ ] Secrets managed through environment variables or secret stores.
- [ ] MCP manifests stored securely with least-privilege credentials.
- [ ] Access reviews conducted quarterly for Discord, Monday.com, GitHub, and AWS integrations.
