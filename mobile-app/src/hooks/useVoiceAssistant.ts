/**
 * Custom hook for voice assistant functionality
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  UseVoiceAssistant,
  LiveKitConfig,
  AudioRoute,
  AudioInput,
  ControlMessage,
  MessageType,
  SessionState,
  EndpointingState,
  PlaybackAction,
  AppError,
  VADResult,
  WakeWordResult,
  AudioFrame,
  TelemetryData,
} from '../types';
import { LiveKitService } from '../services/LiveKitService';
import { AudioService } from '../services/AudioService';
import { VADConfig, WakeWordConfig } from '../types';

interface UseVoiceAssistantProps {
  livekitConfig: LiveKitConfig;
  vadConfig: VADConfig;
  wakeWordConfig: WakeWordConfig;
  onError?: (error: AppError) => void;
  onTranscript?: (transcript: string, isFinal: boolean) => void;
  onResponse?: (response: string) => void;
  onWakeWord?: (result: WakeWordResult) => void;
  onVADResult?: (result: VADResult) => void;
  onTelemetry?: (data: TelemetryData) => void;
}

export const useVoiceAssistant = ({
  livekitConfig,
  vadConfig,
  wakeWordConfig,
  onError,
  onTranscript,
  onResponse,
  onWakeWord,
  onVADResult,
  onTelemetry,
}: UseVoiceAssistantProps): UseVoiceAssistant => {
  // State
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isResponding, setIsResponding] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [currentTranscript, setCurrentTranscript] = useState('');
  const [lastResponse, setLastResponse] = useState('');
  const [error, setError] = useState<AppError | null>(null);
  const [sessionDuration, setSessionDuration] = useState(0);
  const [audioRoute, setAudioRoute] = useState<AudioRoute>(AudioRoute.SPEAKER);
  const [audioInput, setAudioInput] = useState<AudioInput>(AudioInput.BUILT_IN);

  // Refs
  const livekitServiceRef = useRef<LiveKitService | null>(null);
  const audioServiceRef = useRef<AudioService | null>(null);
  const sessionStartTimeRef = useRef<number>(0);
  const telemetryIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize services
  useEffect(() => {
    const initializeServices = async () => {
      try {
        // Initialize LiveKit service
        livekitServiceRef.current = new LiveKitService();
        
        // Initialize audio service
        audioServiceRef.current = new AudioService(vadConfig, wakeWordConfig);
        await audioServiceRef.current.initialize();

        // Set up event handlers
        setupEventHandlers();

        console.log('Voice assistant services initialized');
      } catch (err) {
        handleError({
          code: 'INITIALIZATION_ERROR',
          message: `Failed to initialize services: ${err}`,
          recoverable: true,
          timestamp: Date.now(),
        });
      }
    };

    initializeServices();

    return () => {
      cleanup();
    };
  }, []);

  // Session duration timer
  useEffect(() => {
    if (isConnected && sessionStartTimeRef.current > 0) {
      const interval = setInterval(() => {
        setSessionDuration(Math.floor((Date.now() - sessionStartTimeRef.current) / 1000));
      }, 1000);

      return () => clearInterval(interval);
    }
  }, [isConnected]);

  // Telemetry interval
  useEffect(() => {
    if (isConnected && livekitServiceRef.current) {
      telemetryIntervalRef.current = setInterval(async () => {
        try {
          const telemetryData = await livekitServiceRef.current!.getTelemetryData();
          onTelemetry?.(telemetryData);
        } catch (err) {
          console.error('Failed to get telemetry data:', err);
        }
      }, 5000);

      return () => {
        if (telemetryIntervalRef.current) {
          clearInterval(telemetryIntervalRef.current);
        }
      };
    }
  }, [isConnected, onTelemetry]);

  const setupEventHandlers = () => {
    if (!livekitServiceRef.current || !audioServiceRef.current) return;

    // LiveKit event handlers
    livekitServiceRef.current.onConnectionStateChange((state) => {
      setIsConnected(state === 'connected');
    });

    livekitServiceRef.current.onControlMessage((message) => {
      handleControlMessage(message);
    });

    // Audio event handlers
    audioServiceRef.current.onVADResult((result) => {
      onVADResult?.(result);
      handleVADResult(result);
    });

    audioServiceRef.current.onWakeWordResult((result) => {
      onWakeWord?.(result);
      handleWakeWordResult(result);
    });

    audioServiceRef.current.onAudioFrame((frame) => {
      handleAudioFrame(frame);
    });
  };

  const handleControlMessage = (message: ControlMessage) => {
    switch (message.messageType) {
      case MessageType.TRANSCRIPT_PARTIAL:
        setCurrentTranscript(message.payload.text);
        onTranscript?.(message.payload.text, false);
        break;

      case MessageType.TRANSCRIPT_FINAL:
        setCurrentTranscript(message.payload.text);
        onTranscript?.(message.payload.text, true);
        break;

      case MessageType.ENDPOINTING:
        const state = message.payload.state as EndpointingState;
        setIsProcessing(state === EndpointingState.PROCESSING);
        setIsResponding(state === EndpointingState.RESPONDING);
        break;

      case MessageType.PLAYBACK_CONTROL:
        const action = message.payload.action as PlaybackAction;
        if (action === PlaybackAction.PAUSE) {
          setIsResponding(false);
        } else if (action === PlaybackAction.RESUME) {
          setIsResponding(true);
        }
        break;

      case MessageType.ERROR:
        handleError({
          code: message.payload.code,
          message: message.payload.message,
          recoverable: message.payload.recoverable,
          timestamp: message.timestamp,
        });
        break;

      case MessageType.TELEMETRY_SNAPSHOT:
        const telemetryData: TelemetryData = {
          rttMs: message.payload.rtt_ms,
          packetLossPercent: message.payload.pl_percent,
          jitterMs: message.payload.jitter_ms,
          bitrate: 0,
          batteryLevel: 0,
          thermalState: 'normal',
          memoryUsage: 0,
          cpuUsage: 0,
        };
        onTelemetry?.(telemetryData);
        break;
    }
  };

  const handleVADResult = (result: VADResult) => {
    if (result.isSpeech && !isRecording) {
      startRecording();
    } else if (!result.isSpeech && isRecording) {
      stopRecording();
    }
  };

  const handleWakeWordResult = (result: WakeWordResult) => {
    if (result.confidence >= wakeWordConfig.threshold) {
      startRecording();
    }
  };

  const handleAudioFrame = (frame: AudioFrame) => {
    // Send audio frame to LiveKit service
    if (livekitServiceRef.current && isConnected) {
      // This would typically involve sending the frame through WebRTC
      // For now, we'll just log it
      console.log('Audio frame processed:', frame.sequenceNumber);
    }
  };

  const handleError = (error: AppError) => {
    setError(error);
    onError?.(error);
  };

  const connect = useCallback(async (config: LiveKitConfig) => {
    try {
      if (!livekitServiceRef.current) {
        throw new Error('LiveKit service not initialized');
      }

      await livekitServiceRef.current.connect(config);
      sessionStartTimeRef.current = Date.now();
      setSessionDuration(0);
      setError(null);
    } catch (err) {
      handleError({
        code: 'CONNECTION_ERROR',
        message: `Failed to connect: ${err}`,
        recoverable: true,
        timestamp: Date.now(),
      });
    }
  }, []);

  const disconnect = useCallback(async () => {
    try {
      if (livekitServiceRef.current) {
        await livekitServiceRef.current.disconnect();
      }
      if (audioServiceRef.current) {
        await audioServiceRef.current.stopRecording();
      }
      sessionStartTimeRef.current = 0;
      setSessionDuration(0);
      setIsRecording(false);
      setIsProcessing(false);
      setIsResponding(false);
    } catch (err) {
      handleError({
        code: 'DISCONNECTION_ERROR',
        message: `Failed to disconnect: ${err}`,
        recoverable: true,
        timestamp: Date.now(),
      });
    }
  }, []);

  const startRecording = useCallback(async () => {
    try {
      if (!audioServiceRef.current) {
        throw new Error('Audio service not initialized');
      }

      await audioServiceRef.current.startRecording();
      setIsRecording(true);
      setCurrentTranscript('');
    } catch (err) {
      handleError({
        code: 'RECORDING_ERROR',
        message: `Failed to start recording: ${err}`,
        recoverable: true,
        timestamp: Date.now(),
      });
    }
  }, []);

  const stopRecording = useCallback(async () => {
    try {
      if (audioServiceRef.current) {
        await audioServiceRef.current.stopRecording();
      }
      setIsRecording(false);
    } catch (err) {
      handleError({
        code: 'RECORDING_ERROR',
        message: `Failed to stop recording: ${err}`,
        recoverable: true,
        timestamp: Date.now(),
      });
    }
  }, []);

  const toggleMute = useCallback(async () => {
    try {
      if (isMuted) {
        await startRecording();
      } else {
        await stopRecording();
      }
      setIsMuted(!isMuted);
    } catch (err) {
      handleError({
        code: 'MUTE_ERROR',
        message: `Failed to toggle mute: ${err}`,
        recoverable: true,
        timestamp: Date.now(),
      });
    }
  }, [isMuted, startRecording, stopRecording]);

  const changeAudioRoute = useCallback(async (route: AudioRoute) => {
    try {
      if (audioServiceRef.current) {
        await audioServiceRef.current.changeAudioRoute(route);
      }
      setAudioRoute(route);
    } catch (err) {
      handleError({
        code: 'AUDIO_ROUTE_ERROR',
        message: `Failed to change audio route: ${err}`,
        recoverable: true,
        timestamp: Date.now(),
      });
    }
  }, []);

  const changeAudioInput = useCallback(async (input: AudioInput) => {
    try {
      if (audioServiceRef.current) {
        await audioServiceRef.current.changeAudioInput(input);
      }
      setAudioInput(input);
    } catch (err) {
      handleError({
        code: 'AUDIO_INPUT_ERROR',
        message: `Failed to change audio input: ${err}`,
        recoverable: true,
        timestamp: Date.now(),
      });
    }
  }, []);

  const sendBargeInRequest = useCallback(async (reason: string) => {
    try {
      if (!livekitServiceRef.current) {
        throw new Error('LiveKit service not initialized');
      }

      const message: ControlMessage = {
        messageType: MessageType.BARGE_IN_REQUEST,
        timestamp: Date.now(),
        correlationId: 'mobile_' + Date.now(),
        payload: { reason },
      };

      await livekitServiceRef.current.sendControlMessage(message);
    } catch (err) {
      handleError({
        code: 'BARGE_IN_ERROR',
        message: `Failed to send barge-in request: ${err}`,
        recoverable: true,
        timestamp: Date.now(),
      });
    }
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const cleanup = () => {
    if (livekitServiceRef.current) {
      livekitServiceRef.current.destroy();
    }
    if (audioServiceRef.current) {
      audioServiceRef.current.destroy();
    }
    if (telemetryIntervalRef.current) {
      clearInterval(telemetryIntervalRef.current);
    }
  };

  return {
    isConnected,
    isRecording,
    isProcessing,
    isResponding,
    isMuted,
    currentTranscript,
    lastResponse,
    error,
    sessionDuration,
    audioRoute,
    audioInput,
    connect,
    disconnect,
    startRecording,
    stopRecording,
    toggleMute,
    changeAudioRoute,
    changeAudioInput,
    sendBargeInRequest,
    clearError,
  };
};