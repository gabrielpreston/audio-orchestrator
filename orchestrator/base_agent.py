"""Base agent interface and response types."""

from abc import ABC, abstractmethod
from typing import Optional, List, AsyncIterator
from audio_pipeline.types import ConversationContext, ExternalAction, AudioChunk


class AgentResponse:
    """Response from an agent containing text, audio, and actions."""

    def __init__(
        self,
        response_text: Optional[str] = None,
        response_audio: Optional[AsyncIterator[AudioChunk]] = None,
        actions: Optional[List[ExternalAction]] = None,
    ):
        """Initialize an agent response.

        Args:
            response_text: Text response to be spoken or displayed
            response_audio: Audio stream to be played
            actions: External actions to be performed
        """
        self.response_text = response_text
        self.response_audio = response_audio
        self.actions = actions or []


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    @abstractmethod
    async def handle(self, context: ConversationContext, transcript: str) -> AgentResponse:
        """Handle a conversation turn.

        Args:
            context: The current conversation context
            transcript: The transcribed user input

        Returns:
            Agent response containing text, audio, and/or actions
        """
        pass
