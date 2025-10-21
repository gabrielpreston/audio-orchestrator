"""Echo agent that simply repeats user input."""

from orchestrator.base_agent import BaseAgent, AgentResponse
from audio_pipeline.types import ConversationContext


class EchoAgent(BaseAgent):
    """Simple echo agent that repeats user input as response."""

    async def handle(self, context: ConversationContext, transcript: str) -> AgentResponse:
        """Echo the user's transcript back as response text.

        Args:
            context: The current conversation context
            transcript: The transcribed user input

        Returns:
            Agent response with the echoed transcript
        """
        return AgentResponse(response_text=transcript)
