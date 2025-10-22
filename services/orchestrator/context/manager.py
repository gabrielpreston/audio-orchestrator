"""Context manager for conversation lifecycle management.

This module provides the ContextManager class that coordinates conversation
context and session management within the orchestrator service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from services.common.logging import get_logger

from .storage_interface import StorageInterface, StorageError
from .types import ConversationContext, Session


logger = get_logger(__name__)


class ContextManager:
    """Manages conversation context lifecycle.

    This class provides the main interface for managing conversation context
    and sessions, coordinating with storage backends for persistence.
    """

    def __init__(self, storage: StorageInterface) -> None:
        """Initialize context manager.

        Args:
            storage: Storage backend for persistence
        """
        self.storage = storage
        self._logger = get_logger(self.__class__.__name__)

        self._logger.info(
            "Context manager initialized",
            extra={"storage_type": storage.__class__.__name__},
        )

    async def get_context(self, session_id: str) -> ConversationContext:
        """Get or create context for session.

        Args:
            session_id: Session identifier

        Returns:
            Conversation context (created if none exists)

        Raises:
            StorageError: If context cannot be retrieved or created
        """
        try:
            # Try to load existing context
            existing_context = await self.storage.get_context(session_id)

            if existing_context:
                self._logger.debug(
                    "Retrieved existing context",
                    extra={
                        "session_id": session_id,
                        "history_length": len(existing_context.history),
                        "context_age_seconds": (
                            datetime.now() - existing_context.created_at
                        ).total_seconds(),
                    },
                )
                return existing_context

            # Create new context if none exists
            session = await self.storage.get_session(session_id)

            new_context = ConversationContext(
                session_id=session_id,
                history=[],
                created_at=session.created_at,
                last_active_at=session.last_active_at,
                metadata={
                    "created_by": "ContextManager",
                    "storage_backend": self.storage.__class__.__name__,
                },
            )

            # Save the new context
            await self.storage.save_context(session_id, new_context)

            self._logger.info(
                "Created new context",
                extra={
                    "session_id": session_id,
                    "session_created_at": session.created_at.isoformat(),
                },
            )

            return new_context

        except Exception as e:
            self._logger.error(
                "Error getting context",
                extra={"session_id": session_id, "error": str(e)},
            )
            raise StorageError(f"Failed to get context for session {session_id}", e)

    async def update_context(self, context: ConversationContext) -> None:
        """Update and persist context.

        Args:
            context: Conversation context to update

        Raises:
            StorageError: If context cannot be updated
        """
        try:
            # Update last active time
            context.last_active_at = datetime.now()

            # Save to storage
            await self.storage.save_context(context.session_id, context)

            self._logger.info(
                "Context updated",
                extra={
                    "session_id": context.session_id,
                    "history_length": len(context.history),
                    "last_active_at": context.last_active_at.isoformat(),
                },
            )

        except Exception as e:
            self._logger.error(
                "Error updating context",
                extra={"session_id": context.session_id, "error": str(e)},
            )
            raise StorageError(
                f"Failed to update context for session {context.session_id}", e
            )

    async def save_context(self, context: ConversationContext) -> None:
        """Explicitly save context.

        Args:
            context: Conversation context to save

        Raises:
            StorageError: If context cannot be saved
        """
        try:
            await self.storage.save_context(context.session_id, context)

            self._logger.debug(
                "Context saved explicitly",
                extra={
                    "session_id": context.session_id,
                    "history_length": len(context.history),
                },
            )

        except Exception as e:
            self._logger.error(
                "Error saving context",
                extra={"session_id": context.session_id, "error": str(e)},
            )
            raise StorageError(
                f"Failed to save context for session {context.session_id}", e
            )

    async def add_interaction(
        self, session_id: str, user_message: str, agent_response: str
    ) -> ConversationContext:
        """Add a new interaction to the conversation.

        Args:
            session_id: Session identifier
            user_message: User's message
            agent_response: Agent's response

        Returns:
            Updated conversation context

        Raises:
            StorageError: If interaction cannot be added
        """
        try:
            # Get current context
            context = await self.get_context(session_id)

            # Add the interaction
            context.add_interaction(user_message, agent_response)

            # Update and save
            await self.update_context(context)

            self._logger.info(
                "Interaction added",
                extra={
                    "session_id": session_id,
                    "user_message_length": len(user_message),
                    "agent_response_length": len(agent_response),
                    "total_interactions": len(context.history),
                },
            )

            return context

        except Exception as e:
            self._logger.error(
                "Error adding interaction",
                extra={
                    "session_id": session_id,
                    "user_message_length": len(user_message),
                    "error": str(e),
                },
            )
            raise StorageError(f"Failed to add interaction for session {session_id}", e)

    async def get_session(self, session_id: str) -> Session:
        """Get session information.

        Args:
            session_id: Session identifier

        Returns:
            Session object

        Raises:
            StorageError: If session cannot be retrieved
        """
        try:
            session = await self.storage.get_session(session_id)

            self._logger.debug(
                "Session retrieved",
                extra={
                    "session_id": session_id,
                    "created_at": session.created_at.isoformat(),
                    "last_active_at": session.last_active_at.isoformat(),
                },
            )

            return session

        except Exception as e:
            self._logger.error(
                "Error getting session",
                extra={"session_id": session_id, "error": str(e)},
            )
            raise StorageError(f"Failed to get session {session_id}", e)

    async def delete_session(self, session_id: str) -> None:
        """Delete a session and its context.

        Args:
            session_id: Session identifier to delete

        Raises:
            StorageError: If session cannot be deleted
        """
        try:
            await self.storage.delete_session(session_id)

            self._logger.info("Session deleted", extra={"session_id": session_id})

        except Exception as e:
            self._logger.error(
                "Error deleting session",
                extra={"session_id": session_id, "error": str(e)},
            )
            raise StorageError(f"Failed to delete session {session_id}", e)

    async def list_sessions(self, limit: int = 100) -> list[str]:
        """List active sessions.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session identifiers

        Raises:
            StorageError: If sessions cannot be listed
        """
        try:
            session_ids: list[str] = await self.storage.list_sessions(limit)

            self._logger.debug(
                "Sessions listed",
                extra={"returned_count": len(session_ids), "limit": limit},
            )

            return session_ids

        except Exception as e:
            self._logger.error("Error listing sessions", extra={"error": str(e)})
            raise StorageError("Failed to list sessions", e)

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions.

        Returns:
            Number of sessions cleaned up

        Raises:
            StorageError: If cleanup fails
        """
        try:
            cleaned_count: int = await self.storage.cleanup_expired_sessions()

            if cleaned_count > 0:
                self._logger.info(
                    "Expired sessions cleaned up",
                    extra={"cleaned_count": cleaned_count},
                )

            return cleaned_count

        except Exception as e:
            self._logger.error(
                "Error cleaning up expired sessions", extra={"error": str(e)}
            )
            raise StorageError("Failed to cleanup expired sessions", e)

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
        try:
            await self.storage.log_agent_execution(
                session_id, agent_name, transcript, response_text, latency_ms
            )

            self._logger.debug(
                "Agent execution logged",
                extra={
                    "session_id": session_id,
                    "agent_name": agent_name,
                    "latency_ms": latency_ms,
                },
            )

        except Exception as e:
            self._logger.error(
                "Error logging agent execution",
                extra={
                    "session_id": session_id,
                    "agent_name": agent_name,
                    "error": str(e),
                },
            )
            raise StorageError(
                f"Failed to log agent execution for session {session_id}", e
            )

    async def get_stats(self) -> dict[str, Any]:
        """Get context manager statistics.

        Returns:
            Dictionary containing manager statistics
        """
        try:
            storage_stats = await self.storage.get_stats()

            return {
                "manager_type": "ContextManager",
                "storage_backend": self.storage.__class__.__name__,
                "storage_stats": storage_stats,
            }

        except Exception as e:
            self._logger.error("Error getting stats", extra={"error": str(e)})
            return {
                "manager_type": "ContextManager",
                "storage_backend": self.storage.__class__.__name__,
                "error": str(e),
            }

    async def health_check(self) -> dict[str, Any]:
        """Perform health check for context manager.

        Returns:
            Health check results
        """
        try:
            storage_health = await self.storage.health_check()

            return {
                "status": "healthy",
                "manager_type": "ContextManager",
                "storage_backend": self.storage.__class__.__name__,
                "storage_health": storage_health,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "manager_type": "ContextManager",
                "storage_backend": self.storage.__class__.__name__,
                "error": str(e),
            }
