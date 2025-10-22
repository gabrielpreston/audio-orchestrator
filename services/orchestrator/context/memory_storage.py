"""In-memory context storage with LRU eviction.

This module provides an in-memory implementation of the StorageInterface
for conversation context and session management with automatic cleanup.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any

from services.common.logging import get_logger

from .storage_interface import StorageError, StorageInterface
from .types import ConversationContext, Session


logger = get_logger(__name__)


class MemoryStorage(StorageInterface):
    """In-memory context storage with LRU eviction and TTL.

    This implementation provides fast in-memory storage for conversation
    context and sessions with automatic cleanup based on TTL and LRU eviction.
    """

    def __init__(self, max_sessions: int = 1000, ttl_minutes: int = 60) -> None:
        """Initialize memory storage.

        Args:
            max_sessions: Maximum number of sessions to keep in memory
            ttl_minutes: Time-to-live for sessions in minutes
        """
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._contexts: OrderedDict[str, ConversationContext] = OrderedDict()
        self._lock = asyncio.Lock()
        self.max_sessions = max_sessions
        self.ttl = timedelta(minutes=ttl_minutes)

        self._logger = get_logger(self.__class__.__name__)

        self._logger.info(
            "Memory storage initialized",
            extra={
                "max_sessions": self.max_sessions,
                "ttl_minutes": ttl_minutes,
            },
        )

    async def get_session(self, session_id: str) -> Session:
        """Get or create session.

        Args:
            session_id: Unique session identifier

        Returns:
            Session object (created if it doesn't exist)

        Raises:
            StorageError: If session cannot be retrieved or created
        """
        try:
            async with self._lock:
                if session_id not in self._sessions:
                    # Create new session
                    new_session = Session(
                        id=session_id,
                        created_at=datetime.now(),
                        last_active_at=datetime.now(),
                        metadata={},
                    )
                    self._sessions[session_id] = new_session
                    self._logger.info(
                        "Created new session", extra={"session_id": session_id}
                    )
                else:
                    # Update last active time and move to end (LRU)
                    self._sessions[session_id].last_active_at = datetime.now()
                    self._sessions.move_to_end(session_id)
                    self._logger.debug(
                        "Retrieved existing session", extra={"session_id": session_id}
                    )

                # Evict old sessions
                await self._evict_old_sessions()

                return self._sessions[session_id]

        except Exception as e:
            self._logger.error(
                "Error getting session",
                extra={"session_id": session_id, "error": str(e)},
            )
            raise StorageError(f"Failed to get session {session_id}", e)

    async def save_context(self, session_id: str, context: ConversationContext) -> None:
        """Save conversation context.

        Args:
            session_id: Associated session identifier
            context: Conversation context to save

        Raises:
            StorageError: If context cannot be saved
        """
        try:
            async with self._lock:
                self._contexts[session_id] = context

                # Update session last active time
                if session_id in self._sessions:
                    self._sessions[session_id].last_active_at = datetime.now()
                    self._sessions.move_to_end(session_id)

                self._logger.info(
                    "Context saved",
                    extra={
                        "session_id": session_id,
                        "history_length": len(context.history),
                        "context_age_seconds": (
                            datetime.now() - context.created_at
                        ).total_seconds(),
                    },
                )

        except Exception as e:
            self._logger.error(
                "Error saving context",
                extra={"session_id": session_id, "error": str(e)},
            )
            raise StorageError(f"Failed to save context for session {session_id}", e)

    async def get_context(self, session_id: str) -> ConversationContext | None:
        """Retrieve conversation context for a session.

        Args:
            session_id: Session identifier

        Returns:
            Conversation context if found, None otherwise

        Raises:
            StorageError: If context cannot be retrieved
        """
        try:
            async with self._lock:
                context = self._contexts.get(session_id)

                if context:
                    # Update session last active time
                    if session_id in self._sessions:
                        self._sessions[session_id].last_active_at = datetime.now()
                        self._sessions.move_to_end(session_id)

                    self._logger.debug(
                        "Context retrieved",
                        extra={
                            "session_id": session_id,
                            "history_length": len(context.history),
                        },
                    )
                else:
                    self._logger.debug(
                        "Context not found", extra={"session_id": session_id}
                    )

                return context

        except Exception as e:
            self._logger.error(
                "Error getting context",
                extra={"session_id": session_id, "error": str(e)},
            )
            raise StorageError(f"Failed to get context for session {session_id}", e)

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
            # For now, just log to structured logs
            # In a production system, this would write to an analytics database
            self._logger.info(
                "Agent execution logged",
                extra={
                    "session_id": session_id,
                    "agent_name": agent_name,
                    "transcript_length": len(transcript),
                    "response_length": len(response_text),
                    "latency_ms": latency_ms,
                    "timestamp": datetime.now().isoformat(),
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

    async def delete_session(self, session_id: str) -> None:
        """Delete a session and its associated context.

        Args:
            session_id: Session identifier to delete

        Raises:
            StorageError: If session cannot be deleted
        """
        try:
            async with self._lock:
                deleted_sessions = 0
                deleted_contexts = 0

                if session_id in self._sessions:
                    del self._sessions[session_id]
                    deleted_sessions = 1

                if session_id in self._contexts:
                    del self._contexts[session_id]
                    deleted_contexts = 1

                self._logger.info(
                    "Session deleted",
                    extra={
                        "session_id": session_id,
                        "deleted_sessions": deleted_sessions,
                        "deleted_contexts": deleted_contexts,
                    },
                )

        except Exception as e:
            self._logger.error(
                "Error deleting session",
                extra={"session_id": session_id, "error": str(e)},
            )
            raise StorageError(f"Failed to delete session {session_id}", e)

    async def list_sessions(self, limit: int = 100) -> list[str]:
        """List active session identifiers.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session identifiers

        Raises:
            StorageError: If sessions cannot be listed
        """
        try:
            async with self._lock:
                # Clean up expired sessions first
                await self._evict_old_sessions()

                # Return session IDs (most recent first due to LRU ordering)
                session_ids = list(self._sessions.keys())[-limit:]
                session_ids.reverse()  # Most recent first

                self._logger.debug(
                    "Sessions listed",
                    extra={
                        "total_sessions": len(self._sessions),
                        "returned_sessions": len(session_ids),
                        "limit": limit,
                    },
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
            async with self._lock:
                return await self._evict_old_sessions()

        except Exception as e:
            self._logger.error(
                "Error cleaning up expired sessions", extra={"error": str(e)}
            )
            raise StorageError("Failed to cleanup expired sessions", e)

    async def _evict_old_sessions(self) -> int:
        """Evict sessions based on TTL and max count.

        Returns:
            Number of sessions evicted
        """
        now = datetime.now()
        evicted_count = 0

        # Remove expired sessions
        expired_sessions = [
            sid
            for sid, session in self._sessions.items()
            if now - session.last_active_at > self.ttl
        ]

        for sid in expired_sessions:
            del self._sessions[sid]
            if sid in self._contexts:
                del self._contexts[sid]
            evicted_count += 1

        # LRU eviction if over max
        while len(self._sessions) > self.max_sessions:
            sid, _ = self._sessions.popitem(last=False)  # Remove oldest
            if sid in self._contexts:
                del self._contexts[sid]
            evicted_count += 1

        if evicted_count > 0:
            self._logger.info(
                "Sessions evicted",
                extra={
                    "evicted_count": evicted_count,
                    "remaining_sessions": len(self._sessions),
                    "remaining_contexts": len(self._contexts),
                },
            )

        return evicted_count

    async def get_stats(self) -> dict[str, Any]:
        """Get storage statistics.

        Returns:
            Dictionary containing storage statistics
        """
        async with self._lock:
            return {
                "storage_type": "MemoryStorage",
                "total_sessions": len(self._sessions),
                "total_contexts": len(self._contexts),
                "max_sessions": self.max_sessions,
                "ttl_minutes": self.ttl.total_seconds() / 60,
                "memory_usage_estimate": {
                    "sessions": len(self._sessions),
                    "contexts": len(self._contexts),
                    "total_objects": len(self._sessions) + len(self._contexts),
                },
            }

    async def health_check(self) -> dict[str, Any]:
        """Perform health check for storage.

        Returns:
            Health check results
        """
        try:
            stats = await self.get_stats()
            return {
                "status": "healthy",
                "storage_type": "MemoryStorage",
                "stats": stats,
                "lock_available": not self._lock.locked(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "storage_type": "MemoryStorage",
                "error": str(e),
            }
