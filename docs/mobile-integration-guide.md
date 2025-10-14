# Mobile Voice Assistant Integration Guide

This guide provides step-by-step instructions for setting up and running the mobile voice assistant integration.

## Overview

The mobile voice assistant integration extends the existing Discord voice lab with cross-platform mobile support using React Native and LiveKit for WebRTC transport. The system reuses the existing STT, TTS, and orchestrator services while adding mobile-specific components.

## Architecture

```
Mobile App (React Native) ←→ LiveKit Room ←→ LiveKit Agent ←→ STT/TTS/Orchestrator
```

## Prerequisites

### Development Environment
- Node.js 16+ and npm/yarn
- React Native CLI
- Android Studio (for Android development)
- Xcode (for iOS development)
- Python 3.11+ (for backend services)
- Docker and Docker Compose

### Services
- LiveKit server (self-hosted or cloud)
- Existing Discord voice lab services (STT, TTS, orchestrator)

## Setup Instructions

### 1. Backend Services

#### 1.1 Update Docker Compose

Add the LiveKit agent service to your `docker-compose.yml`:

```yaml
services:
  # ... existing services ...
  
  livekit-agent:
    build:
      context: .
      dockerfile: services/livekit/Dockerfile
    image: discord-voice-lab/livekit-agent:latest
    ports:
      - "8080:8080"
    env_file:
      - ./.env.common
      - ./.env.docker
      - ./services/livekit/.env.service
    volumes:
      - ./debug:/app/debug
    depends_on:
      - stt
      - orch
      - tts
    restart: unless-stopped
```

#### 1.2 Configure Environment

Create `services/livekit/.env.service`:

```bash
# LiveKit configuration
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# Service URLs
STT_BASE_URL=http://stt:9000
TTS_BASE_URL=http://tts:7000
ORCHESTRATOR_BASE_URL=http://orch:8000

# Audio processing
CANONICAL_SAMPLE_RATE=16000
CANONICAL_FRAME_MS=20
OPUS_SAMPLE_RATE=48000

# Session management
MAX_SESSION_DURATION_MINUTES=30
WAKE_COOLDOWN_MS=1000
VAD_TIMEOUT_MS=2000
ENDPOINTING_TIMEOUT_MS=5000

# Barge-in configuration
BARGE_IN_ENABLED=true
BARGE_IN_PAUSE_DELAY_MS=250
MAX_PAUSE_DURATION_MS=10000

# Quality targets
TARGET_RTT_MEDIAN_MS=400
TARGET_RTT_P95_MS=650
MAX_PACKET_LOSS_PERCENT=10.0
MAX_JITTER_MS=80.0

# Logging
LOG_LEVEL=info
LOG_JSON=true

# Authentication
AUTH_TOKEN=changeme

# Timeouts
STT_TIMEOUT=45
TTS_TIMEOUT=30
ORCHESTRATOR_TIMEOUT=60
```

#### 1.3 Start Backend Services

```bash
# Start all services including LiveKit agent
make run

# Check logs
make logs SERVICE=livekit-agent
```

### 2. Mobile App Setup

#### 2.1 Install Dependencies

```bash
cd mobile-app
npm install
```

#### 2.2 Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_TOKEN=your-room-token
ROOM_NAME=voice-assistant

# Service URLs (for direct API calls if needed)
STT_BASE_URL=http://localhost:9000
TTS_BASE_URL=http://localhost:7000
ORCHESTRATOR_BASE_URL=http://localhost:8000

# Audio Configuration
AUDIO_SAMPLE_RATE=16000
AUDIO_FRAME_MS=20
AUDIO_CHANNELS=1
AUDIO_BIT_DEPTH=16

# Wake Word Configuration
WAKE_WORD_ENABLED=true
WAKE_WORD_PHRASES=hey atlas,ok atlas
WAKE_WORD_THRESHOLD=0.5
WAKE_WORD_COOLDOWN_MS=1000

# VAD Configuration
VAD_ENABLED=true
VAD_AGGRESSIVENESS=2
VAD_TIMEOUT_MS=2000
VAD_PADDING_MS=200

# UI Configuration
UI_THEME=dark
UI_ANIMATIONS_ENABLED=true
UI_DEBUG_MODE=false

# Debug Configuration
DEBUG_ENABLED=false
DEBUG_LOG_LEVEL=info
DEBUG_SAVE_AUDIO=false
```

#### 2.3 iOS Setup

```bash
cd ios
pod install
cd ..
```

#### 2.4 Android Setup

No additional setup required for Android.

### 3. LiveKit Server Setup

#### 3.1 Self-Hosted LiveKit

```bash
# Using Docker
docker run --rm -p 7880:7880 -p 7881:7881/udp \
  -e LIVEKIT_KEYS="devkey: devsecret" \
  livekit/livekit-server:latest --dev
```

#### 3.2 Generate Room Token

Use the LiveKit CLI or API to generate room tokens:

```bash
# Install LiveKit CLI
npm install -g @livekit/cli

# Generate token
livekit-cli create-token \
  --api-key devkey \
  --api-secret devsecret \
  --room voice-assistant \
  --identity mobile-user \
  --valid-for 1h
```

### 4. Running the Application

#### 4.1 Start Backend Services

```bash
# Start all services
make run

# Verify LiveKit agent is running
curl http://localhost:8080/health
```

#### 4.2 Start Mobile App

```bash
# Start Metro bundler
npm start

# Run on iOS
npm run ios

# Run on Android
npm run android
```

## Configuration

### Audio Processing

The system uses a canonical audio format:
- **Sample Rate:** 16 kHz (STT-optimized)
- **Channels:** Mono
- **Bit Depth:** 16-bit
- **Frame Size:** 20 ms (320 samples)

### Wake Word Detection

Configure wake word detection in the mobile app:

```typescript
const wakeWordConfig = {
  enabled: true,
  phrases: ['hey atlas', 'ok atlas'],
  threshold: 0.5,
  cooldownMs: 1000,
};
```

### VAD Configuration

Voice Activity Detection settings:

```typescript
const vadConfig = {
  enabled: true,
  aggressiveness: 2, // 0-3, higher = more aggressive
  timeoutMs: 2000,
  paddingMs: 200,
  minSpeechDurationMs: 300,
  maxSilenceDurationMs: 1000,
};
```

## Usage

### Basic Usage

1. **Connect:** Tap the main button to connect to the voice assistant
2. **Speak:** The app will automatically detect speech and transcribe it
3. **Listen:** Responses will be played through the device speakers
4. **Interrupt:** Tap the interrupt button during responses to barge in

### Push-to-Talk Mode

1. **Enable PTT:** Disable wake word detection in settings
2. **Hold to Talk:** Press and hold the main button while speaking
3. **Release:** Release the button to send the audio for processing

### Audio Routing

- **Speaker:** Audio plays through device speakers
- **Earpiece:** Audio plays through earpiece (phone calls)
- **Bluetooth:** Audio plays through connected Bluetooth device

## Troubleshooting

### Common Issues

#### Connection Issues
- Verify LiveKit server is running and accessible
- Check network connectivity and firewall settings
- Ensure room token is valid and not expired

#### Audio Issues
- Check microphone permissions
- Verify audio session configuration
- Test with different audio routes

#### Performance Issues
- Monitor telemetry data for network quality
- Check device battery and thermal state
- Adjust VAD and wake word sensitivity

### Debug Mode

Enable debug mode to see detailed logs and telemetry:

```bash
# In .env file
DEBUG_ENABLED=true
DEBUG_LOG_LEVEL=debug
DEBUG_SAVE_AUDIO=true
```

### Logs

View logs for different components:

```bash
# Backend services
make logs SERVICE=livekit-agent

# Mobile app (React Native)
npx react-native log-ios
npx react-native log-android
```

## Testing

### Unit Tests

```bash
# Run mobile app tests
npm test

# Run backend tests
make test
```

### Integration Tests

```bash
# Test end-to-end flow
npm run test:integration
```

### Performance Tests

```bash
# Test latency and quality
npm run test:performance
```

## Deployment

### Production Configuration

1. **Update environment variables** with production values
2. **Configure LiveKit server** with proper SSL certificates
3. **Set up monitoring** and alerting
4. **Configure CDN** for static assets

### Security Considerations

- Use HTTPS/WSS for all connections
- Rotate API keys regularly
- Implement proper authentication
- Encrypt sensitive data at rest

## Monitoring

### Metrics

The system provides comprehensive telemetry:

- **Network:** RTT, packet loss, jitter, bitrate
- **Audio:** VAD confidence, wake word detection
- **Session:** Duration, state transitions, errors
- **Device:** Battery, thermal state, memory usage

### Alerts

Set up alerts for:
- High latency (> 650ms p95)
- High packet loss (> 10%)
- Service errors
- Session failures

## Support

For issues and questions:

1. Check the troubleshooting section
2. Review logs and telemetry data
3. Consult the API documentation
4. Open an issue in the repository

## Contributing

See the main repository's contributing guidelines for information on:

- Code style and formatting
- Testing requirements
- Pull request process
- Documentation standards