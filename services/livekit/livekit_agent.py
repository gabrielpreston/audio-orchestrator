"""Main LiveKit agent service for mobile voice assistant integration."""

import asyncio
import json
import time
from typing import Optional

from livekit import rtc

from services.common.audio_contracts import (
    AudioSegment,
    EndpointingMessage,
    EndpointingState,
    ErrorMessage,
    SessionState,
    TranscriptFinalMessage,
    TranscriptPartialMessage,
)
from services.common.logging import configure_logging, get_logger

from .audio_processor import LiveKitAudioProcessor
from .config import config
from .session_manager import MobileSession, SessionManager
from .stt_adapter import LiveKitSTTAdapter
from .tts_adapter import LiveKitTTSAdapter


class MobileVoiceAgent:
    """LiveKit agent for mobile voice assistant integration."""

    def __init__(self):
        # Configure logging
        configure_logging(
            level=config.log_level, json_logs=config.log_json, service_name=config.service_name
        )

        self.logger = get_logger("mobile_voice_agent")

        # Initialize components
        self.audio_processor = LiveKitAudioProcessor()
        self.stt_adapter = LiveKitSTTAdapter(config.stt_base_url, config.stt_timeout)
        self.tts_adapter = LiveKitTTSAdapter(config.tts_base_url, config.tts_timeout)
        self.session_manager = SessionManager()

        # Agent state
        self.is_running = False
        self.room: Optional[rtc.Room] = None

        # Audio tracks
        self.mic_track: Optional[rtc.LocalAudioTrack] = None
        self.speaker_track: Optional[rtc.LocalAudioTrack] = None

        # Data channel for control messages
        self.data_channel: Optional[rtc.DataChannel] = None

    async def start(self):
        """Start the mobile voice agent."""
        try:
            self.logger.info("agent.starting")

            # Start session manager
            await self.session_manager.start()

            # Initialize LiveKit room
            self.room = rtc.Room()
            await self._setup_room_handlers()

            self.is_running = True
            self.logger.info("agent.started")

        except Exception as e:
            self.logger.error("agent.startup_failed", error=str(e))
            raise

    async def stop(self):
        """Stop the mobile voice agent."""
        try:
            self.logger.info("agent.stopping")

            self.is_running = False

            # Stop session manager
            await self.session_manager.stop()

            # Disconnect from room
            if self.room:
                await self.room.disconnect()

            self.logger.info("agent.stopped")

        except Exception as e:
            self.logger.error("agent.shutdown_error", error=str(e))

    async def join_room(self, room_name: str, token: str):
        """Join a LiveKit room."""
        if not self.room:
            raise RuntimeError("Agent not started")

        try:
            # Connect to room
            await self.room.connect(url=config.livekit_url, token=token)

            # Wait for connection
            await asyncio.sleep(1)

            self.logger.info(
                "agent.room_joined",
                room_name=room_name,
                participant_count=len(self.room.remote_participants),
            )

        except Exception as e:
            self.logger.error("agent.room_join_failed", room_name=room_name, error=str(e))
            raise

    async def _setup_room_handlers(self):
        """Setup LiveKit room event handlers."""
        if not self.room:
            return

        @self.room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant):
            asyncio.create_task(self._handle_participant_connected(participant))

        @self.room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant):
            asyncio.create_task(self._handle_participant_disconnected(participant))

        @self.room.on("data_received")
        def on_data_received(data: rtc.DataPacket):
            asyncio.create_task(self._handle_data_received(data))

        @self.room.on("track_subscribed")
        def on_track_subscribed(
            track: rtc.Track, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant
        ):
            asyncio.create_task(self._handle_track_subscribed(track, publication, participant))

        @self.room.on("track_unsubscribed")
        def on_track_unsubscribed(
            track: rtc.Track, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant
        ):
            asyncio.create_task(self._handle_track_unsubscribed(track, publication, participant))

    async def _handle_participant_connected(self, participant: rtc.RemoteParticipant):
        """Handle participant connection."""
        correlation_id = f"mobile_{participant.identity}_{int(time.time())}"

        # Create session
        await self.session_manager.create_session(self.room, participant, correlation_id)

        self.logger.info(
            "agent.participant_connected",
            correlation_id=correlation_id,
            participant_identity=participant.identity,
            participant_sid=participant.sid,
        )

    async def _handle_participant_disconnected(self, participant: rtc.RemoteParticipant):
        """Handle participant disconnection."""
        # Find and remove session
        if self.room:
            room_sessions = await self.session_manager.get_room_sessions(self.room.name)
            for session in room_sessions:
                if session.participant.sid == participant.sid:
                    await self.session_manager.remove_session(session.correlation_id)
                    break

        self.logger.info(
            "agent.participant_disconnected",
            participant_identity=participant.identity,
            participant_sid=participant.sid,
        )

    async def _handle_data_received(self, data: rtc.DataPacket):
        """Handle data channel messages."""
        try:
            # Parse control message
            message_data = json.loads(data.data.decode("utf-8"))

            # Find session by participant
            participant = data.participant
            if not self.room:
                return
            room_sessions = await self.session_manager.get_room_sessions(self.room.name)
            session = None

            for s in room_sessions:
                if s.participant.sid == participant.sid:
                    session = s
                    break

            if not session:
                self.logger.warning("agent.session_not_found", participant_sid=participant.sid)
                return

            # Create control message object
            from ..common.audio_contracts import ControlMessage, MessageType

            message = ControlMessage(
                message_type=MessageType(message_data["type"]),
                timestamp=message_data["timestamp"],
                correlation_id=message_data["correlation_id"],
                payload=message_data["payload"],
            )

            # Handle message
            response = await self.session_manager.handle_control_message(session, message)

            # Send response if available
            if response and self.data_channel:
                await self.data_channel.send(json.dumps(response.to_dict()).encode("utf-8"))

        except Exception as e:
            self.logger.error("agent.data_handling_error", error=str(e))

    async def _handle_track_subscribed(
        self,
        track: rtc.Track,
        publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        """Handle track subscription."""
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            # Handle incoming audio from mobile client
            await self._handle_audio_track(track, participant)
        elif track.kind == rtc.TrackKind.KIND_DATA:
            # Handle data channel
            self.data_channel = track
            self.logger.info("agent.data_channel_established")

    async def _handle_track_unsubscribed(
        self,
        track: rtc.Track,
        publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        """Handle track unsubscription."""
        if track.kind == rtc.TrackKind.KIND_DATA and track == self.data_channel:
            self.data_channel = None
            self.logger.info("agent.data_channel_closed")

    async def _handle_audio_track(self, track: rtc.AudioTrack, participant: rtc.RemoteParticipant):
        """Handle incoming audio track from mobile client."""
        # Find session
        if not self.room:
            return
        room_sessions = await self.session_manager.get_room_sessions(self.room.name)
        session = None

        for s in room_sessions:
            if s.participant.sid == participant.sid:
                session = s
                break

        if not session:
            self.logger.warning("agent.audio_session_not_found", participant_sid=participant.sid)
            return

        # Start STT stream
        stt_stream_id = await self.stt_adapter.start_stream(session.correlation_id)

        try:
            # Process audio frames
            frame_count = 0
            async for audio_frame in track:
                if not self.is_running:
                    break

                # Convert to canonical format
                pcm_data = await self.audio_processor.decode_opus_to_pcm(audio_frame.data)
                pcm_data = self.audio_processor.resample_audio(
                    pcm_data,
                    from_rate=48000,  # Opus sample rate
                    to_rate=16000,  # Canonical sample rate
                )

                # Create audio frame
                canonical_frame = self.audio_processor.create_audio_frame(
                    pcm_data=pcm_data,
                    timestamp=time.time(),
                    sequence_number=frame_count,
                    is_speech=False,  # VAD would be handled client-side
                    is_endpoint=False,
                    confidence=0.0,
                )

                # Process with STT
                segment = await self.stt_adapter.process_audio_frame(stt_stream_id, canonical_frame)

                if segment:
                    # Send transcript to orchestrator
                    await self._process_transcript(session, segment)

                frame_count += 1
                session.stats["frames_processed"] += 1

        except Exception as e:
            self.logger.error(
                "agent.audio_processing_error", correlation_id=session.correlation_id, error=str(e)
            )
        finally:
            # Flush STT stream
            final_segment = await self.stt_adapter.flush_stream(stt_stream_id)
            if final_segment:
                await self._process_transcript(session, final_segment)

            await self.stt_adapter.stop_stream(stt_stream_id)

    async def _process_transcript(self, session: MobileSession, segment: AudioSegment):
        """Process transcript segment with orchestrator."""
        try:
            # Send partial transcript
            if not segment.is_final:
                partial_msg = TranscriptPartialMessage(
                    session.correlation_id, segment.transcript, segment.confidence
                )

                if self.data_channel:
                    await self.data_channel.send(json.dumps(partial_msg.to_dict()).encode("utf-8"))

                return

            # Send final transcript
            final_msg = TranscriptFinalMessage(
                session.correlation_id, segment.transcript, segment.words
            )

            if self.data_channel:
                await self.data_channel.send(json.dumps(final_msg.to_dict()).encode("utf-8"))

            # Update session state
            session.state = SessionState.PROCESSING
            session.endpointing_state = EndpointingState.PROCESSING

            endpointing_msg = EndpointingMessage(
                session.correlation_id, session.endpointing_state.value
            )

            if self.data_channel:
                await self.data_channel.send(json.dumps(endpointing_msg.to_dict()).encode("utf-8"))

            # Process with orchestrator
            await self._call_orchestrator(session, segment)

        except Exception as e:
            self.logger.error(
                "agent.transcript_processing_error",
                correlation_id=session.correlation_id,
                error=str(e),
            )

    async def _call_orchestrator(self, session: MobileSession, segment: AudioSegment):
        """Call orchestrator service with transcript."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=config.orchestrator_timeout) as client:
                response = await client.post(
                    f"{config.orchestrator_base_url}/v1/chat/completions",
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [{"role": "user", "content": segment.transcript}],
                        "stream": True,
                    },
                    headers={
                        "Authorization": f"Bearer {config.auth_token}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()

                # Process streaming response
                tts_stream_id = await self.tts_adapter.start_stream(session.correlation_id)
                response_text = ""

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        if data.strip() == "[DONE]":
                            break

                        try:
                            chunk_data = json.loads(data)
                            if "choices" in chunk_data and chunk_data["choices"]:
                                delta = chunk_data["choices"][0].get("delta", {})
                                content = delta.get("content", "")

                                if content:
                                    response_text += content
                                    await self.tts_adapter.add_text_chunk(tts_stream_id, content)

                                    # Send audio chunks to client
                                    await self._send_audio_chunks(session, tts_stream_id)

                        except json.JSONDecodeError:
                            continue

                # Finalize TTS stream
                await self.tts_adapter.stop_stream(tts_stream_id)

                # Update session state
                session.state = SessionState.RESPONDING
                session.endpointing_state = EndpointingState.RESPONDING
                session.is_responding = True

                endpointing_msg = EndpointingMessage(
                    session.correlation_id, session.endpointing_state.value
                )

                if self.data_channel:
                    await self.data_channel.send(
                        json.dumps(endpointing_msg.to_dict()).encode("utf-8")
                    )

                self.logger.info(
                    "agent.orchestrator_response",
                    correlation_id=session.correlation_id,
                    response_length=len(response_text),
                )

        except Exception as e:
            self.logger.error(
                "agent.orchestrator_error", correlation_id=session.correlation_id, error=str(e)
            )

            # Send error to client
            error_msg = ErrorMessage(
                session.correlation_id,
                "ORCHESTRATOR_ERROR",
                f"Failed to process request: {e}",
                recoverable=True,
            )

            if self.data_channel:
                await self.data_channel.send(json.dumps(error_msg.to_dict()).encode("utf-8"))

    async def _send_audio_chunks(self, session: MobileSession, tts_stream_id: str):
        """Send audio chunks from TTS to client."""
        try:
            while True:
                chunk = await self.tts_adapter.get_audio_chunk(tts_stream_id)
                if not chunk:
                    break

                # Here you would publish the audio chunk to the room
                # For now, we'll just log it
                self.logger.debug(
                    "agent.audio_chunk_sent",
                    correlation_id=session.correlation_id,
                    chunk_size=len(chunk),
                )

        except Exception as e:
            self.logger.error(
                "agent.audio_chunk_error", correlation_id=session.correlation_id, error=str(e)
            )


async def main():
    """Main entry point for the LiveKit agent."""
    agent = MobileVoiceAgent()

    try:
        await agent.start()

        # Keep running
        while agent.is_running:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
