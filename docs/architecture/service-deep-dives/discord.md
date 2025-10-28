---
title: Discord Service Deep Dive
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-18
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Architecture ▸ Service Deep Dives ▸ Discord Bot

# Discord Voice Service

The Discord service runs the voice-enabled bot that bridges guild conversations to the rest of the
stack.

## Responsibilities

-  Maintain a persistent gateway and voice connection to the configured guild/channel.
-  Buffer PCM audio, apply VAD segmentation, and forward speech windows to the STT API.
-  Match transcripts against configured wake phrases before invoking the orchestrator.
-  Play orchestrator-supplied audio streams (TTS output) back into the voice channel.

## Key Modules

| File | Purpose |
| --- | --- |
| `audio.py` | Handles audio receive loops, buffering, and VAD-based segmentation. |
| `wake.py` | Evaluates transcripts against wake phrase thresholds with optional preview logging. |
| `transcription.py` | Manages HTTP calls to the STT service with retry behavior. |
| `discord_voice.py` | Coordinates Discord client lifecycle, playback, and event handling. |

## Configuration Highlights

-  `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `DISCORD_VOICE_CHANNEL_ID` — Core connection identifiers.
-  `WAKE_PHRASES`, `WAKE_THRESHOLD` — Wake detection tuning.
-  `STT_BASE_URL`, `STT_TIMEOUT` — Speech-to-text endpoint and timeout.
-  Logging controlled via shared `LOG_LEVEL`/`LOG_JSON` from `.env.common`.

## Observability

-  Structured JSON logs emit transcript previews and wake matches.
-  Optional Prometheus metrics can bind to `METRICS_PORT` if configured.
-  Use `make logs SERVICE=discord` for live troubleshooting and correlation with STT/LLM logs.

## Observability Notes

-  High-volume events like `voice.vad_decision`, `voice.frame_buffered`, and unknown user/SSRC messages are sampled to reduce noise in production.
-  Configure sampling via env:
  -  `LOG_SAMPLE_VAD_N` (default 50)
  -  `LOG_SAMPLE_UNKNOWN_USER_N` (default 100)
  -  `LOG_RATE_LIMIT_PACKET_WARN_S` (default 10s)
-  Correlation IDs propagate across services (`X-Correlation-ID`) to trace a segment from Discord → STT → Orchestrator → LLM.

## API Surface

-  `POST /api/v1/messages` — Send text message to Discord channel.
-  `POST /api/v1/transcripts` — Handle transcript notification from orchestrator.
-  `GET /api/v1/capabilities` — List available capabilities.
-  `GET /health/live` — Liveness check for container health.
-  `GET /health/ready` — Readiness check for service availability.

## Dependencies

-  Depends on the STT service for transcription and the orchestrator for response planning.
-  Uses the TTS service indirectly through orchestrator-provided URLs for playback.
