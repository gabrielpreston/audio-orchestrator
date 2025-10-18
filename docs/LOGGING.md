---
title: Logging Standards and Guidelines
last-updated: 2025-10-17
---

# Logging Standards and Guidelines

This document outlines the logging standards and best practices for the Discord Voice Lab project.

## Log Levels and Usage

### TRACE

- **Purpose**: Ultra-verbose debugging information
- **Usage**: Per-packet/per-frame events (RTCP, silence packets)
- **Example**: Individual audio frame processing, network packet details

### DEBUG

- **Purpose**: Diagnostic information useful during development
- **Usage**: VAD decisions, audio normalization, internal state changes
- **Example**: `voice.vad_decision`, `audio.normalized`, `wake.detection_attempt`

### INFO

- **Purpose**: Normal operational events
- **Usage**: Service connections, segment processing, state changes
- **Example**: `discord.ready`, `stt.request_initiated`, `orchestrator.processing_started`

### WARNING

- **Purpose**: Unexpected but recoverable issues
- **Usage**: Retries, fallbacks, circuit breaker states
- **Example**: `stt.circuit_open`, `wake.model_load_failed`

### ERROR

- **Purpose**: Failures requiring attention
- **Usage**: STT timeouts, orchestrator errors, service failures
- **Example**: `stt.transcribe_failed`, `orchestrator.transcript_processing_failed`

### CRITICAL

- **Purpose**: Service-level failures
- **Usage**: Can't connect to Discord, model load failures
- **Example**: `discord.connection_failed`, `stt.model_load_critical`

## Required Fields

All log events must include these standard fields:

### Service Identification

```json
{
  "service": "discord|stt|orchestrator|tts|llm"
}
```

### Correlation IDs

```json
{
  "correlation_id": "uuid-string"
}
```

### User Context (when applicable)

```json
{
  "user_id": 123456789
}
```

### Trace Context (when OpenTelemetry is available)

```json
{
  "trace_id": "32-character-hex",
  "span_id": "16-character-hex"
}
```

## Event Naming Conventions

### Format: `service.event_name`

Examples:

- `discord.voice_connected`
- `stt.request_initiated`
- `orchestrator.processing_started`
- `wake.detection_result`

### Common Event Types

#### Connection Events

- `service.connected`
- `service.disconnected`
- `service.reconnecting`

#### Request/Response Events

- `service.request_initiated`
- `service.response_received`
- `service.request_failed`

#### Processing Events

- `service.processing_started`
- `service.processing_completed`
- `service.processing_failed`

## Sampling Strategies

### High-Frequency Events

For events that occur very frequently, use sampling to reduce log volume:

```python
# Sample at 1% after first 10 occurrences
if sequence <= 10 or sequence % 100 == 0:
    logger.debug("event.name", ...)
```

### Examples of Sampled Events

- VAD decisions (1% after first 10)
- Audio normalization (configurable sampling via `LOG_SAMPLE_AUDIO_RATE`, default 0.005)
- RTCP packets (1% or aggregate)

### Audio Frame Logging (REMOVED)

**Important**: PCM frame logging has been removed from `services/discord/receiver.py` as it was creating 97% of log volume with no actionable troubleshooting value. Audio processing metrics are still tracked through VAD decisions with proper sampling.

**Before**: Every RTP packet logged twice (`voice.pcm_received`, `voice.decoder_output`)
**After**: Only VAD decisions sampled at 1% after first 10 frames
**Impact**: 95% reduction in log volume while maintaining observability

## Correlation ID Usage

### Propagation

Correlation IDs should propagate through the entire request chain:

1. **Discord Service**: Generate correlation ID when audio segment is created
2. **STT Service**: Include correlation ID in request headers
3. **Orchestrator**: Use correlation ID for all downstream processing
4. **TTS Service**: Include correlation ID in synthesis requests

### Implementation

```python
from services.common.logging import bind_correlation_id

# Bind correlation ID to logger
logger = bind_correlation_id(self._logger, segment.correlation_id)

# All subsequent logs will include the correlation ID
logger.info("stt.request_initiated", user_id=segment.user_id, ...)
```

## Structured Logging

### JSON Format

All logs use structured JSON format via structlog:

```json
{
  "event": "stt.request_initiated",
  "level": "info",
  "timestamp": "2025-10-17T18:24:47.133137Z",
  "service": "discord",
  "correlation_id": "abc123-def456",
  "user_id": 140570555303591937,
  "audio_bytes": 3840,
  "duration": 0.08
}
```

### Field Naming

- Use snake_case for field names
- Be descriptive but concise
- Include units in field names when relevant (e.g., `latency_ms`, `audio_bytes`)

## Performance Considerations

### Log Volume Reduction

- Use sampling for high-frequency events
- Aggregate similar events when possible
- Remove or downgrade routine debug events
- Suppress overly verbose third-party libraries (e.g., python-multipart)
- Optional sampling for `voice.segment_ready` via `LOG_SAMPLE_SEGMENT_READY_RATE` (0..1) or `LOG_SAMPLE_SEGMENT_READY_N` (every N)

### Stage timing fields

Discord emits per-segment timing fields to aid diagnosis:

```json
{
  "event": "voice.segment_processing_complete",
  "pre_stt_ms": 3,
  "stt_ms": 2190,
  "orchestrator_ms": 12993,
  "tts_ms": 388
}
```

Warm-ups:

- `audio.encode_warmup_ms` on Discord startup (PCM→WAV preheating)
- `stt.warmup_ms` on STT startup (dummy transcribe)

### Memory Usage

- Avoid logging large objects (audio data, full transcripts)
- Use previews for long text (e.g., `transcript[:120]`)
- Log metadata instead of full payloads

## Security and Privacy

### Sensitive Data

- Never log passwords, tokens, or API keys
- Redact PII when necessary
- Use correlation IDs instead of user IDs in some contexts

### Audio Data

- Don't log raw audio data
- Log metadata only (duration, sample rate, frame count)
- Consider log retention policies for audio-related logs

## Troubleshooting with Logs

### Common Debugging Scenarios

#### "Why didn't the bot respond?"

1. Check for `stt.request_initiated` and `stt.response_received`
2. Look for `wake.detection_result` events
3. Verify `orchestrator.processing_started` and `orchestrator.processing_completed`
4. Check for error events in the chain

#### "Audio quality issues"

1. Look for `audio.normalized` events with RMS values
2. Check `voice.pipeline_stats` for speech ratio
3. Verify VAD decisions in `voice.vad_decision`

#### "Performance problems"

1. Check latency values in response events
2. Look for circuit breaker states
3. Monitor queue depths and processing times

### Log Volume Expectations

**Normal Operation (per minute):**

- **Total logs**: ~50-100 events (down from 1,200+)
- **INFO logs**: 60-80% (service events, segment processing)
- **DEBUG logs**: 20-40% (VAD decisions, internal state)
- **WARNING/ERROR**: <5% (issues requiring attention)

**During Active Voice:**

- **Segment processing**: 1-5 `voice.segment_flushing` events per minute
- **STT requests**: 1-5 `stt.request_initiated`/`stt.response_received` pairs
- **Wake detection**: 0-2 `wake.detection_result` events
- **VAD decisions**: ~10-20 sampled `voice.vad_decision` events

**Startup Sequence:**

- Service initialization: ~15 INFO events
- Voice connection: ~8 INFO events
- Dependency checks: ~4 INFO events
- **Total startup**: ~30 events (fits on one screen)

### Correlation ID Usage

Use correlation IDs to trace a single request through all services:

```bash
# Find all logs for a specific correlation ID
grep "abc123-def456" docker.logs

# Or use structured log analysis tools
jq 'select(.correlation_id == "abc123-def456")' logs.json
```

## Monitoring and Alerting

### Key Metrics to Monitor

- Request rates by service
- Error rates and types
- Latency percentiles
- Audio pipeline metrics (speech ratio, segment duration)

### Alert Conditions

- High error rates (>5% for 5 minutes)
- High latency (>2s for STT, >5s for orchestrator)
- Service unavailability
- Circuit breaker open states

## Best Practices

### Do's

- ✅ Use structured logging with consistent field names
- ✅ Include correlation IDs in all related events
- ✅ Log at appropriate levels (DEBUG for diagnostics, INFO for operations)
- ✅ Use sampling for high-frequency events
- ✅ Include context (user_id, service, correlation_id)

### Don'ts

- ❌ Log sensitive data (passwords, tokens, PII)
- ❌ Log large objects (audio data, full transcripts)
- ❌ Use inconsistent event naming
- ❌ Log at wrong levels (DEBUG for normal operations)
- ❌ Forget to propagate correlation IDs

## Tools and Integration

### Log Analysis

- Use `jq` for JSON log analysis
- Implement log aggregation (ELK stack, Grafana Loki)
- Set up dashboards for key metrics

### Development

- Use correlation IDs for local debugging
- Enable DEBUG level for development
- Use structured logging for better searchability

### Production

- Use INFO level for normal operations
- Implement log rotation and retention
- Monitor log volume and costs
- Set up alerting on error patterns

## Sampling and Rate Limiting

High-frequency events are sampled to reduce log volume in production. Configure via environment variables:

```env
LOG_SAMPLE_VAD_N=50                # VAD/frame logs: log every Nth event
LOG_SAMPLE_UNKNOWN_USER_N=100      # Unknown user/SSRC logs: every Nth event
LOG_RATE_LIMIT_PACKET_WARN_S=10    # Minimum seconds between packet warning logs
LOG_SAMPLE_AUDIO_RATE=0.005        # Probability for audio normalization debug logs
```

These are consumed by the Discord service (`services/discord/audio.py`, `services/discord/receiver.py`) and implemented via helpers in `services/common/logging.py` (`should_sample`, `should_rate_limit`).

### Recommended defaults

- VAD/frame: 50
- Unknown user/SSRC: 100
- Packet warnings: 10s
- Audio normalization sampling: 0.005

## Docker Log Rotation

Enable JSON-file log rotation to prevent disk growth. Already configured in `docker-compose.yml` for all services:

```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "5"
```

This keeps per-service logs manageable while retaining recent history for troubleshooting.
