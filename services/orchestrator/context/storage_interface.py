"""
Abstract storage interface for context and session management.

This module defines the abstract interface that all storage backends must implement
for persisting conversation context and session data.
"""

from abc import ABC, abstractmethod
from typing import Any

from .types import ConversationContext, Session


class StorageInterface(ABC):
    """Abstract interface for context/session storage.

    This interface defines the contract that all storage backends must implement
    for persisting conversation context and session data. Implementations can
    use in-memory storage, SQL databases, or other persistence mechanisms.
    """

    @abstractmethod
    async def get_session(self, session_id: str) -> Session:
        """Retrieve or create a session.

        Args:
            session_id: Unique session identifier

        Returns:
            Session object (created if it doesn't exist)

        Raises:
            StorageError: If session cannot be retrieved or created
        """
        pass

    @abstractmethod
    async def save_context(self, session_id: str, context: ConversationContext) -> None:
        """Save conversation context.

        Args:
            session_id: Associated session identifier
            context: Conversation context to save

        Raises:
            StorageError: If context cannot be saved
        """
        pass

    @abstractmethod
    async def get_context(self, session_id: str) -> ConversationContext | None:
        """Retrieve conversation context for a session.

        Args:
            session_id: Session identifier

        Returns:
            Conversation context if found, None otherwise

        Raises:
            StorageError: If context cannot be retrieved
        """
        pass

    @abstractmethod
    async def log_agent_execution(
        self,
        session_id: str,
        agent_name: str,
        transcript: str,
        response_text: str,
        latency_ms: int,
    ) -> None:
        """Log agent execution for analytics.

        Args:
            session_id: Session identifier
            agent_name: Name of the agent that executed
            transcript: User transcript that triggered the agent
            response_text: Agent's response text
            latency_ms: Execution latency in milliseconds

        Raises:
            StorageError: If execution cannot be logged
        """
        pass

    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        """Delete a session and its associated context.

        Args:
            session_id: Session identifier to delete

        Raises:
            StorageError: If session cannot be deleted
        """
        pass

    @abstractmethod
    async def list_sessions(self, limit: int = 100) -> list[str]:
        """List active session identifiers.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session identifiers

        Raises:
            StorageError: If sessions cannot be listed
        """
        pass

    @abstractmethod
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions.

        Returns:
            Number of sessions cleaned up

        Raises:
            StorageError: If cleanup fails
        """
        pass

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Get storage statistics.

        Returns:
            Dictionary containing storage statistics
        """
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Perform health check for storage.

        Returns:
            Health check results
        """
        pass


class StorageError(Exception):
    """Exception raised for storage-related errors."""

    def __init__(self, message: str, original_error: Exception | None = None):
        """Initialize storage error.

        Args:
            message: Error message
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.original_error = original_error
