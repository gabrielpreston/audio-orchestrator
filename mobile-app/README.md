# Mobile Voice Assistant

React Native mobile application for cross-platform voice assistant integration using LiveKit WebRTC transport.

## Features

- **Real-time Voice Processing**: 16kHz PCM audio with 20ms frames
- **WebRTC Integration**: LiveKit for low-latency audio transport
- **Wake Word Detection**: Configurable wake phrase detection
- **Voice Activity Detection**: Automatic speech detection
- **Barge-in Support**: Interrupt TTS during user speech
- **Audio Routing**: Speaker, earpiece, Bluetooth support
- **Cross-platform**: iOS and Android support

## Prerequisites

- Node.js 16+ and npm/yarn
- React Native CLI
- Android Studio (for Android development)
- Xcode (for iOS development)
- LiveKit server instance

## Installation

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **iOS setup** (macOS only):
   ```bash
   cd ios
   pod install
   cd ..
   ```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_TOKEN=your-room-token
ROOM_NAME=voice-assistant

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

## Development

### Running the App

```bash
# Start Metro bundler
npm start

# Run on iOS
npm run ios

# Run on Android
npm run android
```

### Linting and Formatting

```bash
# Run ESLint
npm run lint

# Fix ESLint issues
npm run lint:fix

# Run TypeScript type checking
npm run type-check

# Format code with Prettier
npm run format

# Check formatting
npm run format:check
```

### Testing

```bash
# Run tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run tests with coverage
npm test -- --coverage
```

## Project Structure

```
mobile-app/
├── src/
│   ├── components/          # React components
│   │   ├── VoiceAssistant.tsx
│   │   ├── AudioVisualizer.tsx
│   │   ├── TranscriptDisplay.tsx
│   │   ├── ControlPanel.tsx
│   │   └── TelemetryDisplay.tsx
│   ├── services/            # Service layer
│   │   ├── LiveKitService.ts
│   │   └── AudioService.ts
│   ├── hooks/               # Custom React hooks
│   │   └── useVoiceAssistant.ts
│   ├── types/               # TypeScript type definitions
│   │   └── index.ts
│   └── App.tsx              # Main app component
├── android/                 # Android-specific code
├── ios/                     # iOS-specific code
├── package.json
├── tsconfig.json
├── .eslintrc.js
├── .prettierrc.js
└── README.md
```

## Architecture

### Components

- **VoiceAssistant**: Main application component
- **AudioVisualizer**: Real-time audio visualization
- **TranscriptDisplay**: Speech-to-text display with word timing
- **ControlPanel**: User interaction controls
- **TelemetryDisplay**: Network and device metrics

### Services

- **LiveKitService**: WebRTC connection and data channel management
- **AudioService**: Audio capture, processing, and routing

### Hooks

- **useVoiceAssistant**: Main hook for voice assistant functionality

## Usage

### Basic Usage

1. **Connect**: Tap the main button to connect to the voice assistant
2. **Speak**: The app will automatically detect speech and transcribe it
3. **Listen**: Responses will be played through the device speakers
4. **Interrupt**: Tap the interrupt button during responses to barge in

### Push-to-Talk Mode

1. **Enable PTT**: Disable wake word detection in settings
2. **Hold to Talk**: Press and hold the main button while speaking
3. **Release**: Release the button to send the audio for processing

### Audio Routing

- **Speaker**: Audio plays through device speakers
- **Earpiece**: Audio plays through earpiece (phone calls)
- **Bluetooth**: Audio plays through connected Bluetooth device

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

View logs for different platforms:

```bash
# iOS logs
npx react-native log-ios

# Android logs
npx react-native log-android
```

## Building for Production

### Android

```bash
# Build APK
npm run build:android

# Build AAB (for Play Store)
cd android
./gradlew bundleRelease
```

### iOS

```bash
# Build for iOS
npm run build:ios
```

## Contributing

1. Follow the existing code style and conventions
2. Run linting and formatting before committing
3. Add tests for new functionality
4. Update documentation as needed

### Code Style

- Use TypeScript for all new code
- Follow React Native best practices
- Use functional components with hooks
- Implement proper error handling
- Add JSDoc comments for public APIs

## License

This project is part of the Discord Voice Lab and follows the same license terms.