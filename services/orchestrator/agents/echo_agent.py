"""Echo agent implementation.

This is a simple agent that echoes back user input, useful for testing
and as a fallback when other agents cannot handle the input.
"""

from __future__ import annotations

from services.common.logging import get_logger

from .base import BaseAgent
from .types import AgentResponse, ConversationContext

logger = get_logger(__name__)


class EchoAgent(BaseAgent):
    """Simple echo agent that repeats user input.
    
    This agent is useful for:
    - Testing the agent framework
    - Providing a fallback when other agents cannot handle input
    - Demonstrating basic agent functionality
    """
    
    @property
    def name(self) -> str:
        """Agent identifier."""
        return "echo"
    
    async def handle(
        self,
        context: ConversationContext,
        transcript: str
    ) -> AgentResponse:
        """Echo the user's transcript back as response text.
        
        Args:
            context: Current conversation context (unused for echo)
            transcript: User's transcribed speech
            
        Returns:
            AgentResponse with echoed text
        """
        self._logger.info(
            "Echoing user input",
            extra={
                "session_id": context.session_id,
                "transcript_length": len(transcript),
                "history_length": len(context.history)
            }
        )
        
        # Simple echo with some context awareness
        if not transcript.strip():
            response_text = "I didn't hear anything. Could you try again?"
        elif len(transcript) > 500:
            response_text = f"You said a lot! Here's what I heard: {transcript[:100]}..."
        else:
            response_text = f"You said: {transcript}"
        
        return AgentResponse(
            response_text=response_text,
            metadata={
                "agent_name": self.name,
                "input_length": len(transcript),
                "echo_type": "simple"
            }
        )
    
    async def can_handle(self, context: ConversationContext, transcript: str) -> bool:
        """Echo agent can handle any input.
        
        Args:
            context: Current conversation context
            transcript: User's transcribed speech input
            
        Returns:
            Always True - echo agent can handle any input
        """
        return True
    
    async def get_capabilities(self) -> list[str]:
        """Get echo agent capabilities.
        
        Returns:
            List of capability strings
        """
        return [
            "Echo user input back",
            "Handle any text input",
            "Provide fallback responses",
            "Test agent framework"
        ]
