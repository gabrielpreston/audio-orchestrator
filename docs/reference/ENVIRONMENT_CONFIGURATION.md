---
last-updated: 2025-10-16
---

# Environment Configuration Guide

## Overview

This guide provides comprehensive configuration instructions for the composable surface architecture. It covers environment variables, configuration files, and deployment settings.

## Environment Variables

### Core Configuration

```bash
# Architecture Selection
USE_NEW_ARCHITECTURE=true                    # Enable new composable architecture
SURFACE_TYPE=discord                         # Primary surface type
SURFACE_ID=voice_channel_123                 # Surface identifier

# Feature Flags
ENABLE_AUDIO_CAPTURE=true                    # Enable audio capture
ENABLE_AUDIO_PLAYBACK=true                   # Enable audio playback
ENABLE_CONTROL_CHANNEL=true                  # Enable control channel
ENABLE_SURFACE_LIFECYCLE=true               # Enable surface lifecycle
```

### Audio Configuration

```bash
# Audio Format
AUDIO_SAMPLE_RATE=16000                      # Sample rate in Hz
AUDIO_CHANNELS=1                             # Number of audio channels
AUDIO_BIT_DEPTH=16                           # Bit depth
AUDIO_FRAME_SIZE_MS=20                       # Frame size in milliseconds

# Audio Processing
AUDIO_BUFFER_SIZE=1024                       # Audio buffer size
AUDIO_LATENCY_TARGET_MS=50                   # Target latency in milliseconds
AUDIO_QUALITY=high                           # Audio quality setting
AUDIO_COMPRESSION=false                      # Enable audio compression

# Audio Sources
AUDIO_SOURCE_ENABLED=true                    # Enable audio source
AUDIO_SOURCE_TIMEOUT_MS=5000                # Audio source timeout
AUDIO_SOURCE_RETRY_COUNT=3                   # Retry count for audio source

# Audio Sinks
AUDIO_SINK_ENABLED=true                      # Enable audio sink
AUDIO_SINK_TIMEOUT_MS=5000                   # Audio sink timeout
AUDIO_SINK_RETRY_COUNT=3                     # Retry count for audio sink
```

### Control Channel Configuration

```bash
# Control Events
CONTROL_EVENT_TIMEOUT_MS=1000                # Control event timeout
CONTROL_EVENT_RETRY_COUNT=3                  # Retry count for control events
CONTROL_EVENT_QUEUE_SIZE=100                 # Control event queue size

# Wake Word Detection
WAKE_WORD_ENABLED=true                       # Enable wake word detection
WAKE_WORDS="hey assistant,ok assistant"     # Comma-separated wake words
WAKE_WORD_CONFIDENCE_THRESHOLD=0.8           # Confidence threshold
WAKE_WORD_TIMEOUT_MS=5000                   # Wake word timeout

# Barge-in Control
BARGE_IN_ENABLED=true                        # Enable barge-in functionality
BARGE_IN_TIMEOUT_MS=2000                     # Barge-in timeout
BARGE_IN_CONFIDENCE_THRESHOLD=0.7            # Barge-in confidence threshold
```

### Surface Lifecycle Configuration

```bash
# Connection Management
SURFACE_CONNECTION_TIMEOUT_MS=10000          # Connection timeout
SURFACE_DISCONNECTION_TIMEOUT_MS=5000        # Disconnection timeout
SURFACE_RECONNECT_ENABLED=true               # Enable auto-reconnect
SURFACE_RECONNECT_DELAY_MS=2000              # Reconnect delay
SURFACE_RECONNECT_MAX_ATTEMPTS=5             # Max reconnect attempts

# Health Monitoring
SURFACE_HEALTH_CHECK_ENABLED=true            # Enable health checks
SURFACE_HEALTH_CHECK_INTERVAL_MS=30000       # Health check interval
SURFACE_HEALTH_CHECK_TIMEOUT_MS=5000         # Health check timeout
SURFACE_HEALTH_CHECK_RETRY_COUNT=3           # Health check retry count
```

### Discord-Specific Configuration

```bash
# Discord Bot
DISCORD_BOT_TOKEN=your_bot_token_here         # Discord bot token
DISCORD_GUILD_ID=123456789                   # Discord guild ID
DISCORD_CHANNEL_ID=987654321                  # Discord voice channel ID
DISCORD_USER_ID=111222333                    # Discord user ID

# Discord Voice
DISCORD_VOICE_ENABLED=true                   # Enable Discord voice
DISCORD_VOICE_TIMEOUT_MS=10000               # Voice connection timeout
DISCORD_VOICE_RECONNECT_ENABLED=true         # Enable voice reconnection
DISCORD_VOICE_QUALITY=high                   # Voice quality setting

# Discord Events
DISCORD_EVENT_TIMEOUT_MS=1000                # Discord event timeout
DISCORD_EVENT_RETRY_COUNT=3                  # Discord event retry count
DISCORD_EVENT_QUEUE_SIZE=100                 # Discord event queue size
```

### STT/TTS Configuration

```bash
# Speech-to-Text
STT_SERVICE_URL=http://localhost:8001         # STT service URL
STT_SERVICE_TIMEOUT_MS=10000                 # STT service timeout
STT_MODEL_NAME=base                          # STT model name
STT_LANGUAGE=en                              # STT language
STT_ENABLE_VAD=true                          # Enable voice activity detection
STT_VAD_THRESHOLD=0.5                        # VAD threshold

# Text-to-Speech
TTS_SERVICE_URL=http://localhost:8002         # TTS service URL
TTS_SERVICE_TIMEOUT_MS=10000                 # TTS service timeout
TTS_MODEL_NAME=piper                         # TTS model name
TTS_VOICE=default                            # TTS voice
TTS_LANGUAGE=en                              # TTS language
TTS_SPEED=1.0                                # TTS speed
```

### Session Management Configuration

```bash
# Session Broker
SESSION_BROKER_ENABLED=true                  # Enable session broker
SESSION_BROKER_URL=http://localhost:8003     # Session broker URL
SESSION_BROKER_TIMEOUT_MS=5000               # Session broker timeout
SESSION_BROKER_RETRY_COUNT=3                 # Session broker retry count

# Session Lifecycle
SESSION_TIMEOUT_MS=300000                    # Session timeout (5 minutes)
SESSION_CLEANUP_INTERVAL_MS=60000            # Session cleanup interval
SESSION_MAX_DURATION_MS=1800000              # Max session duration (30 minutes)
SESSION_IDLE_TIMEOUT_MS=120000               # Session idle timeout (2 minutes)
```

### Policy Engine Configuration

```bash
# Policy Engine
POLICY_ENGINE_ENABLED=true                   # Enable policy engine
POLICY_ENGINE_URL=http://localhost:8004      # Policy engine URL
POLICY_ENGINE_TIMEOUT_MS=5000                # Policy engine timeout
POLICY_ENGINE_RETRY_COUNT=3                  # Policy engine retry count

# VAD Policy
VAD_ENABLED=true                             # Enable VAD
VAD_THRESHOLD=0.5                            # VAD threshold
VAD_TIMEOUT_MS=2000                          # VAD timeout
VAD_SILENCE_TIMEOUT_MS=1000                  # VAD silence timeout

# Endpointing
ENDPOINTING_ENABLED=true                      # Enable endpointing
ENDPOINTING_THRESHOLD=0.5                    # Endpointing threshold
ENDPOINTING_TIMEOUT_MS=2000                  # Endpointing timeout
ENDPOINTING_SILENCE_TIMEOUT_MS=1000          # Endpointing silence timeout

# Barge-in Policy
BARGE_IN_POLICY_ENABLED=true                 # Enable barge-in policy
BARGE_IN_POLICY_THRESHOLD=0.7                # Barge-in policy threshold
BARGE_IN_POLICY_TIMEOUT_MS=2000              # Barge-in policy timeout
```

### Media Gateway Configuration

```bash
# Media Gateway
MEDIA_GATEWAY_ENABLED=true                   # Enable media gateway
MEDIA_GATEWAY_URL=http://localhost:8005     # Media gateway URL
MEDIA_GATEWAY_TIMEOUT_MS=5000                # Media gateway timeout
MEDIA_GATEWAY_RETRY_COUNT=3                  # Media gateway retry count

# Codec Conversion
CODEC_CONVERSION_ENABLED=true                # Enable codec conversion
CODEC_INPUT_FORMAT=pcm                       # Input codec format
CODEC_OUTPUT_FORMAT=pcm                      # Output codec format
CODEC_QUALITY=high                           # Codec quality

# Audio Normalization
AUDIO_NORMALIZATION_ENABLED=true             # Enable audio normalization
AUDIO_NORMALIZATION_LEVEL=0.8                # Normalization level
AUDIO_NORMALIZATION_CLIPPING=false           # Enable clipping protection
```

### Testing Configuration

```bash
# Contract Testing
CONTRACT_TESTING_ENABLED=true                # Enable contract testing
CONTRACT_TEST_TIMEOUT_MS=30000               # Contract test timeout
CONTRACT_TEST_RETRY_COUNT=3                  # Contract test retry count

# Parity Testing
PARITY_TESTING_ENABLED=true                  # Enable parity testing
PARITY_TEST_DURATION_MS=10000                # Parity test duration
PARITY_TEST_SAMPLE_COUNT=100                 # Parity test sample count
PARITY_TEST_WARMUP_SAMPLES=10                # Parity test warmup samples

# Chaos Testing
CHAOS_TESTING_ENABLED=true                   # Enable chaos testing
CHAOS_TEST_DURATION_MS=30000                 # Chaos test duration
CHAOS_TEST_FAULT_PROBABILITY=0.1             # Chaos test fault probability
CHAOS_TEST_MEMORY_PRESSURE=0.5               # Chaos test memory pressure
```

### Logging Configuration

```bash
# Logging Level
LOG_LEVEL=INFO                               # Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_FORMAT=json                              # Log format (json, text)
LOG_OUTPUT=stdout                            # Log output (stdout, file, syslog)

# Surface Logging
SURFACE_LOG_LEVEL=INFO                       # Surface-specific log level
SURFACE_LOG_ENABLED=true                     # Enable surface logging
SURFACE_LOG_CORRELATION_ID=true             # Enable correlation IDs

# Performance Logging
PERFORMANCE_LOG_ENABLED=true                 # Enable performance logging
PERFORMANCE_LOG_INTERVAL_MS=1000             # Performance log interval
PERFORMANCE_LOG_METRICS=true                 # Enable performance metrics
```

## Configuration Files

### Main Configuration File

```yaml
# config/surfaces.yaml
surfaces:
  discord:
    type: discord
    enabled: true
    config:
      guild_id: "123456789"
      channel_id: "987654321"
      user_id: "111222333"
      audio:
        sample_rate: 16000
        channels: 1
        bit_depth: 16
        frame_size_ms: 20
      control:
        wake_words: ["hey assistant", "ok assistant"]
        barge_in_enabled: true
        wake_word_confidence_threshold: 0.8
      lifecycle:
        auto_reconnect: true
        health_check_interval_ms: 30000
        connection_timeout_ms: 10000
        reconnect_delay_ms: 2000
        max_reconnect_attempts: 5

  webrtc:
    type: webrtc
    enabled: false
    config:
      server_url: "wss://webrtc.example.com"
      room_id: "voice_room_123"
      user_id: "user_456"
      audio:
        sample_rate: 16000
        channels: 1
        bit_depth: 16
      control:
        wake_words: ["hey assistant"]
        barge_in_enabled: true
      lifecycle:
        auto_reconnect: true
        health_check_interval_ms: 30000

# Global Settings
global:
  audio:
    default_sample_rate: 16000
    default_channels: 1
    default_bit_depth: 16
    latency_target_ms: 50
    buffer_size: 1024
  
  control:
    default_wake_words: ["hey assistant", "ok assistant"]
    default_barge_in_enabled: true
    event_timeout_ms: 1000
    event_retry_count: 3
  
  lifecycle:
    default_auto_reconnect: true
    default_health_check_interval_ms: 30000
    default_connection_timeout_ms: 10000
    default_reconnect_delay_ms: 2000
    default_max_reconnect_attempts: 5
  
  testing:
    contract_test_timeout_ms: 30000
    parity_test_duration_ms: 10000
    chaos_test_duration_ms: 30000
    test_sample_count: 100
    test_warmup_samples: 10
```

### Environment-Specific Configuration

#### Development Environment


```yaml
# config/development.yaml
surfaces:
  discord:
    config:
      guild_id: "dev_guild_123"
      channel_id: "dev_channel_456"
      user_id: "dev_user_789"
      audio:
        sample_rate: 16000
        quality: "low"  # Lower quality for development
      control:
        wake_words: ["hey dev assistant"]
        barge_in_enabled: true
      lifecycle:
        health_check_interval_ms: 10000  # More frequent checks in dev

global:
  logging:
    level: DEBUG
    format: text
    output: stdout
  
  testing:
    enabled: true
    contract_testing: true
    parity_testing: true
    chaos_testing: false  # Disable chaos testing in dev
```

#### Staging Environment


```yaml
# config/staging.yaml
surfaces:
  discord:
    config:
      guild_id: "staging_guild_123"
      channel_id: "staging_channel_456"
      user_id: "staging_user_789"
      audio:
        sample_rate: 16000
        quality: "medium"
      control:
        wake_words: ["hey staging assistant"]
        barge_in_enabled: true
      lifecycle:
        health_check_interval_ms: 20000

global:
  logging:
    level: INFO
    format: json
    output: file
  
  testing:
    enabled: true
    contract_testing: true
    parity_testing: true
    chaos_testing: true
```

#### Production Environment


```yaml
# config/production.yaml
surfaces:
  discord:
    config:
      guild_id: "prod_guild_123"
      channel_id: "prod_channel_456"
      user_id: "prod_user_789"
      audio:
        sample_rate: 16000
        quality: "high"
      control:
        wake_words: ["hey assistant", "ok assistant"]
        barge_in_enabled: true
      lifecycle:
        health_check_interval_ms: 30000

global:
  logging:
    level: WARNING
    format: json
    output: syslog
  
  testing:
    enabled: false  # Disable testing in production
    contract_testing: false
    parity_testing: false
    chaos_testing: false
```

## Docker Configuration

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  discord-voice-bot:
    build: .
    environment:
    -  USE_NEW_ARCHITECTURE=true
    -  SURFACE_TYPE=discord
    -  DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN}
    -  DISCORD_GUILD_ID=${DISCORD_GUILD_ID}
    -  DISCORD_CHANNEL_ID=${DISCORD_CHANNEL_ID}
    -  AUDIO_SAMPLE_RATE=16000
    -  AUDIO_CHANNELS=1
    -  AUDIO_BIT_DEPTH=16
    -  LOG_LEVEL=INFO
    volumes:
    -  ./config:/app/config
    -  ./logs:/app/logs
    depends_on:
    -  stt-service
    -  tts-service
    -  orchestrator-service

  stt-service:
    build: ./services/stt
    environment:
    -  STT_MODEL_NAME=base
    -  STT_LANGUAGE=en
    -  STT_ENABLE_VAD=true
    ports:
    -  "8001:8000"

  tts-service:
    build: ./services/tts
    environment:
    -  TTS_MODEL_NAME=piper
    -  TTS_VOICE=default
    -  TTS_LANGUAGE=en
    ports:
    -  "8002:8000"

  orchestrator-service:
    build: ./services/orchestrator
    environment:
    -  ORCHESTRATOR_URL=http://localhost:8000
    -  SESSION_BROKER_URL=http://localhost:8003
    -  POLICY_ENGINE_URL=http://localhost:8004
    ports:
    -  "8000:8000"
```

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
RUN mkdir -p logs config

# Set environment variables
ENV PYTHONPATH=/app
ENV USE_NEW_ARCHITECTURE=true

# Expose ports
EXPOSE 8000

# Run application
CMD ["python", "-m", "services.discord.bot"]
```

## Kubernetes Configuration

### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: discord-voice-bot
spec:
  replicas: 3
  selector:
    matchLabels:
      app: discord-voice-bot
  template:
    metadata:
      labels:
        app: discord-voice-bot
    spec:
      containers:
    -  name: discord-voice-bot
        image: discord-voice-bot:latest
        env:
        -  name: USE_NEW_ARCHITECTURE
          value: "true"
        -  name: SURFACE_TYPE
          value: "discord"
        -  name: DISCORD_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: discord-secrets
              key: bot-token
        -  name: DISCORD_GUILD_ID
          value: "123456789"
        -  name: DISCORD_CHANNEL_ID
          value: "987654321"
        -  name: AUDIO_SAMPLE_RATE
          value: "16000"
        -  name: AUDIO_CHANNELS
          value: "1"
        -  name: AUDIO_BIT_DEPTH
          value: "16"
        -  name: LOG_LEVEL
          value: "INFO"
        volumeMounts:
        -  name: config
          mountPath: /app/config
        -  name: logs
          mountPath: /app/logs
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
      volumes:
    -  name: config
        configMap:
          name: discord-config
    -  name: logs
        emptyDir: {}
```

### ConfigMap

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: discord-config
data:
  surfaces.yaml: |
    surfaces:
      discord:
        type: discord
        enabled: true
        config:
          guild_id: "123456789"
          channel_id: "987654321"
          user_id: "111222333"
          audio:
            sample_rate: 16000
            channels: 1
            bit_depth: 16
          control:
            wake_words: ["hey assistant", "ok assistant"]
            barge_in_enabled: true
          lifecycle:
            auto_reconnect: true
            health_check_interval_ms: 30000
```

### Secret

```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: discord-secrets
type: Opaque
data:
  bot-token: <base64-encoded-bot-token>
```

## Monitoring Configuration

### Health Checks

```yaml
# monitoring/health-checks.yaml
health_checks:
  surface_lifecycle:
    endpoint: /health/surface
    timeout_ms: 5000
    interval_ms: 30000
    retry_count: 3
  
  audio_source:
    endpoint: /health/audio/source
    timeout_ms: 5000
    interval_ms: 30000
    retry_count: 3
  
  audio_sink:
    endpoint: /health/audio/sink
    timeout_ms: 5000
    interval_ms: 30000
    retry_count: 3
  
  control_channel:
    endpoint: /health/control
    timeout_ms: 5000
    interval_ms: 30000
    retry_count: 3
```

### Metrics

```yaml
# monitoring/metrics.yaml
metrics:
  audio_capture:
    latency_ms: true
    throughput_fps: true
    error_rate: true
  
  audio_playback:
    latency_ms: true
    throughput_fps: true
    error_rate: true
  
  event_processing:
    latency_ms: true
    throughput_eps: true
    error_rate: true
  
  connection:
    latency_ms: true
    success_rate: true
    error_rate: true
```

## Security Configuration

### Authentication

```yaml
# security/auth.yaml
authentication:
  discord:
    token: "${DISCORD_BOT_TOKEN}"
    permissions: ["VOICE_CONNECT", "VOICE_SPEAK", "VOICE_USE_VAD"]
  
  webrtc:
    server_url: "${WEBRTC_SERVER_URL}"
    api_key: "${WEBRTC_API_KEY}"
    permissions: ["AUDIO_CAPTURE", "AUDIO_PLAYBACK"]
```

### Encryption

```yaml
# security/encryption.yaml
encryption:
  audio:
    enabled: true
    algorithm: "AES-256-GCM"
    key_rotation_interval_ms: 3600000  # 1 hour
  
  events:
    enabled: true
    algorithm: "AES-256-GCM"
    key_rotation_interval_ms: 3600000  # 1 hour
  
  control:
    enabled: true
    algorithm: "AES-256-GCM"
    key_rotation_interval_ms: 3600000  # 1 hour
```

## Troubleshooting

### Common Configuration Issues

- **Audio Quality Issues**
  -  Check sample rate configuration
  -  Verify bit depth settings
  -  Review audio buffer size

- **Connection Problems**
  -  Validate authentication tokens
  -  Check network connectivity
  -  Review timeout settings

- **Performance Issues**
  -  Adjust buffer sizes
  -  Review latency targets
  -  Check resource limits

- **Event Processing Errors**
  -  Verify event routing configuration
  -  Check event timeout settings
  -  Review retry configurations

### Configuration Validation

```bash
# Validate configuration
python -m services.common.config.validate

# Test surface configuration
python -m services.common.config.test_surfaces

# Check environment variables
python -m services.common.config.check_env
```

### Configuration Testing

```bash
# Run configuration tests
python -m pytest tests/config/ -v

# Test specific surface
python -m pytest tests/config/test_discord_config.py -v

# Test environment variables
python -m pytest tests/config/test_env_vars.py -v
```
