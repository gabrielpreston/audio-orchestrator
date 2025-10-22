"""
Context and session type definitions for the orchestrator service.

This module defines the core data structures for managing conversation context
and user sessions, enabling multi-turn conversations and session persistence.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class Session:
    """User session metadata.

    Represents a user session with metadata about when it was created,
    last activity, and any additional session-specific data.

    Attributes:
        id: Unique session identifier
        created_at: When the session was created
        last_active_at: When the session was last active
        metadata: Additional session-specific data
    """

    id: str
    created_at: datetime
    last_active_at: datetime
    metadata: dict[str, Any]


@dataclass
class ConversationContext:
    """Complete conversation state.

    Represents the full state of a conversation including history,
    session information, and metadata.

    Attributes:
        session_id: Associated session identifier
        history: List of (user_message, agent_response) pairs
        created_at: When the conversation context was created
        last_active_at: When the context was last updated
        metadata: Additional context-specific data
    """

    session_id: str
    history: list[tuple[str, str]]  # (user, agent) pairs
    created_at: datetime
    last_active_at: datetime
    metadata: dict[str, Any] | None = None

    def add_interaction(self, user_message: str, agent_response: str) -> None:
        """Add a new user-agent interaction to the history.

        Args:
            user_message: The user's message
            agent_response: The agent's response
        """
        self.history.append((user_message, agent_response))
        self.last_active_at = datetime.now()

    def get_recent_history(self, max_turns: int = 10) -> list[tuple[str, str]]:
        """Get the most recent conversation history.

        Args:
            max_turns: Maximum number of turns to return (must be >= 0)

        Returns:
            List of recent (user, agent) interaction pairs
        """
        if not self.history or max_turns <= 0:
            return []

        # Return the most recent max_turns interactions
        return self.history[-max_turns:]

    def get_conversation_length(self) -> int:
        """Get the total number of interactions in this conversation.

        Returns:
            Number of user-agent interaction pairs
        """
        return len(self.history)

    def is_empty(self) -> bool:
        """Check if the conversation has any history.

        Returns:
            True if no interactions have occurred
        """
        return len(self.history) == 0
