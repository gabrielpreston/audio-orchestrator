/**
 * Audio service for mobile voice assistant
 */

import {
  AudioFrame,
  AudioSegment,
  WordTiming,
  VADConfig,
  VADResult,
  WakeWordConfig,
  WakeWordResult,
  AudioRoute,
  AudioInput,
  AudioSessionConfig,
} from '../types';

export class AudioService {
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private audioWorkletNode: AudioWorkletNode | null = null;
  private vadConfig: VADConfig;
  private wakeWordConfig: WakeWordConfig;
  private isRecording = false;
  private frameCount = 0;
  private vadCallbacks: ((result: VADResult) => void)[] = [];
  private wakeWordCallbacks: ((result: WakeWordResult) => void)[] = [];
  private audioFrameCallbacks: ((frame: AudioFrame) => void)[] = [];

  constructor(vadConfig: VADConfig, wakeWordConfig: WakeWordConfig) {
    this.vadConfig = vadConfig;
    this.wakeWordConfig = wakeWordConfig;
  }

  async initialize(): Promise<void> {
    try {
      // Create audio context
      this.audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: 16000,
        latencyHint: 'interactive',
      });

      // Load audio worklet for VAD and wake word detection
      await this.loadAudioWorklet();

      console.log('Audio service initialized');
    } catch (error) {
      console.error('Failed to initialize audio service:', error);
      throw error;
    }
  }

  async startRecording(): Promise<void> {
    if (this.isRecording) {
      return;
    }

    try {
      // Get microphone access
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Create audio source
      const source = this.audioContext!.createMediaStreamSource(this.mediaStream);
      
      // Connect to audio worklet
      source.connect(this.audioWorkletNode!);
      this.audioWorkletNode!.connect(this.audioContext!.destination);

      this.isRecording = true;
      console.log('Started recording');
    } catch (error) {
      console.error('Failed to start recording:', error);
      throw error;
    }
  }

  async stopRecording(): Promise<void> {
    if (!this.isRecording) {
      return;
    }

    try {
      // Stop media stream
      if (this.mediaStream) {
        this.mediaStream.getTracks().forEach(track => track.stop());
        this.mediaStream = null;
      }

      // Disconnect audio nodes
      if (this.audioWorkletNode) {
        this.audioWorkletNode.disconnect();
      }

      this.isRecording = false;
      console.log('Stopped recording');
    } catch (error) {
      console.error('Failed to stop recording:', error);
      throw error;
    }
  }

  async changeAudioRoute(route: AudioRoute): Promise<void> {
    try {
      // This would typically involve native bridge calls
      // For now, we'll just log the change
      console.log('Changed audio route to:', route);
    } catch (error) {
      console.error('Failed to change audio route:', error);
      throw error;
    }
  }

  async changeAudioInput(input: AudioInput): Promise<void> {
    try {
      // This would typically involve native bridge calls
      // For now, we'll just log the change
      console.log('Changed audio input to:', input);
    } catch (error) {
      console.error('Failed to change audio input:', error);
      throw error;
    }
  }

  onVADResult(callback: (result: VADResult) => void): void {
    this.vadCallbacks.push(callback);
  }

  onWakeWordResult(callback: (result: WakeWordResult) => void): void {
    this.wakeWordCallbacks.push(callback);
  }

  onAudioFrame(callback: (frame: AudioFrame) => void): void {
    this.audioFrameCallbacks.push(callback);
  }

  private async loadAudioWorklet(): Promise<void> {
    if (!this.audioContext) {
      throw new Error('Audio context not initialized');
    }

    try {
      // Register audio worklet processor
      await this.audioContext.audioWorklet.addModule('/audio-processor.js');
      
      // Create audio worklet node
      this.audioWorkletNode = new AudioWorkletNode(this.audioContext, 'audio-processor', {
        processorOptions: {
          vadConfig: this.vadConfig,
          wakeWordConfig: this.wakeWordConfig,
        },
      });

      // Set up message handling
      this.audioWorkletNode.port.onmessage = (event) => {
        const { type, data } = event.data;

        switch (type) {
          case 'vad':
            this.handleVADResult(data);
            break;
          case 'wakeWord':
            this.handleWakeWordResult(data);
            break;
          case 'audioFrame':
            this.handleAudioFrame(data);
            break;
        }
      };

      console.log('Audio worklet loaded');
    } catch (error) {
      console.error('Failed to load audio worklet:', error);
      throw error;
    }
  }

  private handleVADResult(data: any): void {
    const result: VADResult = {
      isSpeech: data.isSpeech,
      confidence: data.confidence,
      timestamp: data.timestamp,
      duration: data.duration,
    };

    this.vadCallbacks.forEach(callback => callback(result));
  }

  private handleWakeWordResult(data: any): void {
    const result: WakeWordResult = {
      phrase: data.phrase,
      confidence: data.confidence,
      timestamp: data.timestamp,
    };

    this.wakeWordCallbacks.forEach(callback => callback(result));
  }

  private handleAudioFrame(data: any): void {
    const frame: AudioFrame = {
      pcmData: new Uint8Array(data.pcmData),
      sampleRate: data.sampleRate,
      channels: data.channels,
      sampleWidth: data.sampleWidth,
      bitDepth: data.bitDepth,
      timestamp: data.timestamp,
      frameDurationMs: data.frameDurationMs,
      sequenceNumber: this.frameCount++,
      isSpeech: data.isSpeech,
      isEndpoint: data.isEndpoint,
      confidence: data.confidence,
    };

    this.audioFrameCallbacks.forEach(callback => callback(frame));
  }

  // Cleanup
  destroy(): void {
    this.stopRecording();
    
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }

    this.vadCallbacks = [];
    this.wakeWordCallbacks = [];
    this.audioFrameCallbacks = [];
  }
}