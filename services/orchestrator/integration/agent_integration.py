"""Integration between audio pipeline and agent framework.

This module provides the integration layer between the audio pipeline
and the agent framework, enabling processed audio to be handled by agents.
"""

from __future__ import annotations

import asyncio
from typing import Any

from services.common.logging import get_logger

from ..agents.manager import AgentManager
from ..agents.types import ConversationContext
from ..pipeline.types import ProcessedSegment

logger = get_logger(__name__)


class AgentIntegration:
    """Integration between audio pipeline and agent framework.
    
    This class coordinates the flow of processed audio segments
    to the appropriate agents for response generation.
    """
    
    def __init__(
        self,
        agent_manager: AgentManager,
    ) -> None:
        """Initialize the agent integration.
        
        Args:
            agent_manager: Manager for agents
        """
        self.agent_manager = agent_manager
        self._logger = get_logger(self.__class__.__name__)
        
        # Session state
        self._active_sessions: dict[str, ConversationContext] = {}
        
        self._logger.info(
            "Agent integration initialized",
            extra={"agent_count": len(self.agent_manager.registry)}
        )
    
    async def handle_processed_segment(
        self,
        processed_segment: ProcessedSegment,
        session_id: str,
    ) -> None:
        """Handle a processed audio segment with agents.
        
        Args:
            processed_segment: Processed audio segment
            session_id: Session identifier
        """
        try:
            self._logger.debug(
                "Handling processed segment with agents",
                extra={
                    "correlation_id": processed_segment.correlation_id,
                    "session_id": session_id,
                    "wake_detected": processed_segment.wake_detected,
                }
            )
            
            # Only process segments with wake detection
            if not processed_segment.wake_detected:
                return
            
            # Get or create conversation context
            context = await self._get_or_create_context(session_id)
            
            # Create transcript from processed segment
            # For now, create a mock transcript
            transcript = f"User said: {processed_segment.wake_phrase or 'something'}"
            
            # Process with agents
            await self._process_with_agents(context, transcript, processed_segment)
            
        except Exception as e:
            self._logger.error(
                "Error handling processed segment with agents",
                extra={
                    "correlation_id": processed_segment.correlation_id,
                    "session_id": session_id,
                    "error": str(e),
                }
            )
    
    async def _get_or_create_context(self, session_id: str) -> ConversationContext:
        """Get or create conversation context for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Conversation context
        """
        if session_id not in self._active_sessions:
            from datetime import datetime
            
            context = ConversationContext(
                session_id=session_id,
                history=[],
                created_at=datetime.now(),
                last_active_at=datetime.now(),
            )
            
            self._active_sessions[session_id] = context
            
            self._logger.info(
                "Created new conversation context",
                extra={"session_id": session_id}
            )
        
        return self._active_sessions[session_id]
    
    async def _process_with_agents(
        self,
        context: ConversationContext,
        transcript: str,
        processed_segment: ProcessedSegment,
    ) -> None:
        """Process transcript with agents.
        
        Args:
            context: Conversation context
            transcript: Transcribed text
            processed_segment: Original processed segment
        """
        try:
            # Select appropriate agent
            agent = await self.agent_manager.select_agent(context, transcript)
            
            if not agent:
                self._logger.warning(
                    "No agent selected for transcript",
                    extra={
                        "session_id": context.session_id,
                        "transcript": transcript,
                    }
                )
                return
            
            self._logger.info(
                "Selected agent for processing",
                extra={
                    "session_id": context.session_id,
                    "agent_name": agent.name,
                    "transcript": transcript,
                }
            )
            
            # Process with selected agent
            response = await self.agent_manager.process_transcript(
                context, transcript
            )
            
            # Update conversation history
            context.history.append((transcript, response.response_text or ""))
            context.last_active_at = processed_segment.processed_at
            
            self._logger.info(
                "Agent processing completed",
                extra={
                    "session_id": context.session_id,
                    "agent_name": agent.name,
                    "response_length": len(response.response_text or ""),
                    "actions_count": len(response.actions),
                }
            )
            
        except Exception as e:
            self._logger.error(
                "Error processing with agents",
                extra={
                    "session_id": context.session_id,
                    "transcript": transcript,
                    "error": str(e),
                }
            )
    
    async def end_session(self, session_id: str) -> None:
        """End a conversation session.
        
        Args:
            session_id: Session identifier
        """
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]
            
            self._logger.info(
                "Ended conversation session",
                extra={"session_id": session_id}
            )
    
    async def get_session_context(self, session_id: str) -> ConversationContext | None:
        """Get conversation context for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Conversation context or None if not found
        """
        return self._active_sessions.get(session_id)
    
    async def get_active_sessions(self) -> list[str]:
        """Get list of active session IDs.
        
        Returns:
            List of active session IDs
        """
        return list(self._active_sessions.keys())
    
    async def get_status(self) -> dict[str, Any]:
        """Get integration status.
        
        Returns:
            Dictionary containing integration status
        """
        return {
            "active_sessions": len(self._active_sessions),
            "session_ids": list(self._active_sessions.keys()),
            "agent_manager": await self.agent_manager.get_stats(),
        }
    
    async def health_check(self) -> dict[str, Any]:
        """Perform health check for the integration.
        
        Returns:
            Health check results
        """
        return {
            "status": "healthy",
            "integration_type": "AgentIntegration",
            "active_sessions": len(self._active_sessions),
            "agent_manager": await self.agent_manager.get_stats(),
        }
