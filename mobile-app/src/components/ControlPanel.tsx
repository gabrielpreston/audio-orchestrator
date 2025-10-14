/**
 * Control panel component
 */

import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import Icon from 'react-native-vector-icons/MaterialIcons';
import { AudioRoute, AudioInput } from '../types';

interface ControlPanelProps {
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

export const ControlPanel: React.FC<ControlPanelProps> = ({
  isConnected,
  isRecording,
  isProcessing,
  isResponding,
  isMuted,
  onStartRecording,
  onStopRecording,
  onToggleMute,
  onDisconnect,
  style,
}) => {
  const getMainButtonColor = () => {
    if (isResponding) return '#4ECDC4';
    if (isProcessing) return '#FFE66D';
    if (isRecording) return '#E74C3C';
    if (isConnected) return '#27AE60';
    return '#95A5A6';
  };

  const getMainButtonIcon = () => {
    if (isResponding) return 'volume-up';
    if (isProcessing) return 'hourglass-empty';
    if (isRecording) return 'mic';
    if (isConnected) return 'mic-none';
    return 'mic-off';
  };

  const getMainButtonText = () => {
    if (isResponding) return 'Responding';
    if (isProcessing) return 'Processing';
    if (isRecording) return 'Listening';
    if (isConnected) return 'Start';
    return 'Connect';
  };

  const handleMainButtonPress = () => {
    if (isConnected) {
      if (isRecording) {
        onStopRecording();
      } else {
        onStartRecording();
      }
    } else {
      onDisconnect();
    }
  };

  const isMainButtonDisabled = isProcessing || isResponding;

  return (
    <View style={[styles.container, style]}>
      {/* Main control button */}
      <TouchableOpacity
        style={[
          styles.mainButton,
          {
            backgroundColor: getMainButtonColor(),
            opacity: isMainButtonDisabled ? 0.6 : 1,
          },
        ]}
        onPress={handleMainButtonPress}
        disabled={isMainButtonDisabled}
      >
        <Icon name={getMainButtonIcon()} size={32} color="#FFFFFF" />
        <Text style={styles.mainButtonText}>{getMainButtonText()}</Text>
      </TouchableOpacity>

      {/* Secondary controls */}
      <View style={styles.secondaryControls}>
        {/* Mute/Unmute button */}
        <TouchableOpacity
          style={[
            styles.secondaryButton,
            {
              backgroundColor: isMuted ? '#E74C3C' : '#34495E',
            },
          ]}
          onPress={onToggleMute}
          disabled={!isConnected}
        >
          <Icon
            name={isMuted ? 'mic-off' : 'mic'}
            size={20}
            color="#FFFFFF"
          />
        </TouchableOpacity>

        {/* Disconnect button */}
        <TouchableOpacity
          style={[
            styles.secondaryButton,
            {
              backgroundColor: '#E74C3C',
            },
          ]}
          onPress={onDisconnect}
          disabled={!isConnected}
        >
          <Icon name="call-end" size={20} color="#FFFFFF" />
        </TouchableOpacity>
      </View>

      {/* Status indicators */}
      <View style={styles.statusIndicators}>
        <View style={styles.statusItem}>
          <View
            style={[
              styles.statusDot,
              { backgroundColor: isConnected ? '#27AE60' : '#E74C3C' },
            ]}
          />
          <Text style={styles.statusText}>
            {isConnected ? 'Connected' : 'Disconnected'}
          </Text>
        </View>

        {isConnected && (
          <View style={styles.statusItem}>
            <View
              style={[
                styles.statusDot,
                { backgroundColor: isRecording ? '#E74C3C' : '#95A5A6' },
              ]}
            />
            <Text style={styles.statusText}>
              {isRecording ? 'Recording' : 'Idle'}
            </Text>
          </View>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  mainButton: {
    width: 120,
    height: 120,
    borderRadius: 60,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 4,
    },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  mainButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
    marginTop: 8,
    textAlign: 'center',
  },
  secondaryControls: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginBottom: 20,
  },
  secondaryButton: {
    width: 50,
    height: 50,
    borderRadius: 25,
    justifyContent: 'center',
    alignItems: 'center',
    marginHorizontal: 10,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 4,
  },
  statusIndicators: {
    flexDirection: 'row',
    justifyContent: 'center',
    flexWrap: 'wrap',
  },
  statusItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 10,
    marginVertical: 5,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  statusText: {
    color: '#BDC3C7',
    fontSize: 12,
    fontWeight: '500',
  },
});