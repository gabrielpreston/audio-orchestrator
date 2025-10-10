---
title: Discord Service Deep Dive
author: Discord Voice Lab Team
status: active
last-updated: 2024-07-05
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Architecture ▸ Service Deep Dives ▸ Discord Bot

# Discord Voice Service

The Discord service runs the voice-enabled bot that bridges guild conversations to the rest of the
stack.

## Responsibilities

- Maintain a persistent gateway and voice connection to the configured guild/channel.
- Buffer PCM audio, apply VAD segmentation, and forward speech windows to the STT API.
- Match transcripts against configured wake phrases before invoking the orchestrator.
- Expose Model Context Protocol (MCP) tools for Discord administration workflows.
- Play orchestrator-supplied audio streams (TTS output) back into the voice channel.

## Key Modules

| File | Purpose |
| --- | --- |
| `audio.py` | Handles audio receive loops, buffering, and VAD-based segmentation. |
| `wake.py` | Evaluates transcripts against wake phrase thresholds with optional preview logging. |
| `transcription.py` | Manages HTTP calls to the STT service with retry behavior. |
| `mcp.py` | Registers Discord-specific MCP tools (messaging, channel operations). |
| `discord_voice.py` | Coordinates Discord client lifecycle, playback, and event handling. |

## Configuration Highlights

- `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `DISCORD_VOICE_CHANNEL_ID` — Core connection identifiers.
- `WAKE_PHRASES`, `WAKE_THRESHOLD` — Wake detection tuning.
- `STT_BASE_URL`, `STT_TIMEOUT` — Speech-to-text endpoint and timeout.
- `MCP_MANIFESTS`, `MCP_WEBSOCKET_URL` — External tool integration.
- Logging controlled via shared `LOG_LEVEL`/`LOG_JSON` from `.env.common`.

## Observability

- Structured JSON logs emit transcript previews, wake matches, and MCP tool execution metadata.
- Optional Prometheus metrics can bind to `METRICS_PORT` if configured.
- Use `make logs SERVICE=discord` for live troubleshooting and correlation with STT/LLM logs.

## Dependencies

- Depends on the STT service for transcription and the orchestrator for response planning.
- Uses the TTS service indirectly through orchestrator-provided URLs for playback.
- MCP manifests expose integrations such as Monday.com, GitHub, or AWS when registered.
