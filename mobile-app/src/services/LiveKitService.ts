/**
 * LiveKit service for WebRTC integration
 */

import {
  Room,
  RoomEvent,
  RemoteParticipant,
  LocalParticipant,
  RemoteTrack,
  LocalTrack,
  Track,
  TrackPublication,
  DataPacket,
  DataPacket_Kind,
  RoomOptions,
  AudioTrack,
  VideoTrack,
  LocalAudioTrack,
  LocalVideoTrack,
  RemoteAudioTrack,
  RemoteVideoTrack,
  RemoteTrackPublication,
  LocalTrackPublication,
  ConnectionState,
  DisconnectReason,
  ParticipantEvent,
  TrackEvent,
  MediaStreamTrack,
  RTCIceServer,
} from 'livekit-client';

import {
  ControlMessage,
  MessageType,
  LiveKitConfig,
  TelemetryData,
} from '../types';

export class LiveKitService {
  private room: Room | null = null;
  private localParticipant: LocalParticipant | null = null;
  private dataChannel: RTCDataChannel | null = null;
  private controlMessageCallbacks: ((message: ControlMessage) => void)[] = [];
  private connectionStateCallbacks: ((state: ConnectionState) => void)[] = [];
  private isConnected = false;
  private correlationId = '';

  constructor() {
    this.correlationId = this.generateCorrelationId();
  }

  async connect(config: LiveKitConfig): Promise<void> {
    try {
      // Create room with options
      const roomOptions: RoomOptions = {
        adaptiveStream: true,
        dynacast: true,
        publishDefaults: {
          audioPreset: {
            maxBitrate: 64000,
            priority: 'high',
          },
        },
        subscribeDefaults: {
          audioPreset: {
            maxBitrate: 64000,
            priority: 'high',
          },
        },
      };

      this.room = new Room(roomOptions);

      // Set up event handlers
      this.setupEventHandlers();

      // Connect to room
      await this.room.connect(config.url, config.token);

      this.localParticipant = this.room.localParticipant;
      this.isConnected = true;

      console.log('Connected to LiveKit room:', config.roomName);
    } catch (error) {
      console.error('Failed to connect to LiveKit room:', error);
      throw error;
    }
  }

  async disconnect(): Promise<void> {
    try {
      if (this.room) {
        await this.room.disconnect();
        this.room = null;
        this.localParticipant = null;
        this.dataChannel = null;
        this.isConnected = false;
        console.log('Disconnected from LiveKit room');
      }
    } catch (error) {
      console.error('Failed to disconnect from LiveKit room:', error);
      throw error;
    }
  }

  async publishAudioTrack(track: MediaStreamTrack): Promise<void> {
    if (!this.room || !this.localParticipant) {
      throw new Error('Not connected to room');
    }

    try {
      // Create local audio track from MediaStreamTrack
      const localAudioTrack = await LocalAudioTrack.createAudioTrack('microphone', track);
      
      // Publish the track
      await this.localParticipant.publishTrack(localAudioTrack, {
        name: 'microphone',
        source: Track.Source.Microphone,
      });

      console.log('Published audio track');
    } catch (error) {
      console.error('Failed to publish audio track:', error);
      throw error;
    }
  }

  subscribeToAudioTrack(callback: (track: MediaStreamTrack) => void): void {
    if (!this.room) {
      throw new Error('Not connected to room');
    }

    // Set up audio track subscription
    this.room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack, publication: RemoteTrackPublication, participant: RemoteParticipant) => {
      if (track.kind === Track.Kind.Audio) {
        const audioTrack = track as RemoteAudioTrack;
        const mediaStreamTrack = audioTrack.mediaStreamTrack;
        callback(mediaStreamTrack);
      }
    });
  }

  async sendControlMessage(message: ControlMessage): Promise<void> {
    if (!this.room || !this.localParticipant) {
      throw new Error('Not connected to room');
    }

    try {
      // Send data packet
      const data = JSON.stringify({
        type: message.messageType,
        timestamp: message.timestamp,
        correlation_id: message.correlationId,
        payload: message.payload,
      });

      await this.room.localParticipant.publishData(
        new TextEncoder().encode(data),
        DataPacket_Kind.RELIABLE
      );

      console.log('Sent control message:', message.messageType);
    } catch (error) {
      console.error('Failed to send control message:', error);
      throw error;
    }
  }

  onControlMessage(callback: (message: ControlMessage) => void): void {
    this.controlMessageCallbacks.push(callback);
  }

  onConnectionStateChange(callback: (state: ConnectionState) => void): void {
    this.connectionStateCallbacks.push(callback);
  }

  getConnectionState(): ConnectionState {
    return this.room?.state || ConnectionState.Disconnected;
  }

  async getStats(): Promise<RTCStatsReport | null> {
    if (!this.room) {
      return null;
    }

    try {
      // Get stats from the room's peer connection
      const stats = await this.room.engine.client.getStats();
      return stats;
    } catch (error) {
      console.error('Failed to get stats:', error);
      return null;
    }
  }

  async getTelemetryData(): Promise<TelemetryData> {
    const stats = await this.getStats();
    if (!stats) {
      return this.getDefaultTelemetryData();
    }

    let rttMs = 0;
    let packetLossPercent = 0;
    let jitterMs = 0;
    let bitrate = 0;

    // Parse RTC stats
    stats.forEach((report) => {
      if (report.type === 'candidate-pair' && report.state === 'succeeded') {
        rttMs = report.currentRoundTripTime ? report.currentRoundTripTime * 1000 : 0;
      } else if (report.type === 'inbound-rtp' && report.mediaType === 'audio') {
        packetLossPercent = report.packetsLost ? (report.packetsLost / report.packetsReceived) * 100 : 0;
        jitterMs = report.jitter ? report.jitter * 1000 : 0;
        bitrate = report.bytesReceived ? (report.bytesReceived * 8) / 1000 : 0; // kbps
      }
    });

    return {
      rttMs,
      packetLossPercent,
      jitterMs,
      bitrate,
      batteryLevel: 0, // Will be filled by device info
      thermalState: 'normal',
      memoryUsage: 0,
      cpuUsage: 0,
    };
  }

  private setupEventHandlers(): void {
    if (!this.room) return;

    // Connection state changes
    this.room.on(RoomEvent.Connected, () => {
      console.log('Room connected');
      this.connectionStateCallbacks.forEach(callback => callback(ConnectionState.Connected));
    });

    this.room.on(RoomEvent.Disconnected, (reason?: DisconnectReason) => {
      console.log('Room disconnected:', reason);
      this.connectionStateCallbacks.forEach(callback => callback(ConnectionState.Disconnected));
    });

    this.room.on(RoomEvent.Reconnecting, () => {
      console.log('Room reconnecting');
      this.connectionStateCallbacks.forEach(callback => callback(ConnectionState.Reconnecting));
    });

    this.room.on(RoomEvent.Reconnected, () => {
      console.log('Room reconnected');
      this.connectionStateCallbacks.forEach(callback => callback(ConnectionState.Connected));
    });

    // Data received
    this.room.on(RoomEvent.DataReceived, (payload: Uint8Array, participant?: RemoteParticipant) => {
      try {
        const data = JSON.parse(new TextDecoder().decode(payload));
        const message: ControlMessage = {
          messageType: data.type as MessageType,
          timestamp: data.timestamp,
          correlationId: data.correlation_id,
          payload: data.payload,
        };

        this.controlMessageCallbacks.forEach(callback => callback(message));
      } catch (error) {
        console.error('Failed to parse control message:', error);
      }
    });

    // Participant events
    this.room.on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
      console.log('Participant connected:', participant.identity);
    });

    this.room.on(RoomEvent.ParticipantDisconnected, (participant: RemoteParticipant) => {
      console.log('Participant disconnected:', participant.identity);
    });

    // Track events
    this.room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack, publication: RemoteTrackPublication, participant: RemoteParticipant) => {
      console.log('Track subscribed:', track.kind, participant.identity);
    });

    this.room.on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack, publication: RemoteTrackPublication, participant: RemoteParticipant) => {
      console.log('Track unsubscribed:', track.kind, participant.identity);
    });
  }

  private generateCorrelationId(): string {
    return `mobile_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private getDefaultTelemetryData(): TelemetryData {
    return {
      rttMs: 0,
      packetLossPercent: 0,
      jitterMs: 0,
      bitrate: 0,
      batteryLevel: 0,
      thermalState: 'normal',
      memoryUsage: 0,
      cpuUsage: 0,
    };
  }

  // Cleanup
  destroy(): void {
    this.controlMessageCallbacks = [];
    this.connectionStateCallbacks = [];
    if (this.room) {
      this.room.disconnect();
      this.room = null;
    }
  }
}