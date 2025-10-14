/**
 * Type definitions for mobile voice assistant
 */

// Audio processing types
export interface AudioFrame {
  pcmData: Uint8Array;
  sampleRate: number;
  channels: number;
  sampleWidth: number;
  bitDepth: number;
  timestamp: number;
  frameDurationMs: number;
  sequenceNumber: number;
  isSpeech: boolean;
  isEndpoint: boolean;
  confidence: number;
}

export interface AudioSegment {
  audioFrames: AudioFrame[];
  transcript: string;
  words: WordTiming[];
  startTime: number;
  endTime: number;
  confidence: number;
  isFinal: boolean;
}

export interface WordTiming {
  word: string;
  startTime: number;
  endTime: number;
  confidence: number;
}

// Control plane message types
export enum MessageType {
  // Client → Agent
  WAKE_DETECTED = 'wake.detected',
  VAD_START_SPEECH = 'vad.start_speech',
  VAD_END_SPEECH = 'vad.end_speech',
  BARGE_IN_REQUEST = 'barge_in.request',
  SESSION_STATE = 'session.state',
  ROUTE_CHANGE = 'route.change',
  
  // Agent → Client
  PLAYBACK_CONTROL = 'playback.control',
  ENDPOINTING = 'endpointing',
  TRANSCRIPT_PARTIAL = 'transcript.partial',
  TRANSCRIPT_FINAL = 'transcript.final',
  ERROR = 'error',
  TELEMETRY_SNAPSHOT = 'telemetry.snapshot',
}

export interface ControlMessage {
  messageType: MessageType;
  timestamp: number;
  correlationId: string;
  payload: Record<string, any>;
}

// Session state types
export enum SessionState {
  IDLE = 'idle',
  ARMING = 'arming',
  LIVE_LISTEN = 'live_listen',
  PROCESSING = 'processing',
  RESPONDING = 'responding',
  TEARDOWN = 'teardown',
}

export enum EndpointingState {
  LISTENING = 'listening',
  PROCESSING = 'processing',
  RESPONDING = 'responding',
}

export enum PlaybackAction {
  PAUSE = 'pause',
  RESUME = 'resume',
  STOP = 'stop',
}

export enum AudioRoute {
  SPEAKER = 'speaker',
  EARPIECE = 'earpiece',
  BLUETOOTH = 'bt',
}

export enum AudioInput {
  BUILT_IN = 'built_in',
  BLUETOOTH = 'bt',
}

// WebRTC types
export interface WebRTCConfig {
  iceServers: RTCIceServer[];
  sdpSemantics: 'unified-plan' | 'plan-b';
}

export interface LiveKitConfig {
  url: string;
  token: string;
  roomName: string;
}

// Audio session types
export interface AudioSessionConfig {
  category: 'playAndRecord' | 'playback' | 'record';
  mode: 'voiceChat' | 'videoChat' | 'gameChat' | 'videoRecording' | 'measurement';
  options: {
    allowBluetooth: boolean;
    allowBluetoothA2DP: boolean;
    allowAirPlay: boolean;
    allowHapticsAndSystemSoundsDuringRecording: boolean;
    defaultToSpeaker: boolean;
    mixWithOthers: boolean;
    overrideCategoryMixWithOthers: boolean;
    overrideCategoryDefaultToSpeaker: boolean;
    overrideCategoryEnableBluetooth: boolean;
  };
}

// Wake word detection types
export interface WakeWordConfig {
  enabled: boolean;
  phrases: string[];
  threshold: number;
  cooldownMs: number;
  modelPath?: string;
}

export interface WakeWordResult {
  phrase: string;
  confidence: number;
  timestamp: number;
}

// VAD types
export interface VADConfig {
  enabled: boolean;
  aggressiveness: number;
  timeoutMs: number;
  paddingMs: number;
  minSpeechDurationMs: number;
  maxSilenceDurationMs: number;
}

export interface VADResult {
  isSpeech: boolean;
  confidence: number;
  timestamp: number;
  duration?: number;
}

// Telemetry types
export interface TelemetryData {
  rttMs: number;
  packetLossPercent: number;
  jitterMs: number;
  bitrate: number;
  batteryLevel: number;
  thermalState: string;
  memoryUsage: number;
  cpuUsage: number;
}

// Error types
export interface AppError {
  code: string;
  message: string;
  recoverable: boolean;
  timestamp: number;
  context?: Record<string, any>;
}

// UI state types
export interface UIState {
  isConnected: boolean;
  isRecording: boolean;
  isProcessing: boolean;
  isResponding: boolean;
  isMuted: boolean;
  currentTranscript: string;
  lastResponse: string;
  error?: AppError;
  sessionDuration: number;
  audioRoute: AudioRoute;
  audioInput: AudioInput;
}

// Configuration types
export interface AppConfig {
  livekit: LiveKitConfig;
  audio: {
    sampleRate: number;
    frameMs: number;
    channels: number;
    bitDepth: number;
  };
  wakeWord: WakeWordConfig;
  vad: VADConfig;
  ui: {
    theme: 'light' | 'dark';
    animationsEnabled: boolean;
    debugMode: boolean;
  };
  debug: {
    enabled: boolean;
    logLevel: 'debug' | 'info' | 'warn' | 'error';
    saveAudio: boolean;
  };
  performance: {
    maxSessionDurationMinutes: number;
    audioBufferSizeMs: number;
    networkTimeoutMs: number;
    retryAttempts: number;
  };
}

// Service types
export interface STTService {
  transcribe(audioData: Uint8Array, isFinal: boolean): Promise<AudioSegment>;
  startStream(): Promise<string>;
  processFrame(streamId: string, frame: AudioFrame): Promise<AudioSegment | null>;
  flushStream(streamId: string): Promise<AudioSegment | null>;
  stopStream(streamId: string): Promise<void>;
}

export interface TTSService {
  synthesize(text: string, voice?: string): Promise<Uint8Array>;
  startStream(): Promise<string>;
  addTextChunk(streamId: string, text: string): Promise<void>;
  getAudioChunk(streamId: string): Promise<Uint8Array | null>;
  pauseStream(streamId: string): Promise<void>;
  resumeStream(streamId: string): Promise<void>;
  stopStream(streamId: string): Promise<void>;
}

export interface LiveKitService {
  connect(config: LiveKitConfig): Promise<void>;
  disconnect(): Promise<void>;
  publishAudioTrack(track: MediaStreamTrack): Promise<void>;
  subscribeToAudioTrack(callback: (track: MediaStreamTrack) => void): void;
  sendControlMessage(message: ControlMessage): Promise<void>;
  onControlMessage(callback: (message: ControlMessage) => void): void;
  getConnectionState(): RTCPeerConnectionState;
  getStats(): Promise<RTCStatsReport>;
}

// Hook types
export interface UseVoiceAssistant {
  isConnected: boolean;
  isRecording: boolean;
  isProcessing: boolean;
  isResponding: boolean;
  isMuted: boolean;
  currentTranscript: string;
  lastResponse: string;
  error: AppError | null;
  sessionDuration: number;
  audioRoute: AudioRoute;
  audioInput: AudioInput;
  connect: (config: LiveKitConfig) => Promise<void>;
  disconnect: () => Promise<void>;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<void>;
  toggleMute: () => Promise<void>;
  changeAudioRoute: (route: AudioRoute) => Promise<void>;
  changeAudioInput: (input: AudioInput) => Promise<void>;
  sendBargeInRequest: (reason: string) => Promise<void>;
  clearError: () => void;
}

// Component prop types
export interface VoiceAssistantProps {
  config: AppConfig;
  onStateChange?: (state: UIState) => void;
  onError?: (error: AppError) => void;
  onTranscript?: (transcript: string, isFinal: boolean) => void;
  onResponse?: (response: string) => void;
  onWakeWord?: (result: WakeWordResult) => void;
  onVADResult?: (result: VADResult) => void;
  onTelemetry?: (data: TelemetryData) => void;
}

export interface AudioVisualizerProps {
  isActive: boolean;
  level: number;
  color?: string;
  size?: number;
  style?: any;
}

export interface TranscriptDisplayProps {
  transcript: string;
  isFinal: boolean;
  words?: WordTiming[];
  style?: any;
}

export interface ControlPanelProps {
  isConnected: boolean;
  isRecording: boolean;
  isProcessing: boolean;
  isResponding: boolean;
  isMuted: boolean;
  onStartRecording: () => void;
  onStopRecording: () => void;
  onToggleMute: () => void;
  onDisconnect: () => void;
  style?: any;
}

export interface TelemetryDisplayProps {
  data: TelemetryData;
  style?: any;
}