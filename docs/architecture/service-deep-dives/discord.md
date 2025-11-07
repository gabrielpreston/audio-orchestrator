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

## Logging Level Expectations

The Discord service follows the [Logging Level Guidelines](../../reference/logging-guidelines.md) for consistent observability:

### INFO Level (Operational Milestones)

Operators should see these events in production:

-  `discord.service_ready` - Service startup complete
-  `discord.voice_connected` - Voice channel connection established
-  `discord.voice_disconnected` - Voice channel disconnected
-  `voice.ssrc_mapping_received` - User identified and mapped to SSRC
-  `voice.buffered_packets_flushed` - Buffered packets processed for new user
-  `wake.detection_result` (detected=True) - Wake phrase detected
-  `stt.request_initiated` - STT request started
-  `stt.response_received` - STT transcription received

### DEBUG Level (Diagnostic Details)

These events are available when `LOG_LEVEL=DEBUG`:

-  `voice.packet_received` - Individual packet reception (rate-limited)
-  `voice.packet_processing` - Packet processing details (first-N pattern)
-  `voice.process_packet_entry` - Internal packet processing (first-N pattern)
-  `voice.process_packet_success` - Successful packet processing (first-N pattern)
-  `voice.handler_called` - Handler invocation (first-N pattern)
-  `stt.request_sending` - HTTP request implementation details
-  `audio.encode_warmup_ms` - Audio encoding warmup timing
-  `discord.gateway_session_validated` - Gateway session validation
-  `wake.detection_result` (detected=False) - Non-detection events

### WARNING Level (Degraded Functionality)

-  `stt.circuit_open` - STT service unavailable, circuit breaker open
-  `voice.corrupted_packet_skipped` - Corrupted packet detected and skipped
-  `discord.stt_health_client_init_failed` - Health client initialization failed (non-critical)

### ERROR Level (Operation Failures)

-  `stt.request_failed` - STT request failed after retries
-  `voice.receiver_callback_failed` - Audio callback execution failed
-  `discord.voice_connection_failed` - Voice connection attempt failed

### First-N Pattern

For high-frequency diagnostic events, the first 5 occurrences are logged at INFO level for initial debugging, with subsequent events at DEBUG level:

```python
if call_count < 5:
    logger.info("voice.packet_processing", packet_number=call_count, ...)
else:
    logger.debug("voice.packet_processing", packet_number=call_count, ...)
```

This pattern provides visibility into initial behavior while keeping ongoing operations at DEBUG level to reduce log noise.

## API Surface

-  `POST /api/v1/messages` — Send text message to Discord channel.
-  `POST /api/v1/transcripts` — Handle transcript notification from orchestrator.
-  `GET /api/v1/capabilities` — List available capabilities.
-  `GET /health/live` — Liveness check for container health.
-  `GET /health/ready` — Readiness check for service availability.

## Dependencies

-  Depends on the STT service for transcription and the orchestrator for response planning.
-  Uses the TTS service indirectly through orchestrator-provided URLs for playback.
