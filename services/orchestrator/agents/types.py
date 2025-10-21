"""Core type definitions for the agent framework.

This module defines the fundamental data structures used throughout the agent system,
including response types, context management, and external actions.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from services.common.logging import get_logger


logger = get_logger(__name__)


@dataclass
class ExternalAction:
    """Represents an external action that an agent can perform.

    This could be calling an API, sending a message, or any other external operation.
    """

    action_type: str
    parameters: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate action data after initialization."""
        if not self.action_type:
            raise ValueError("action_type cannot be empty")
        if not isinstance(self.parameters, dict):
            raise ValueError("parameters must be a dictionary")


@dataclass
class AgentResponse:
    """Response from an agent containing text, audio, and/or actions.

    This is the primary return type for all agent implementations.
    Agents can return text responses, audio streams, or external actions.
    """

    response_text: str | None = None
    response_audio: AsyncIterator[bytes] | None = None
    actions: list[ExternalAction] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate response data after initialization."""
        if not any([self.response_text, self.response_audio, self.actions]):
            logger.warning("AgentResponse created with no content")

        if self.response_text and not isinstance(self.response_text, str):
            raise ValueError("response_text must be a string")

        if self.actions and not all(
            isinstance(action, ExternalAction) for action in self.actions
        ):
            raise ValueError("all actions must be ExternalAction instances")


@dataclass
class ConversationContext:
    """Current conversation state and history.

    This maintains the conversation context across multiple turns,
    including user input, agent responses, and metadata.
    """

    session_id: str
    history: list[tuple[str, str]]  # (user_input, agent_response) pairs
    created_at: datetime
    last_active_at: datetime
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate context data after initialization."""
        if not self.session_id:
            raise ValueError("session_id cannot be empty")

        if not isinstance(self.history, list):
            raise ValueError("history must be a list")

        if not isinstance(self.created_at, datetime):
            raise ValueError("created_at must be a datetime")

        if not isinstance(self.last_active_at, datetime):
            raise ValueError("last_active_at must be a datetime")

    def add_turn(self, user_input: str, agent_response: str) -> None:
        """Add a conversation turn to the history.

        Args:
            user_input: What the user said
            agent_response: How the agent responded
        """
        if not user_input or not agent_response:
            logger.warning("Adding turn with empty input or response")

        self.history.append((user_input, agent_response))
        self.last_active_at = datetime.now()

    def get_recent_history(self, max_turns: int = 10) -> list[tuple[str, str]]:
        """Get the most recent conversation turns.

        Args:
            max_turns: Maximum number of turns to return

        Returns:
            List of (user_input, agent_response) pairs
        """
        return self.history[-max_turns:] if self.history else []

    def get_conversation_summary(self) -> str:
        """Get a summary of the conversation.

        Returns:
            String summary of the conversation
        """
        if not self.history:
            return "No conversation history"

        turn_count = len(self.history)
        duration = (self.last_active_at - self.created_at).total_seconds()

        return f"Conversation with {turn_count} turns over {duration:.1f} seconds"
