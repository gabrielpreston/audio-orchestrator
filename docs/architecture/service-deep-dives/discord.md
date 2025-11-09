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
-  `WAKE_THRESHOLD` — Wake detection tuning.
-  `STT_BASE_URL`, `STT_TIMEOUT` — Speech-to-text endpoint and timeout.
-  `AUDIO_QUALITY_MIN_SNR_DB`, `AUDIO_QUALITY_MIN_RMS`, `AUDIO_QUALITY_MIN_CLARITY` — Audio quality validation thresholds.
-  `AUDIO_QUALITY_WAKE_MIN_SNR_DB`, `AUDIO_QUALITY_WAKE_MIN_RMS` — Wake detection specific quality thresholds.
-  `DISCORD_VOICE_HEALTH_MONITOR_TIMEOUT_S` — Timeout for detecting PacketRouter crashes (default: 5.0 seconds).
-  `DISCORD_VOICE_RECONNECT_BASE_DELAY`, `DISCORD_VOICE_RECONNECT_MAX_DELAY` — Reconnection backoff configuration.
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
-  `wake.format_conversion` - Audio format conversion (float32 → int16) for OpenWakeWord

### WARNING Level (Degraded Functionality)

-  `stt.circuit_open` - STT service unavailable, circuit breaker open
-  `voice.corrupted_packet_skipped` - Corrupted packet detected and skipped
-  `discord.voice_health_monitor_timeout` - PacketRouter crash detected, automatic reconnection triggered
-  `discord.stt_health_client_init_failed` - Health client initialization failed (non-critical)

### ERROR Level (Operation Failures)

-  `stt.request_failed` - STT request failed after retries
-  `voice.receiver_callback_failed` - Audio callback execution failed
-  `discord.voice_connection_failed` - Voice connection attempt failed
-  `discord.health_monitor_error` - Health monitoring task encountered an error

### Audio Quality Validation

The Discord service now includes automated audio quality validation during wake detection to help diagnose detection failures.

**Quality Metrics Logging**:

Quality metrics (RMS, SNR, clarity score) are automatically calculated and logged with every wake detection attempt:

-  `audio_processor_wrapper.wake_detection_invoked` — Includes quality metrics when wake detection is attempted
-  `audio_processor_wrapper.wake_detection_no_result` — Includes quality metrics when detection finds nothing

**Configuration**:

Quality thresholds are configurable via environment variables (see Configuration Highlights above). Defaults are:

-  SNR: 10.0 dB (minimum acceptable)
-  RMS: 100.0 (minimum acceptable)
-  Clarity: 0.3 (minimum acceptable)

**Troubleshooting Quality Issues**:

If wake detection is failing, check quality metrics in logs:

1.  Look for `audio_processor_wrapper.wake_detection_invoked` events with low `snr_db`, `rms`, or `clarity_score` values
2.  Use `make analyze-audio-quality` to generate quality reports from logs
3.  Compare metrics against thresholds:

   -  **Good**: SNR > 20dB, RMS > 200, Clarity > 0.7
   -  **Acceptable**: SNR > 10dB, RMS > 100, Clarity > 0.3
   -  **Poor**: SNR < 10dB, RMS < 100, Clarity < 0.3 (likely causing failures)

**Common Quality Issues**:

-  **Low SNR**: Background noise or microphone issues
-  **Low RMS**: Audio level too quiet, check microphone gain
-  **Low Clarity**: Distorted audio or poor microphone quality
-  **Silent Audio (`snr_db: -Infinity`)**: Expected for silent audio (all zeros). This is normal and indicates no signal power.

### ONNX Dimension Mismatch Errors

If you see errors like `Got invalid dimensions for input: onnx::Flatten_0 for the following indices index: 1 Got: 14 Expected: 16`, this indicates the wake word model received audio with an unexpected melspectrogram frame count.

**Automatic Handling**:

The wake detection system now automatically pads or truncates audio to ensure consistent input dimensions:

-  Audio shorter than 5120 samples (320ms at 16kHz) is padded with zeros
-  Audio longer than 5120 samples is truncated to the last 5120 samples
-  Log events `wake.audio_padded` and `wake.audio_truncated` indicate when adjustments occur

**Troubleshooting**:

1.  Check logs for `wake.audio_padded` or `wake.audio_truncated` events to see dimension adjustments
2.  If errors persist, verify the custom model was trained with the expected input shape (16 melspectrogram frames)
3.  Check `wake.audio_inference_failed` events for detailed error messages
4.  Ensure the model file is compatible with the inference framework (`WAKE_INFERENCE_FRAMEWORK=onnx`)

### Audio Format Requirements

**OpenWakeWord Format**: The wake detection system automatically converts normalized float32 audio to int16 PCM format required by OpenWakeWord:

-  Audio is normalized to float32 for processing (padding/truncation)
-  Converted back to int16 before passing to the model
-  Values are clamped to prevent overflow during conversion
-  Format conversion is logged at DEBUG level with event `wake.format_conversion`

### PacketRouter Crash Detection and Auto-Reconnection

The Discord service includes automatic detection and recovery from PacketRouter crashes caused by corrupted Opus packets.

**Problem**:

When Discord sends a corrupted Opus packet, `discord-ext-voice-recv`'s `PacketRouter` raises
`OpusError` in its internal loop. The `PacketRouter.run()` method catches all exceptions and calls
`stop_listening()`, which stops all voice processing permanently until manual restart.

**Automatic Recovery**:

The service monitors packet reception timestamps per guild and automatically detects when PacketRouter crashes:

-  Tracks last packet received timestamp for each active voice connection
-  Runs periodic health check (every 1 second) to detect stale connections
-  When no packets received for configured timeout (default: 5 seconds) AND voice client is still connected, triggers automatic reconnection
-  Uses existing reconnection logic with exponential backoff

**Configuration**:

-  `DISCORD_VOICE_HEALTH_MONITOR_TIMEOUT_S` (default: 5.0) - Timeout in seconds before considering connection stale
-  Reconnection behavior controlled by existing `DISCORD_VOICE_RECONNECT_BASE_DELAY` and `DISCORD_VOICE_RECONNECT_MAX_DELAY`

**Logging**:

-  `discord.voice_health_monitor_timeout` (WARNING) - PacketRouter crash detected, reconnection triggered
-  `discord.voice_reconnect_scheduled` (INFO) - Reconnection scheduled with reason "packet_router_crashed"
-  `discord.voice_reconnect_success` (INFO) - Reconnection successful
-  `discord.health_monitor_error` (ERROR) - Health monitoring task encountered an error

**Troubleshooting**:

1.  If voice processing stops unexpectedly, check logs for `discord.voice_health_monitor_timeout` events
2.  Monitor `discord.voice_reconnect_success` to confirm automatic recovery
3.  If reconnection fails repeatedly, check network connectivity and Discord API status
4.  Adjust `DISCORD_VOICE_HEALTH_MONITOR_TIMEOUT_S` if false positives occur (e.g., during natural silence)

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
