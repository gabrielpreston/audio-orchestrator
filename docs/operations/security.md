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
- Use the automated token rotation script for consistent AUTH_TOKEN management across all services.
- Limit Discord bot scopes to required intents (`guilds`, `guild_voice_states`).

### Token Rotation

The `discord-voice-lab` includes an automated script for rotating AUTH_TOKEN values across all environment files:

```bash
# Rotate all AUTH_TOKENs
make rotate-tokens

# Preview changes without modifying files
make rotate-tokens-dry-run

# Validate token consistency across all environment files
make validate-tokens
```

The rotation script:
- Generates cryptographically secure random tokens (32 characters by default)
- Updates all relevant environment files (`.env.sample`, service-specific `.env.service` files)
- Validates token consistency after rotation
- Supports dry-run mode for safe testing
- Can rotate specific tokens or all tokens at once

For manual rotation or custom token lengths:
```bash
# Rotate only specific tokens
./scripts/rotate_auth_tokens.py --tokens ORCH_AUTH_TOKEN

# Use custom token length
./scripts/rotate_auth_tokens.py --length 64
```

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
