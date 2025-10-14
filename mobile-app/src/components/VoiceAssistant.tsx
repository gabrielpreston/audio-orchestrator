/**
 * Main VoiceAssistant component
 */

import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  Dimensions,
  StatusBar,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'react-native-linear-gradient';
import Icon from 'react-native-vector-icons/MaterialIcons';

import { VoiceAssistantProps, UIState, AppError } from '../types';
import { useVoiceAssistant } from '../hooks/useVoiceAssistant';
import { AudioVisualizer } from './AudioVisualizer';
import { TranscriptDisplay } from './TranscriptDisplay';
import { ControlPanel } from './ControlPanel';
import { TelemetryDisplay } from './TelemetryDisplay';

const { width, height } = Dimensions.get('window');

export const VoiceAssistant: React.FC<VoiceAssistantProps> = ({
  config,
  onStateChange,
  onError,
  onTranscript,
  onResponse,
  onWakeWord,
  onVADResult,
  onTelemetry,
}) => {
  const [uiState, setUIState] = useState<UIState>({
    isConnected: false,
    isRecording: false,
    isProcessing: false,
    isResponding: false,
    isMuted: false,
    currentTranscript: '',
    lastResponse: '',
    sessionDuration: 0,
    audioRoute: 'speaker',
    audioInput: 'built_in',
  });

  const {
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
  } = useVoiceAssistant({
    livekitConfig: config.livekit,
    vadConfig: config.vad,
    wakeWordConfig: config.wakeWord,
    onError: (error) => {
      setUIState(prev => ({ ...prev, error }));
      onError?.(error);
    },
    onTranscript: (transcript, isFinal) => {
      setUIState(prev => ({ ...prev, currentTranscript: transcript }));
      onTranscript?.(transcript, isFinal);
    },
    onResponse: (response) => {
      setUIState(prev => ({ ...prev, lastResponse: response }));
      onResponse?.(response);
    },
    onWakeWord,
    onVADResult,
    onTelemetry,
  });

  // Update UI state
  useEffect(() => {
    const newState: UIState = {
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
    };
    setUIState(newState);
    onStateChange?.(newState);
  }, [
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
    onStateChange,
  ]);

  // Handle errors
  useEffect(() => {
    if (error) {
      Alert.alert(
        'Error',
        error.message,
        [
          {
            text: 'OK',
            onPress: () => clearError(),
          },
        ]
      );
    }
  }, [error, clearError]);

  // Auto-connect on mount
  useEffect(() => {
    connect(config.livekit);
  }, [connect, config.livekit]);

  const handleConnect = () => {
    if (isConnected) {
      disconnect();
    } else {
      connect(config.livekit);
    }
  };

  const handleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const handleBargeIn = () => {
    sendBargeInRequest('button_press');
  };

  const getStatusColor = () => {
    if (error) return '#FF6B6B';
    if (isResponding) return '#4ECDC4';
    if (isProcessing) return '#FFE66D';
    if (isRecording) return '#FF6B6B';
    if (isConnected) return '#4ECDC4';
    return '#95A5A6';
  };

  const getStatusText = () => {
    if (error) return 'Error';
    if (isResponding) return 'Responding';
    if (isProcessing) return 'Processing';
    if (isRecording) return 'Listening';
    if (isConnected) return 'Connected';
    return 'Disconnected';
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#2C3E50" />
      
      <LinearGradient
        colors={['#2C3E50', '#34495E']}
        style={styles.gradient}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Voice Assistant</Text>
          <View style={styles.statusContainer}>
            <View style={[styles.statusIndicator, { backgroundColor: getStatusColor() }]} />
            <Text style={styles.statusText}>{getStatusText()}</Text>
          </View>
        </View>

        {/* Audio Visualizer */}
        <View style={styles.visualizerContainer}>
          <AudioVisualizer
            isActive={isRecording || isProcessing || isResponding}
            level={isRecording ? 0.7 : isProcessing ? 0.3 : 0.1}
            color={getStatusColor()}
            size={Math.min(width, height) * 0.6}
          />
        </View>

        {/* Transcript Display */}
        <View style={styles.transcriptContainer}>
          <TranscriptDisplay
            transcript={currentTranscript}
            isFinal={!isRecording}
            words={[]}
          />
        </View>

        {/* Response Display */}
        {lastResponse && (
          <View style={styles.responseContainer}>
            <Text style={styles.responseLabel}>Response:</Text>
            <Text style={styles.responseText}>{lastResponse}</Text>
          </View>
        )}

        {/* Control Panel */}
        <View style={styles.controlContainer}>
          <ControlPanel
            isConnected={isConnected}
            isRecording={isRecording}
            isProcessing={isProcessing}
            isResponding={isResponding}
            isMuted={isMuted}
            onStartRecording={handleRecording}
            onStopRecording={handleRecording}
            onToggleMute={toggleMute}
            onDisconnect={handleConnect}
          />
        </View>

        {/* Barge-in Button */}
        {isResponding && (
          <TouchableOpacity
            style={styles.bargeInButton}
            onPress={handleBargeIn}
          >
            <Icon name="mic" size={24} color="#FFFFFF" />
            <Text style={styles.bargeInText}>Interrupt</Text>
          </TouchableOpacity>
        )}

        {/* Session Info */}
        <View style={styles.sessionInfo}>
          <Text style={styles.sessionText}>
            Session: {Math.floor(sessionDuration / 60)}:{(sessionDuration % 60).toString().padStart(2, '0')}
          </Text>
          <Text style={styles.audioText}>
            Audio: {audioRoute} / {audioInput}
          </Text>
        </View>

        {/* Telemetry Display (Debug Mode) */}
        {config.debug.enabled && (
          <View style={styles.telemetryContainer}>
            <TelemetryDisplay
              data={{
                rttMs: 0,
                packetLossPercent: 0,
                jitterMs: 0,
                bitrate: 0,
                batteryLevel: 0,
                thermalState: 'normal',
                memoryUsage: 0,
                cpuUsage: 0,
              }}
            />
          </View>
        )}
      </LinearGradient>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#2C3E50',
  },
  gradient: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 15,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
  statusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusIndicator: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: 8,
  },
  statusText: {
    fontSize: 16,
    color: '#FFFFFF',
    fontWeight: '500',
  },
  visualizerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 20,
  },
  transcriptContainer: {
    paddingHorizontal: 20,
    paddingVertical: 15,
    minHeight: 100,
  },
  responseContainer: {
    paddingHorizontal: 20,
    paddingVertical: 10,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    marginHorizontal: 20,
    borderRadius: 10,
  },
  responseLabel: {
    fontSize: 14,
    color: '#BDC3C7',
    marginBottom: 5,
  },
  responseText: {
    fontSize: 16,
    color: '#FFFFFF',
    lineHeight: 22,
  },
  controlContainer: {
    paddingHorizontal: 20,
    paddingVertical: 15,
  },
  bargeInButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#E74C3C',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 25,
    marginHorizontal: 20,
    marginVertical: 10,
  },
  bargeInText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
  sessionInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 10,
  },
  sessionText: {
    fontSize: 14,
    color: '#BDC3C7',
  },
  audioText: {
    fontSize: 14,
    color: '#BDC3C7',
  },
  telemetryContainer: {
    paddingHorizontal: 20,
    paddingVertical: 10,
    backgroundColor: 'rgba(0, 0, 0, 0.3)',
    marginHorizontal: 20,
    marginBottom: 10,
    borderRadius: 10,
  },
});