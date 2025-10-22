"""Summarization agent implementation.

This agent provides conversation summarization capabilities using LLM integration.
It can summarize conversation history and provide contextual summaries.
"""

from __future__ import annotations

from typing import Any

import httpx
from services.common.logging import get_logger

from .base import BaseAgent
from .types import AgentResponse, ConversationContext


logger = get_logger(__name__)


class SummarizationAgent(BaseAgent):
    """Agent that summarizes conversation history using LLM integration.

    This agent can:
    - Summarize conversation history
    - Provide contextual summaries
    - Handle summarization requests with various triggers
    """

    def __init__(self, llm_service_url: str, **kwargs: Any) -> None:
        """Initialize the summarization agent.

        Args:
            llm_service_url: URL of the LLM service for summarization
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.llm_url = llm_service_url.rstrip("/")
        self._logger.info(
            "SummarizationAgent initialized", extra={"llm_url": self.llm_url}
        )

    @property
    def name(self) -> str:
        """Agent identifier."""
        return "summarization"

    async def handle(
        self, context: ConversationContext, transcript: str
    ) -> AgentResponse:
        """Generate summary of conversation history.

        Args:
            context: Conversation context with history
            transcript: User's request (e.g., "summarize our conversation")

        Returns:
            AgentResponse with summary text
        """
        self._logger.info(
            "Processing summarization request",
            extra={
                "session_id": context.session_id,
                "transcript": transcript,
                "history_length": len(context.history),
            },
        )

        # Check if there's conversation history to summarize
        if not context.history:
            return AgentResponse(
                response_text="There's no conversation history to summarize yet. "
                "Let's have a conversation first!",
                metadata={
                    "agent_name": self.name,
                    "history_length": 0,
                    "summary_type": "no_history",
                },
            )

        # Build conversation history for LLM
        history_text = self._build_conversation_history(context)

        # Generate summary using LLM
        try:
            summary = await self._generate_summary(history_text, transcript)

            return AgentResponse(
                response_text=summary,
                metadata={
                    "agent_name": self.name,
                    "history_length": len(context.history),
                    "summary_type": "conversation_summary",
                    "llm_url": self.llm_url,
                },
            )
        except Exception as e:
            self._logger.error(
                "Failed to generate summary",
                extra={
                    "session_id": context.session_id,
                    "error": str(e),
                    "llm_url": self.llm_url,
                },
            )

            # Fallback response
            return AgentResponse(
                response_text=(
                    "I'm having trouble generating a summary right now. "
                    "Here's a brief overview: We've had "
                    f"{len(context.history)} conversation turns so far."
                ),
                metadata={
                    "agent_name": self.name,
                    "history_length": len(context.history),
                    "summary_type": "fallback",
                    "error": str(e),
                },
            )

    async def can_handle(self, context: ConversationContext, transcript: str) -> bool:
        """Check if this agent can handle the summarization request.

        Args:
            context: Current conversation context
            transcript: User's transcribed speech input

        Returns:
            True if this looks like a summarization request
        """
        # Check for summarization keywords
        summary_keywords = [
            "summarize",
            "summary",
            "recap",
            "overview",
            "what did we talk about",
            "conversation summary",
            "brief",
            "sum up",
            "key points",
        ]

        transcript_lower = transcript.lower().strip()

        # Check if transcript contains summarization keywords
        for keyword in summary_keywords:
            if keyword in transcript_lower:
                return True

        # Check if it's a very short request that might be asking for summary
        if len(transcript.strip()) < 20 and any(
            word in transcript_lower
            for word in [
                "what did we",
                "tell me about",
                "show me what",
                "give me a summary",
            ]
        ):
            return True

        return False

    async def get_capabilities(self) -> list[str]:
        """Get summarization agent capabilities.

        Returns:
            List of capability strings
        """
        return [
            "Summarize conversation history",
            "Provide conversation overviews",
            "Generate contextual summaries",
            "Handle summarization requests",
        ]

    def _build_conversation_history(self, context: ConversationContext) -> str:
        """Build formatted conversation history for LLM.

        Args:
            context: Conversation context with history

        Returns:
            Formatted conversation history string
        """
        if not context.history:
            return "No conversation history available."

        history_lines = []
        for i, (user_input, agent_response) in enumerate(context.history, 1):
            history_lines.append(f"Turn {i}:")
            history_lines.append(f"User: {user_input}")
            history_lines.append(f"Assistant: {agent_response}")
            history_lines.append("")  # Empty line for readability

        return "\n".join(history_lines)

    async def _generate_summary(self, history_text: str, user_request: str) -> str:
        """Generate summary using LLM service.

        Args:
            history_text: Formatted conversation history
            user_request: User's specific summarization request

        Returns:
            Generated summary text

        Raises:
            Exception: If LLM service call fails
        """
        # Build prompt for LLM
        prompt = self._build_summarization_prompt(history_text, user_request)

        # Call LLM service
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.llm_url}/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",  # Default model
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that provides clear, concise summaries of conversations.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 500,
                    "temperature": 0.3,  # Lower temperature for more focused summaries
                },
            )

            if response.status_code != 200:
                raise Exception(
                    f"LLM service error: {response.status_code} - {response.text}"
                )

            result = response.json()

            if "choices" not in result or not result["choices"]:
                raise Exception("Invalid response from LLM service")

            content = result["choices"][0]["message"]["content"]
            return str(content).strip()

    def _build_summarization_prompt(self, history_text: str, user_request: str) -> str:
        """Build the prompt for LLM summarization.

        Args:
            history_text: Formatted conversation history
            user_request: User's specific request

        Returns:
            Complete prompt for LLM
        """
        return f"""Please provide a clear and concise summary of the following conversation.

User's request: {user_request}

Conversation history:
{history_text}

Please provide a summary that:
1. Captures the main topics discussed
2. Highlights key points and decisions
3. Is concise but comprehensive
4. Addresses the user's specific request

Summary:"""

    async def health_check(self) -> dict[str, Any]:
        """Perform health check for the summarization agent.

        Returns:
            Health check results including LLM service connectivity
        """
        base_health = await super().health_check()

        # Test LLM service connectivity
        llm_healthy = False
        llm_error = None

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.llm_url}/health")
                llm_healthy = response.status_code == 200
        except Exception as e:
            llm_error = str(e)

        return {
            **base_health,
            "llm_service_url": self.llm_url,
            "llm_service_healthy": llm_healthy,
            "llm_error": llm_error,
        }
