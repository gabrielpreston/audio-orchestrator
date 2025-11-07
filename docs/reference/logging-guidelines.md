---
title: Logging Level Guidelines
author: Discord Voice Lab Team
status: active
last-updated: 2025-01-27
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Reference ▸ Logging Level Guidelines

# Logging Level Guidelines

This document establishes consistent logging level guidelines for all services in the audio-orchestrator project. These guidelines ensure that production logs are clean and actionable while preserving diagnostic information for debugging.

## Logging Level Decision Tree

When adding a new log statement, use this decision tree:

1.  **Is this a critical service-threatening issue?** → `CRITICAL`
2.  **Is this an operation failure that breaks functionality?** → `ERROR`
3.  **Is functionality degraded but service still works?** → `WARNING`
4.  **Is this an operational milestone operators need to see?** → `INFO`
5.  **Is this diagnostic detail for debugging?** → `DEBUG`

## Logging Levels

### DEBUG

**Purpose**: Diagnostic details for developers debugging issues.

**Use for**:

-  Diagnostic details: packet processing, frame-by-frame VAD decisions, accumulator state
-  Internal implementation details: buffer status, SSRC mapping details, connection attempts
-  Technical metadata: data types, attribute inspection, internal state transitions
-  High-frequency events: packet reception, frame processing, callback scheduling
-  Implementation details: request sending, encoding steps, internal validation

**Examples**:

```python
logger.debug("voice.packet_received", user_id=user_id, ssrc=ssrc)
logger.debug("stt.request_sending", correlation_id=correlation_id, url=url)
logger.debug("audio.encode_warmup_ms", value=elapsed_ms)
```

**Pattern**: Use DEBUG for information that is useful during development/debugging but too verbose for production INFO logs.

### INFO

**Purpose**: Operational milestones that operators need to monitor.

**Use for**:

-  Operational milestones: service startup/ready, bot connected, voice connected
-  Significant state changes: segment created, wake phrase detected, transcript received
-  Successful operations: audio playback started, STT response received, messages sent
-  Configuration changes: model loaded, health checks passed

**Examples**:

```python
logger.info("discord.service_ready", service="discord")
logger.info("discord.voice_connected", guild_id=guild_id, channel_id=channel_id)
logger.info("wake.detection_result", detected=True, phrase="hey assistant")
logger.info("stt.response_received", correlation_id=correlation_id, text_length=len(text))
```

**Pattern**: INFO logs should tell the story of what the service is doing at a high level. Operators should be able to understand service behavior from INFO logs alone.

### WARNING

**Purpose**: Degraded functionality or noteworthy issues that don't break the service.

**Use for**:

-  Degraded functionality: service unavailable (circuit breaker), wake models not loaded
-  Expected but noteworthy issues: connection retries, corrupted packets skipped
-  Performance concerns: low RMS values, timeout warnings
-  Missing optional components: health client init failed (non-critical)

**Examples**:

```python
logger.warning("stt.circuit_open", correlation_id=correlation_id, action="dropping_segment")
logger.warning("voice.corrupted_packet_skipped", error=str(exc), user_id=user_id)
logger.warning("discord.stt_health_client_init_failed", error=str(exc))
```

**Pattern**: WARNING indicates something is wrong but the service continues to function, possibly with reduced capabilities.

### ERROR

**Purpose**: Operation failures that break functionality.

**Use for**:

-  Operation failures: connection failures, transcription failures, playback failures
-  Missing critical components: listen method missing, extension unavailable
-  Communication failures: orchestrator unavailable, STT request failed
-  Invalid configurations: bot token invalid, dependency timeout

**Examples**:

```python
logger.error("stt.request_failed", error=str(exc), correlation_id=correlation_id)
logger.error("discord.voice_connection_failed", error=str(exc), guild_id=guild_id)
logger.error("voice.receiver_callback_failed", error=str(exc))
```

**Pattern**: ERROR indicates a failure that prevents normal operation. These should be investigated promptly.

### CRITICAL

**Purpose**: Service-threatening issues that may cause service shutdown.

**Use for**:

-  Service-threatening issues: critical extension missing, fatal initialization failures
-  Unrecoverable errors that require immediate attention

**Examples**:

```python
logger.critical("discord.critical_extension_missing", extension="discord.ext.voice_recv")
logger.critical("discord.fatal_initialization_failure", error=str(exc))
```

**Pattern**: CRITICAL indicates the service cannot continue operating. These are rare and require immediate action.

## Common Patterns

### Pattern 1: First-N-then-DEBUG

For diagnostic details that are useful during initial debugging but too verbose for ongoing operation:

```python
if call_count < 5:
    logger.info("initial.diagnostic_event", call_number=call_count, ...)
else:
    logger.debug("ongoing.diagnostic_event", call_number=call_count, ...)
```

**Applied to**: Packet processing, handler calls, connection attempts

**Rationale**: First few events help with initial debugging, but ongoing events should be DEBUG to reduce log noise.

### Pattern 2: Operational Milestones

Significant state changes that operators need to see at INFO:

-  Service startup/ready
-  Bot connected/disconnected
-  Voice channel connected/disconnected
-  Segment created/flushed
-  Wake phrase detected
-  Transcript received/sent

**Rationale**: These events represent the normal flow of the service and should be visible at INFO level.

### Pattern 3: Degraded Functionality

When service works but functionality is reduced → WARNING:

-  Circuit breaker open
-  Optional components unavailable
-  Fallback modes active
-  Retries happening

**Rationale**: Service is functioning but not at full capacity. Operators should be aware but not alarmed.

### Pattern 4: Error Handling

Operation failures → ERROR:

-  Connection failures
-  Request failures
-  Missing critical components
-  Invalid configurations

**Rationale**: These represent actual failures that need investigation.

## Log Sampling and Rate Limiting

For high-frequency events, use sampling and rate limiting to reduce log volume:

```python
from services.common.structured_logging import should_sample, should_rate_limit

# Sample every Nth event
if should_sample("event.name", sample_n=50):
    logger.debug("event.name", ...)

# Rate limit to once per N seconds
if should_rate_limit("event.name", rate_s=1.0):
    logger.debug("event.name", ...)
```

**Configuration**:

-  `LOG_SAMPLE_VAD_N` (default 50) - Sample VAD decisions
-  `LOG_SAMPLE_UNKNOWN_USER_N` (default 100) - Sample unknown user events
-  `LOG_RATE_LIMIT_PACKET_WARN_S` (default 10s) - Rate limit packet warnings

## Best Practices

1.  **Use structured logging**: Always use structured log fields instead of string interpolation

   ```python
   # Good
   logger.info("event.name", user_id=user_id, correlation_id=correlation_id)

   # Bad
   logger.info(f"Event for user {user_id} with correlation {correlation_id}")
   ```

1.  **Include correlation IDs**: Propagate correlation IDs across service boundaries

   ```python
   from services.common.structured_logging import bind_correlation_id
   logger = bind_correlation_id(logger, correlation_id)
   ```

1.  **Use appropriate log levels**: When in doubt, use DEBUG for diagnostic details

   ```python
   # If unsure whether INFO or DEBUG, prefer DEBUG
   # Operators can enable DEBUG when needed
   ```

1.  **Preserve operational visibility**: Keep operational milestones at INFO

   ```python
   # Service state changes, successful operations, and significant events
   # should be visible at INFO level
   ```

1.  **Document patterns**: If you create a new logging pattern, document it here

## Service-Specific Considerations

### Discord Service

-  **High-frequency events**: Packet processing, VAD decisions, frame buffering → DEBUG with sampling
-  **Operational milestones**: Voice connected, wake detected, transcript received → INFO
-  **First-N pattern**: First few diagnostic events at INFO, rest at DEBUG

### STT Service

-  **Request details**: Implementation details → DEBUG
-  **Operational events**: Request initiated, response received → INFO
-  **Failures**: Request failures → ERROR

### Orchestrator Service

-  **Reasoning steps**: LLM interactions → DEBUG
-  **Tool calls**: Successful tool invocations → INFO
-  **Failures**: Tool failures → ERROR

## Review Checklist

When adding new log statements:

-  [ ] Is the log level appropriate for the event type?
-  [ ] Is the log structured (not using string interpolation)?
-  [ ] Does it include correlation IDs when applicable?
-  [ ] Is high-frequency logging properly sampled/rate-limited?
-  [ ] Would an operator need to see this at INFO level?
-  [ ] Is diagnostic detail in DEBUG level?

## References

-  [Discord Service Deep Dive](../architecture/service-deep-dives/discord.md) - Discord-specific logging patterns
-  [Configuration Catalog](configuration-catalog.md) - Logging configuration variables
-  [Structured Logging Implementation](../../services/common/structured_logging.py) - Logging utilities
