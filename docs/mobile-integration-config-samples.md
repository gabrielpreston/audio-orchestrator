# Mobile Voice Assistant Configuration Samples

This document provides configuration examples for the mobile voice assistant integration.

## Environment Configuration

### Backend Services (.env files)

#### services/livekit/.env.service

```bash
# LiveKit agent service configuration

# Service configuration
SERVICE_NAME=livekit-agent
PORT=8080
HOST=0.0.0.0

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

# Debug
LIVEKIT_DEBUG_SAVE=false
DEBUG_SAVE_DIR=/app/debug

# Authentication
AUTH_TOKEN=changeme

# Timeouts
STT_TIMEOUT=45
TTS_TIMEOUT=30
ORCHESTRATOR_TIMEOUT=60

# Retry configuration
MAX_RETRIES=3
RETRY_DELAY_MS=1000

# Telemetry
TELEMETRY_INTERVAL_MS=5000
METRICS_ENABLED=true
```

#### mobile-app/.env

```bash
# Mobile Voice Assistant Configuration

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

# Performance Configuration
MAX_SESSION_DURATION_MINUTES=30
AUDIO_BUFFER_SIZE_MS=100
NETWORK_TIMEOUT_MS=30000
RETRY_ATTEMPTS=3
```

## LiveKit Configuration

### LiveKit Server Configuration (livekit.yaml)

```yaml
port: 7880
rtc:
  udp_port: 7881
  use_external_ip: false
  stun_servers:
    - stun:stun.l.google.com:19302
    - stun:stun1.l.google.com:19302
  turn_servers:
    - url: turn:your-turn-server.com:3478
      username: your-username
      credential: your-password
  ice_candidate_pool_size: 2
  ice_transport_policy: all
  ice_servers:
    - urls:
        - stun:stun.l.google.com:19302
        - stun:stun1.l.google.com:19302
      username: ""
      credential: ""

keys:
  devkey: devsecret

redis:
  address: localhost:6379
  username: ""
  password: ""
  db: 0

log_level: info
```

### Room Token Generation

```javascript
// Generate room token for mobile app
const { AccessToken } = require('livekit-server-sdk');

const token = new AccessToken('devkey', 'devsecret', {
  identity: 'mobile-user',
  ttl: '1h',
});

token.addGrant({
  room: 'voice-assistant',
  roomJoin: true,
  canPublish: true,
  canSubscribe: true,
  canPublishData: true,
});

const jwt = token.toJwt();
console.log('Room token:', jwt);
```

## Audio Configuration

### Audio Session Configuration (iOS)

```swift
// iOS Audio Session Configuration
import AVFoundation

func configureAudioSession() {
    let audioSession = AVAudioSession.sharedInstance()
    
    do {
        try audioSession.setCategory(
            .playAndRecord,
            mode: .voiceChat,
            options: [
                .allowBluetooth,
                .allowBluetoothA2DP,
                .allowAirPlay,
                .defaultToSpeaker
            ]
        )
        
        try audioSession.setActive(true)
    } catch {
        print("Failed to configure audio session: \(error)")
    }
}
```

### Audio Session Configuration (Android)

```java
// Android Audio Session Configuration
import android.media.AudioManager;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;

public class AudioConfig {
    private static final int SAMPLE_RATE = 16000;
    private static final int CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO;
    private static final int AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT;
    
    public static AudioRecord createAudioRecord() {
        int bufferSize = AudioRecord.getMinBufferSize(
            SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT
        );
        
        return new AudioRecord(
            MediaRecorder.AudioSource.MIC,
            SAMPLE_RATE,
            CHANNEL_CONFIG,
            AUDIO_FORMAT,
            bufferSize
        );
    }
}
```

## Wake Word Configuration

### Porcupine Wake Word Engine

```javascript
// Wake word detection configuration
const wakeWordConfig = {
    enabled: true,
    phrases: ['hey atlas', 'ok atlas'],
    threshold: 0.5,
    cooldownMs: 1000,
    modelPath: 'path/to/porcupine/model',
    keywords: [
        {
            name: 'hey atlas',
            sensitivity: 0.5,
            modelPath: 'path/to/hey-atlas.ppn'
        },
        {
            name: 'ok atlas',
            sensitivity: 0.5,
            modelPath: 'path/to/ok-atlas.ppn'
        }
    ]
};
```

### Open Wake Word Configuration

```javascript
// Alternative wake word engine
const openWakeWordConfig = {
    enabled: true,
    modelPath: 'path/to/openwakeword/model',
    threshold: 0.5,
    cooldownMs: 1000,
    phrases: ['hey atlas', 'ok atlas']
};
```

## VAD Configuration

### WebRTC VAD Configuration

```javascript
// Voice Activity Detection settings
const vadConfig = {
    enabled: true,
    aggressiveness: 2, // 0-3, higher = more aggressive
    timeoutMs: 2000,
    paddingMs: 200,
    minSpeechDurationMs: 300,
    maxSilenceDurationMs: 1000,
    sampleRate: 16000,
    frameSize: 320, // 20ms at 16kHz
    channels: 1
};
```

### Custom VAD Configuration

```javascript
// Custom VAD implementation
const customVADConfig = {
    enabled: true,
    algorithm: 'energy', // 'energy', 'spectral', 'neural'
    energyThreshold: 0.01,
    spectralThreshold: 0.5,
    neuralModelPath: 'path/to/vad/model',
    frameSize: 320,
    sampleRate: 16000
};
```

## Network Configuration

### WebRTC ICE Servers

```javascript
// ICE server configuration for WebRTC
const iceServers = [
    {
        urls: 'stun:stun.l.google.com:19302'
    },
    {
        urls: 'stun:stun1.l.google.com:19302'
    },
    {
        urls: 'turn:your-turn-server.com:3478',
        username: 'your-username',
        credential: 'your-password'
    }
];

const rtcConfig = {
    iceServers: iceServers,
    iceCandidatePoolSize: 10,
    iceTransportPolicy: 'all',
    bundlePolicy: 'max-bundle',
    rtcpMuxPolicy: 'require'
};
```

### Network Quality Monitoring

```javascript
// Network quality thresholds
const networkQualityConfig = {
    rtt: {
        excellent: 100,
        good: 200,
        fair: 400,
        poor: 650
    },
    packetLoss: {
        excellent: 0,
        good: 1,
        fair: 3,
        poor: 10
    },
    jitter: {
        excellent: 10,
        good: 20,
        fair: 50,
        poor: 80
    },
    bitrate: {
        minimum: 32000,
        target: 64000,
        maximum: 128000
    }
};
```

## UI Configuration

### Theme Configuration

```javascript
// UI theme settings
const themeConfig = {
    light: {
        primary: '#4ECDC4',
        secondary: '#45B7B8',
        background: '#FFFFFF',
        surface: '#F8F9FA',
        text: '#2C3E50',
        textSecondary: '#7F8C8D',
        error: '#E74C3C',
        warning: '#F39C12',
        success: '#27AE60'
    },
    dark: {
        primary: '#4ECDC4',
        secondary: '#45B7B8',
        background: '#2C3E50',
        surface: '#34495E',
        text: '#FFFFFF',
        textSecondary: '#BDC3C7',
        error: '#E74C3C',
        warning: '#F39C12',
        success: '#27AE60'
    }
};
```

### Animation Configuration

```javascript
// Animation settings
const animationConfig = {
    enabled: true,
    duration: {
        short: 150,
        medium: 300,
        long: 500
    },
    easing: {
        easeIn: 'ease-in',
        easeOut: 'ease-out',
        easeInOut: 'ease-in-out'
    },
    spring: {
        tension: 300,
        friction: 30
    }
};
```

## Debug Configuration

### Debug Settings

```javascript
// Debug configuration
const debugConfig = {
    enabled: false,
    logLevel: 'info', // 'debug', 'info', 'warn', 'error'
    saveAudio: false,
    saveTranscripts: false,
    saveTelemetry: true,
    maxLogSize: '10MB',
    logRotation: true,
    consoleOutput: true,
    fileOutput: false,
    remoteLogging: false
};
```

### Performance Monitoring

```javascript
// Performance monitoring settings
const performanceConfig = {
    enabled: true,
    metrics: {
        latency: true,
        memory: true,
        cpu: true,
        battery: true,
        thermal: true,
        network: true
    },
    sampling: {
        interval: 1000, // ms
        duration: 30000, // ms
        maxSamples: 1000
    },
    thresholds: {
        latency: 400, // ms
        memory: 100, // MB
        cpu: 80, // %
        battery: 20, // %
        thermal: 'serious'
    }
};
```

## Security Configuration

### Authentication

```javascript
// Authentication configuration
const authConfig = {
    provider: 'jwt', // 'jwt', 'oauth', 'custom'
    jwt: {
        secret: 'your-secret-key',
        expiresIn: '1h',
        issuer: 'voice-assistant',
        audience: 'mobile-app'
    },
    oauth: {
        clientId: 'your-client-id',
        clientSecret: 'your-client-secret',
        redirectUri: 'your-redirect-uri',
        scopes: ['voice', 'profile']
    },
    rateLimiting: {
        enabled: true,
        maxRequests: 100,
        windowMs: 60000
    }
};
```

### Data Encryption

```javascript
// Data encryption settings
const encryptionConfig = {
    enabled: true,
    algorithm: 'AES-256-GCM',
    keyDerivation: 'PBKDF2',
    iterations: 100000,
    saltLength: 32,
    ivLength: 16,
    tagLength: 16,
    keyStorage: 'secure', // 'secure', 'memory', 'file'
    keyRotation: {
        enabled: true,
        interval: '24h'
    }
};
```

## Production Configuration

### Production Environment Variables

```bash
# Production configuration
NODE_ENV=production
LOG_LEVEL=warn
DEBUG_ENABLED=false
LIVEKIT_URL=wss://your-production-server.com
LIVEKIT_API_KEY=your-production-key
LIVEKIT_API_SECRET=your-production-secret
AUTH_TOKEN=your-production-token
```

### Monitoring Configuration

```javascript
// Production monitoring
const monitoringConfig = {
    enabled: true,
    provider: 'datadog', // 'datadog', 'newrelic', 'custom'
    apiKey: 'your-monitoring-api-key',
    serviceName: 'mobile-voice-assistant',
    environment: 'production',
    tags: {
        version: '1.0.0',
        region: 'us-east-1',
        team: 'voice-assistant'
    },
    alerts: {
        latency: 650, // ms
        errorRate: 5, // %
        availability: 99.9 // %
    }
};
```

## Testing Configuration

### Test Environment

```javascript
// Testing configuration
const testConfig = {
    environment: 'test',
    mockServices: true,
    mockAudio: true,
    mockNetwork: true,
    testData: {
        audioFiles: 'path/to/test/audio',
        transcripts: 'path/to/test/transcripts',
        responses: 'path/to/test/responses'
    },
    timeouts: {
        connection: 5000,
        audio: 10000,
        response: 30000
    }
};
```

### Load Testing

```javascript
// Load testing configuration
const loadTestConfig = {
    enabled: false,
    users: 100,
    duration: 300, // seconds
    rampUp: 60, // seconds
    scenarios: {
        normal: 70, // %
        heavy: 20, // %
        burst: 10 // %
    },
    metrics: {
        latency: true,
        throughput: true,
        errorRate: true,
        resourceUsage: true
    }
};
```

These configuration samples provide comprehensive examples for setting up the mobile voice assistant integration in various environments and use cases.
