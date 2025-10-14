"""Session management for LiveKit agent service."""

import asyncio
import time
from typing import Dict, Optional, Set

from livekit import rtc
from services.common.audio_contracts import (
    SessionState,
    EndpointingState,
    PlaybackAction,
    AudioRoute,
    AudioInput,
    ControlMessage,
    WakeDetectedMessage,
    VADStartSpeechMessage,
    VADEndSpeechMessage,
    BargeInRequestMessage,
    SessionStateMessage,
    RouteChangeMessage,
    PlaybackControlMessage,
    EndpointingMessage,
    TranscriptPartialMessage,
    TranscriptFinalMessage,
    ErrorMessage,
    TelemetrySnapshotMessage,
    AudioFrame,
    AudioSegment,
    WordTiming
)
from services.common.logging import get_logger


class MobileSession:
    """Represents a mobile voice assistant session."""
    
    def __init__(self, room: rtc.Room, participant: rtc.RemoteParticipant, correlation_id: str):
        self.room = room
        self.participant = participant
        self.correlation_id = correlation_id
        self.logger = get_logger("mobile_session", correlation_id=correlation_id)
        
        # Session state
        self.state = SessionState.IDLE
        self.endpointing_state = EndpointingState.LISTENING
        self.start_time = time.time()
        self.last_activity = time.time()
        
        # Audio configuration
        self.audio_route = AudioRoute.SPEAKER
        self.audio_input = AudioInput.BUILT_IN
        self.is_muted = False
        
        # Wake word and VAD
        self.wake_armed = True
        self.last_wake_time = 0.0
        self.speech_start_time = 0.0
        self.speech_duration = 0.0
        
        # Barge-in state
        self.barge_in_enabled = True
        self.is_responding = False
        self.response_paused = False
        self.pause_start_time = 0.0
        self.max_pause_duration = 10.0  # seconds
        
        # Audio processing
        self.audio_frames: list[AudioFrame] = []
        self.current_transcript = ""
        self.transcript_history: list[AudioSegment] = []
        
        # Telemetry
        self.stats = {
            "frames_processed": 0,
            "transcripts_processed": 0,
            "barge_ins": 0,
            "errors": 0,
            "rtt_ms": 0.0,
            "packet_loss_percent": 0.0,
            "jitter_ms": 0.0
        }
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = time.time()
    
    def is_expired(self, max_duration_minutes: int = 30) -> bool:
        """Check if session has expired."""
        return (time.time() - self.start_time) > (max_duration_minutes * 60)
    
    def can_barge_in(self) -> bool:
        """Check if barge-in is currently allowed."""
        return (
            self.barge_in_enabled and
            self.is_responding and
            not self.response_paused and
            (time.time() - self.pause_start_time) < self.max_pause_duration
        )


class SessionManager:
    """Manages mobile voice assistant sessions."""
    
    def __init__(self, max_sessions: int = 100):
        self.max_sessions = max_sessions
        self.logger = get_logger("session_manager")
        self._sessions: Dict[str, MobileSession] = {}
        self._room_sessions: Dict[str, Set[str]] = {}  # room_name -> session_ids
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the session manager."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.logger.info("session_manager.started")
    
    async def stop(self):
        """Stop the session manager."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Clean up all sessions
        for session in list(self._sessions.values()):
            await self._cleanup_session(session)
        
        self.logger.info("session_manager.stopped")
    
    async def create_session(
        self,
        room: rtc.Room,
        participant: rtc.RemoteParticipant,
        correlation_id: str
    ) -> MobileSession:
        """Create a new mobile session."""
        if len(self._sessions) >= self.max_sessions:
            # Remove oldest session
            oldest_session = min(self._sessions.values(), key=lambda s: s.start_time)
            await self.remove_session(oldest_session.correlation_id)
        
        session = MobileSession(room, participant, correlation_id)
        self._sessions[correlation_id] = session
        
        # Track by room
        room_name = room.name
        if room_name not in self._room_sessions:
            self._room_sessions[room_name] = set()
        self._room_sessions[room_name].add(correlation_id)
        
        self.logger.info(
            "session.created",
            correlation_id=correlation_id,
            room_name=room_name,
            participant_identity=participant.identity,
            total_sessions=len(self._sessions)
        )
        
        return session
    
    async def get_session(self, correlation_id: str) -> Optional[MobileSession]:
        """Get a session by correlation ID."""
        return self._sessions.get(correlation_id)
    
    async def remove_session(self, correlation_id: str) -> bool:
        """Remove a session."""
        session = self._sessions.get(correlation_id)
        if not session:
            return False
        
        await self._cleanup_session(session)
        
        # Remove from room tracking
        room_name = session.room.name
        if room_name in self._room_sessions:
            self._room_sessions[room_name].discard(correlation_id)
            if not self._room_sessions[room_name]:
                del self._room_sessions[room_name]
        
        del self._sessions[correlation_id]
        
        self.logger.info(
            "session.removed",
            correlation_id=correlation_id,
            total_sessions=len(self._sessions)
        )
        
        return True
    
    async def get_room_sessions(self, room_name: str) -> list[MobileSession]:
        """Get all sessions for a room."""
        session_ids = self._room_sessions.get(room_name, set())
        return [self._sessions[sid] for sid in session_ids if sid in self._sessions]
    
    async def handle_control_message(
        self,
        session: MobileSession,
        message: ControlMessage
    ) -> Optional[ControlMessage]:
        """Handle a control message from the client."""
        session.update_activity()
        
        try:
            if message.message_type.value == "wake.detected":
                return await self._handle_wake_detected(session, message)
            elif message.message_type.value == "vad.start_speech":
                return await self._handle_vad_start_speech(session, message)
            elif message.message_type.value == "vad.end_speech":
                return await self._handle_vad_end_speech(session, message)
            elif message.message_type.value == "barge_in.request":
                return await self._handle_barge_in_request(session, message)
            elif message.message_type.value == "session.state":
                return await self._handle_session_state(session, message)
            elif message.message_type.value == "route.change":
                return await self._handle_route_change(session, message)
            else:
                self.logger.warning(
                    "session.unknown_message_type",
                    correlation_id=session.correlation_id,
                    message_type=message.message_type.value
                )
                return None
                
        except Exception as e:
            self.logger.error(
                "session.message_handling_error",
                correlation_id=session.correlation_id,
                error=str(e),
                message_type=message.message_type.value
            )
            session.stats["errors"] += 1
            return ErrorMessage(
                session.correlation_id,
                "MESSAGE_HANDLING_ERROR",
                f"Failed to handle message: {e}",
                recoverable=True
            )
    
    async def _handle_wake_detected(
        self,
        session: MobileSession,
        message: ControlMessage
    ) -> Optional[ControlMessage]:
        """Handle wake word detection."""
        confidence = message.payload.get("confidence", 0.0)
        current_time = time.time()
        
        # Check cooldown
        if current_time - session.last_wake_time < 1.0:  # 1 second cooldown
            return None
        
        session.last_wake_time = current_time
        session.state = SessionState.ARMING
        
        self.logger.info(
            "session.wake_detected",
            correlation_id=session.correlation_id,
            confidence=confidence
        )
        
        # Transition to live listen state
        session.state = SessionState.LIVE_LISTEN
        session.endpointing_state = EndpointingState.LISTENING
        
        return EndpointingMessage(
            session.correlation_id,
            session.endpointing_state.value
        )
    
    async def _handle_vad_start_speech(
        self,
        session: MobileSession,
        message: ControlMessage
    ) -> Optional[ControlMessage]:
        """Handle VAD speech start."""
        session.speech_start_time = time.time()
        session.state = SessionState.LIVE_LISTEN
        session.endpointing_state = EndpointingState.LISTENING
        
        # Handle barge-in if responding
        if session.is_responding and session.can_barge_in():
            session.response_paused = True
            session.pause_start_time = time.time()
            session.stats["barge_ins"] += 1
            
            self.logger.info(
                "session.barge_in_triggered",
                correlation_id=session.correlation_id
            )
            
            return PlaybackControlMessage(
                session.correlation_id,
                PlaybackAction.PAUSE.value,
                "user_speaking"
            )
        
        return None
    
    async def _handle_vad_end_speech(
        self,
        session: MobileSession,
        message: ControlMessage
    ) -> Optional[ControlMessage]:
        """Handle VAD speech end."""
        duration_ms = message.payload.get("duration_ms", 0)
        session.speech_duration = duration_ms / 1000.0
        
        # Transition to processing state
        session.state = SessionState.PROCESSING
        session.endpointing_state = EndpointingState.PROCESSING
        
        self.logger.info(
            "session.speech_ended",
            correlation_id=session.correlation_id,
            duration_ms=duration_ms
        )
        
        return EndpointingMessage(
            session.correlation_id,
            session.endpointing_state.value
        )
    
    async def _handle_barge_in_request(
        self,
        session: MobileSession,
        message: ControlMessage
    ) -> Optional[ControlMessage]:
        """Handle barge-in request."""
        reason = message.payload.get("reason", "unknown")
        
        if session.can_barge_in():
            session.response_paused = True
            session.pause_start_time = time.time()
            session.stats["barge_ins"] += 1
            
            self.logger.info(
                "session.barge_in_requested",
                correlation_id=session.correlation_id,
                reason=reason
            )
            
            return PlaybackControlMessage(
                session.correlation_id,
                PlaybackAction.PAUSE.value,
                reason
            )
        
        return None
    
    async def _handle_session_state(
        self,
        session: MobileSession,
        message: ControlMessage
    ) -> Optional[ControlMessage]:
        """Handle session state change."""
        action = message.payload.get("action", "")
        
        if action == "mute":
            session.is_muted = True
        elif action == "unmute":
            session.is_muted = False
        elif action == "leave":
            session.state = SessionState.TEARDOWN
            await self.remove_session(session.correlation_id)
            return None
        
        self.logger.info(
            "session.state_changed",
            correlation_id=session.correlation_id,
            action=action,
            is_muted=session.is_muted
        )
        
        return None
    
    async def _handle_route_change(
        self,
        session: MobileSession,
        message: ControlMessage
    ) -> Optional[ControlMessage]:
        """Handle audio route change."""
        output = message.payload.get("output", "speaker")
        input_source = message.payload.get("input", "built_in")
        
        try:
            session.audio_route = AudioRoute(output)
            session.audio_input = AudioInput(input_source)
            
            self.logger.info(
                "session.route_changed",
                correlation_id=session.correlation_id,
                output=output,
                input=input_source
            )
            
        except ValueError as e:
            self.logger.warning(
                "session.invalid_route",
                correlation_id=session.correlation_id,
                output=output,
                input=input_source,
                error=str(e)
            )
        
        return None
    
    async def _cleanup_session(self, session: MobileSession):
        """Clean up a session."""
        try:
            # Send teardown message if needed
            if session.state != SessionState.TEARDOWN:
                session.state = SessionState.TEARDOWN
                
            self.logger.info(
                "session.cleanup",
                correlation_id=session.correlation_id,
                duration=time.time() - session.start_time,
                stats=session.stats
            )
            
        except Exception as e:
            self.logger.error(
                "session.cleanup_error",
                correlation_id=session.correlation_id,
                error=str(e)
            )
    
    async def _cleanup_loop(self):
        """Background cleanup loop."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                current_time = time.time()
                expired_sessions = []
                
                for session in self._sessions.values():
                    if session.is_expired() or (current_time - session.last_activity) > 300:  # 5 minutes
                        expired_sessions.append(session.correlation_id)
                
                for correlation_id in expired_sessions:
                    await self.remove_session(correlation_id)
                
                if expired_sessions:
                    self.logger.info(
                        "session.cleanup_completed",
                        expired_count=len(expired_sessions),
                        remaining_sessions=len(self._sessions)
                    )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("session.cleanup_loop_error", error=str(e))