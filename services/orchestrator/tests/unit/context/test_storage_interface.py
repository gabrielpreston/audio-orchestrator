"""
Unit tests for storage interface.

Tests the StorageInterface abstract class and StorageError exception.
"""

from datetime import datetime

import pytest

from services.orchestrator.context.storage_interface import (
    StorageError,
    StorageInterface,
)
from services.orchestrator.context.types import ConversationContext, Session


class MockStorage(StorageInterface):
    """Mock storage implementation for testing."""

    def __init__(self):
        self.sessions: dict[str, Session] = {}
        self.contexts: dict[str, ConversationContext] = {}
        self.execution_logs: list[dict] = []
        self.should_raise_error = False
        self.error_message = "Mock storage error"

    async def get_session(self, session_id: str) -> Session:
        """Mock get_session implementation."""
        if self.should_raise_error:
            raise StorageError(self.error_message)

        if session_id not in self.sessions:
            now = datetime.now()
            self.sessions[session_id] = Session(
                id=session_id, created_at=now, last_active_at=now, metadata={}
            )
        return self.sessions[session_id]

    async def save_context(self, session_id: str, context: ConversationContext) -> None:
        """Mock save_context implementation."""
        if self.should_raise_error:
            raise StorageError(self.error_message)
        self.contexts[session_id] = context

    async def get_context(self, session_id: str) -> ConversationContext | None:
        """Mock get_context implementation."""
        if self.should_raise_error:
            raise StorageError(self.error_message)
        return self.contexts.get(session_id)

    async def log_agent_execution(
        self,
        session_id: str,
        agent_name: str,
        transcript: str,
        response_text: str,
        latency_ms: int,
    ) -> None:
        """Mock log_agent_execution implementation."""
        if self.should_raise_error:
            raise StorageError(self.error_message)
        self.execution_logs.append(
            {
                "session_id": session_id,
                "agent_name": agent_name,
                "transcript": transcript,
                "response_text": response_text,
                "latency_ms": latency_ms,
            }
        )

    async def delete_session(self, session_id: str) -> None:
        """Mock delete_session implementation."""
        if self.should_raise_error:
            raise StorageError(self.error_message)
        self.sessions.pop(session_id, None)
        self.contexts.pop(session_id, None)

    async def list_sessions(self, limit: int = 100) -> list[str]:
        """Mock list_sessions implementation."""
        if self.should_raise_error:
            raise StorageError(self.error_message)
        return list(self.sessions.keys())[:limit]

    async def cleanup_expired_sessions(self) -> int:
        """Mock cleanup_expired_sessions implementation."""
        if self.should_raise_error:
            raise StorageError(self.error_message)
        return 0


class TestStorageInterface:
    """Test StorageInterface abstract class."""

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage instance."""
        return MockStorage()

    @pytest.mark.asyncio
    async def test_get_session_creates_new_session(self, mock_storage):
        """Test that get_session creates a new session if it doesn't exist."""
        session_id = "test-session-123"

        session = await mock_storage.get_session(session_id)

        assert session.id == session_id
        assert session_id in mock_storage.sessions

    @pytest.mark.asyncio
    async def test_get_session_returns_existing_session(self, mock_storage):
        """Test that get_session returns existing session."""
        session_id = "test-session-123"
        now = datetime.now()

        # Create session manually
        mock_storage.sessions[session_id] = Session(
            id=session_id, created_at=now, last_active_at=now, metadata={"test": "data"}
        )

        session = await mock_storage.get_session(session_id)

        assert session.id == session_id
        assert session.metadata == {"test": "data"}

    @pytest.mark.asyncio
    async def test_save_context(self, mock_storage):
        """Test saving conversation context."""
        session_id = "test-session-123"
        now = datetime.now()

        context = ConversationContext(
            session_id=session_id,
            history=[("Hello", "Hi there!")],
            created_at=now,
            last_active_at=now,
        )

        await mock_storage.save_context(session_id, context)

        assert session_id in mock_storage.contexts
        assert mock_storage.contexts[session_id] == context

    @pytest.mark.asyncio
    async def test_get_context_returns_saved_context(self, mock_storage):
        """Test retrieving saved conversation context."""
        session_id = "test-session-123"
        now = datetime.now()

        context = ConversationContext(
            session_id=session_id,
            history=[("Hello", "Hi there!")],
            created_at=now,
            last_active_at=now,
        )

        # Save context
        await mock_storage.save_context(session_id, context)

        # Retrieve context
        retrieved_context = await mock_storage.get_context(session_id)

        assert retrieved_context is not None
        assert retrieved_context.session_id == session_id
        assert retrieved_context.history == [("Hello", "Hi there!")]

    @pytest.mark.asyncio
    async def test_get_context_returns_none_for_missing_session(self, mock_storage):
        """Test that get_context returns None for non-existent session."""
        session_id = "non-existent-session"

        context = await mock_storage.get_context(session_id)

        assert context is None

    @pytest.mark.asyncio
    async def test_log_agent_execution(self, mock_storage):
        """Test logging agent execution."""
        session_id = "test-session-123"
        agent_name = "echo"
        transcript = "Hello world"
        response_text = "Hello world"
        latency_ms = 150

        await mock_storage.log_agent_execution(
            session_id, agent_name, transcript, response_text, latency_ms
        )

        assert len(mock_storage.execution_logs) == 1
        log_entry = mock_storage.execution_logs[0]
        assert log_entry["session_id"] == session_id
        assert log_entry["agent_name"] == agent_name
        assert log_entry["transcript"] == transcript
        assert log_entry["response_text"] == response_text
        assert log_entry["latency_ms"] == latency_ms

    @pytest.mark.asyncio
    async def test_delete_session(self, mock_storage):
        """Test deleting a session."""
        session_id = "test-session-123"
        now = datetime.now()

        # Create session and context
        mock_storage.sessions[session_id] = Session(
            id=session_id, created_at=now, last_active_at=now, metadata={}
        )
        mock_storage.contexts[session_id] = ConversationContext(
            session_id=session_id, history=[], created_at=now, last_active_at=now
        )

        # Delete session
        await mock_storage.delete_session(session_id)

        assert session_id not in mock_storage.sessions
        assert session_id not in mock_storage.contexts

    @pytest.mark.asyncio
    async def test_list_sessions(self, mock_storage):
        """Test listing sessions."""
        # Create multiple sessions
        for i in range(5):
            session_id = f"test-session-{i}"
            now = datetime.now()
            mock_storage.sessions[session_id] = Session(
                id=session_id, created_at=now, last_active_at=now, metadata={}
            )

        sessions = await mock_storage.list_sessions()

        assert len(sessions) == 5
        assert "test-session-0" in sessions
        assert "test-session-4" in sessions

    @pytest.mark.asyncio
    async def test_list_sessions_with_limit(self, mock_storage):
        """Test listing sessions with limit."""
        # Create multiple sessions
        for i in range(10):
            session_id = f"test-session-{i}"
            now = datetime.now()
            mock_storage.sessions[session_id] = Session(
                id=session_id, created_at=now, last_active_at=now, metadata={}
            )

        sessions = await mock_storage.list_sessions(limit=3)

        assert len(sessions) == 3

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, mock_storage):
        """Test cleaning up expired sessions."""
        cleaned_count = await mock_storage.cleanup_expired_sessions()

        assert cleaned_count == 0  # Mock implementation returns 0


class TestStorageError:
    """Test StorageError exception."""

    def test_storage_error_creation(self):
        """Test creating StorageError with message only."""
        error = StorageError("Test error message")

        assert str(error) == "Test error message"
        assert error.original_error is None

    def test_storage_error_with_original_error(self):
        """Test creating StorageError with original exception."""
        original = ValueError("Original error")
        error = StorageError("Test error message", original)

        assert str(error) == "Test error message"
        assert error.original_error is original

    def test_storage_error_inheritance(self):
        """Test that StorageError inherits from Exception."""
        error = StorageError("Test error")

        assert isinstance(error, Exception)

    @pytest.mark.asyncio
    async def test_storage_error_propagation(self):
        """Test that StorageError is properly raised by storage implementations."""
        mock_storage = MockStorage()
        mock_storage.should_raise_error = True
        mock_storage.error_message = "Test storage error"

        with pytest.raises(StorageError) as exc_info:
            await mock_storage.get_session("test-session")

        assert str(exc_info.value) == "Test storage error"
        assert exc_info.value.original_error is None
