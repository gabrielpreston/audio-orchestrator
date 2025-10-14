/**
 * Main App component
 */

import React, { useState, useEffect } from 'react';
import { StatusBar, StyleSheet, View, Alert } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { Provider as PaperProvider } from 'react-native-paper';
import Config from 'react-native-config';

import { VoiceAssistant } from './components/VoiceAssistant';
import { AppConfig, UIState, AppError, VADResult, WakeWordResult, TelemetryData } from './types';

const Stack = createStackNavigator();

// Default configuration
const defaultConfig: AppConfig = {
  livekit: {
    url: Config.LIVEKIT_URL || 'wss://your-livekit-server.com',
    token: Config.LIVEKIT_TOKEN || 'your-token',
    roomName: Config.ROOM_NAME || 'voice-assistant',
  },
  audio: {
    sampleRate: parseInt(Config.AUDIO_SAMPLE_RATE || '16000'),
    frameMs: parseInt(Config.AUDIO_FRAME_MS || '20'),
    channels: parseInt(Config.AUDIO_CHANNELS || '1'),
    bitDepth: parseInt(Config.AUDIO_BIT_DEPTH || '16'),
  },
  wakeWord: {
    enabled: Config.WAKE_WORD_ENABLED === 'true',
    phrases: (Config.WAKE_WORD_PHRASES || 'hey atlas,ok atlas').split(','),
    threshold: parseFloat(Config.WAKE_WORD_THRESHOLD || '0.5'),
    cooldownMs: parseInt(Config.WAKE_WORD_COOLDOWN_MS || '1000'),
  },
  vad: {
    enabled: Config.VAD_ENABLED === 'true',
    aggressiveness: parseInt(Config.VAD_AGGRESSIVENESS || '2'),
    timeoutMs: parseInt(Config.VAD_TIMEOUT_MS || '2000'),
    paddingMs: parseInt(Config.VAD_PADDING_MS || '200'),
    minSpeechDurationMs: 300,
    maxSilenceDurationMs: 1000,
  },
  ui: {
    theme: (Config.UI_THEME as 'light' | 'dark') || 'dark',
    animationsEnabled: Config.UI_ANIMATIONS_ENABLED !== 'false',
    debugMode: Config.UI_DEBUG_MODE === 'true',
  },
  debug: {
    enabled: Config.DEBUG_ENABLED === 'true',
    logLevel: (Config.DEBUG_LOG_LEVEL as 'debug' | 'info' | 'warn' | 'error') || 'info',
    saveAudio: Config.DEBUG_SAVE_AUDIO === 'true',
  },
  performance: {
    maxSessionDurationMinutes: parseInt(Config.MAX_SESSION_DURATION_MINUTES || '30'),
    audioBufferSizeMs: parseInt(Config.AUDIO_BUFFER_SIZE_MS || '100'),
    networkTimeoutMs: parseInt(Config.NETWORK_TIMEOUT_MS || '30000'),
    retryAttempts: parseInt(Config.RETRY_ATTEMPTS || '3'),
  },
};

const App: React.FC = () => {
  const [config, setConfig] = useState<AppConfig>(defaultConfig);
  const [uiState, setUIState] = useState<UIState | null>(null);

  // Load configuration from environment
  useEffect(() => {
    // Configuration is loaded from Config object (react-native-config)
    // In a real app, you might load this from a remote API or user preferences
    console.log('App configuration loaded:', config);
  }, [config]);

  const handleStateChange = (state: UIState) => {
    setUIState(state);
    console.log('UI state changed:', state);
  };

  const handleError = (error: AppError) => {
    console.error('App error:', error);
    
    // Show error alert for non-recoverable errors
    if (!error.recoverable) {
      Alert.alert(
        'Error',
        error.message,
        [
          {
            text: 'OK',
            onPress: () => console.log('Error acknowledged'),
          },
        ]
      );
    }
  };

  const handleTranscript = (transcript: string, isFinal: boolean) => {
    console.log('Transcript:', { transcript, isFinal });
  };

  const handleResponse = (response: string) => {
    console.log('Response:', response);
  };

  const handleWakeWord = (result: WakeWordResult) => {
    console.log('Wake word detected:', result);
  };

  const handleVADResult = (result: VADResult) => {
    console.log('VAD result:', result);
  };

  const handleTelemetry = (data: TelemetryData) => {
    console.log('Telemetry data:', data);
  };

  return (
    <SafeAreaProvider>
      <PaperProvider>
        <NavigationContainer>
          <StatusBar barStyle="light-content" backgroundColor="#2C3E50" />
          <View style={styles.container}>
            <Stack.Navigator
              screenOptions={{
                headerShown: false,
                cardStyle: { backgroundColor: '#2C3E50' },
              }}
            >
              <Stack.Screen name="VoiceAssistant">
                {() => (
                  <VoiceAssistant
                    config={config}
                    onStateChange={handleStateChange}
                    onError={handleError}
                    onTranscript={handleTranscript}
                    onResponse={handleResponse}
                    onWakeWord={handleWakeWord}
                    onVADResult={handleVADResult}
                    onTelemetry={handleTelemetry}
                  />
                )}
              </Stack.Screen>
            </Stack.Navigator>
          </View>
        </NavigationContainer>
      </PaperProvider>
    </SafeAreaProvider>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#2C3E50',
  },
});

export default App;