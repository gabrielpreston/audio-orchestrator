"""Multi-turn conversation agent for natural language interactions.

This module provides the ConversationAgent class that handles natural multi-turn
conversations using LLM integration and conversation history management.
"""

import logging
from typing import Any

import httpx
from services.orchestrator.agents.base import BaseAgent
from services.orchestrator.agents.types import AgentResponse, ConversationContext


class ConversationAgent(BaseAgent):
    """Agent for natural multi-turn conversations."""

    def __init__(self, llm_service_url: str, max_history: int = 10):
        """Initialize the conversation agent.

        Args:
            llm_service_url: URL of the LLM service for generating responses
            max_history: Maximum number of turns to keep in history for LLM context
        """
        self.llm_url = llm_service_url
        self.max_history = max_history
        self._logger = logging.getLogger(__name__)

    @property
    def name(self) -> str:
        """Return the agent name."""
        return "conversation"

    async def handle(
        self, context: ConversationContext, transcript: str
    ) -> AgentResponse:
        """Generate contextual response using conversation history.

        Args:
            context: Conversation context with history
            transcript: User's current input

        Returns:
            AgentResponse with contextual response text
        """
        try:
            # Build conversation history for LLM
            messages = self._build_message_history(context)
            messages.append({"role": "user", "content": transcript})

            # Call LLM service with history
            response_text = await self._generate_response(messages)

            return AgentResponse(response_text=response_text)

        except Exception as e:
            self._logger.error(
                "Error in conversation agent",
                extra={
                    "error": str(e),
                    "transcript": transcript[:100] + "..."
                    if len(transcript) > 100
                    else transcript,
                    "session_id": context.session_id,
                },
            )
            return AgentResponse(
                response_text="I'm sorry, I'm having trouble understanding right now."
            )

    def _build_message_history(
        self, context: ConversationContext
    ) -> list[dict[str, str]]:
        """Convert history to LLM message format.

        Args:
            context: Conversation context

        Returns:
            List of messages in LLM format
        """
        messages = []
        for user_msg, agent_msg in context.get_recent_history(self.max_history):
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": agent_msg})
        return messages

    async def _generate_response(self, messages: list[dict[str, str]]) -> str:
        """Call LLM to generate response.

        Args:
            messages: Conversation messages in LLM format

        Returns:
            Generated response text
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.llm_url}/v1/chat/completions",
                    json={
                        "model": "gpt-3.5-turbo",  # TODO: Make configurable
                        "messages": messages,
                        "max_tokens": 150,
                        "temperature": 0.7,
                    },
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()
                return str(result["choices"][0]["message"]["content"]).strip()
        except httpx.HTTPError as e:
            self._logger.error(f"HTTP error calling LLM service: {e}")
            raise
        except Exception as e:
            self._logger.error(f"Error generating LLM response: {e}")
            raise

    async def can_handle(self, context: ConversationContext, transcript: str) -> bool:
        """Determine if this agent can handle the request.

        The conversation agent can handle any request that is not explicitly
        handled by other specialized agents.

        Args:
            context: Conversation context
            transcript: User's transcript

        Returns:
            Always True (as a fallback for general conversation)
        """
        return True  # Acts as a general fallback

    async def health_check(self) -> dict[str, Any]:
        """Check the health of the conversation agent.

        Returns:
            Health status dictionary
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.llm_url}/health/ready")
                llm_healthy = response.status_code == 200
        except Exception:
            llm_healthy = False

        return {
            "agent_name": self.name,
            "llm_service_healthy": llm_healthy,
            "max_history": self.max_history,
        }
