"""Agent framework for audio-orchestrator services.

This module provides the core abstractions for pluggable agents within the orchestrator service,
enabling flexible response generation strategies.

Key Components:
- BaseAgent: Abstract base class for all agents
- AgentResponse: Response data structure with text, audio, and actions
- ConversationContext: Conversation state and history management
- AgentManager: Agent selection and routing
- AgentRegistry: Agent registration and discovery

Usage:
    from services.orchestrator.agents import BaseAgent, AgentResponse, ConversationContext

    class MyAgent(BaseAgent):
        async def handle(self, context: ConversationContext, transcript: str) -> AgentResponse:
            return AgentResponse(response_text="Hello from my agent!")
"""

from .base import BaseAgent
from .echo_agent import EchoAgent
from .intent_agent import IntentClassificationAgent
from .manager import AgentManager
from .registry import AgentRegistry
from .summarization_agent import SummarizationAgent
from .types import AgentResponse, ConversationContext, ExternalAction


__all__ = [
    "AgentManager",
    "AgentRegistry",
    "AgentResponse",
    "BaseAgent",
    "ConversationContext",
    "EchoAgent",
    "ExternalAction",
    "IntentClassificationAgent",
    "SummarizationAgent",
]
