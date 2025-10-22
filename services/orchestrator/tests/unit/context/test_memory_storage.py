"""Tests for MemoryStorage implementation."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from services.orchestrator.context.memory_storage import MemoryStorage
from services.orchestrator.context.storage_interface import StorageError
from services.orchestrator.context.types import ConversationContext, Session


class TestMemoryStorage:
    """Test cases for MemoryStorage."""

    @pytest.fixture
    def storage(self):
        """Create MemoryStorage instance for testing."""
        return MemoryStorage(max_sessions=5, ttl_minutes=1)

    @pytest.fixture
    def sample_session(self):
        """Create sample session for testing."""
        return Session(
            id="test-session-123",
            created_at=datetime.now(),
            last_active_at=datetime.now(),
            metadata={"test": "data"},
        )

    @pytest.fixture
    def sample_context(self):
        """Create sample context for testing."""
        return ConversationContext(
            session_id="test-session-123",
            history=[("Hello", "Hi there!")],
            created_at=datetime.now(),
            last_active_at=datetime.now(),
            metadata={"test": "context"},
        )

    @pytest.mark.asyncio
    async def test_get_session_creates_new(self, storage):
        """Test that get_session creates new session if none exists."""
        session_id = "new-session-456"

        session = await storage.get_session(session_id)

        assert session.id == session_id
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_active_at, datetime)
        assert session.metadata == {}

    @pytest.mark.asyncio
    async def test_get_session_returns_existing(self, storage, sample_session):
        """Test that get_session returns existing session."""
        session_id = sample_session.id

        # Manually add session to storage
        storage._sessions[session_id] = sample_session

        session = await storage.get_session(session_id)

        assert session.id == session_id
        assert session.created_at == sample_session.created_at

    @pytest.mark.asyncio
    async def test_save_context(self, storage, sample_context):
        """Test saving conversation context."""
        session_id = sample_context.session_id

        await storage.save_context(session_id, sample_context)

        # Verify context was saved
        retrieved_context = await storage.get_context(session_id)
        assert retrieved_context is not None
        assert retrieved_context.session_id == session_id
        assert len(retrieved_context.history) == 1

    @pytest.mark.asyncio
    async def test_get_context_returns_none_if_not_found(self, storage):
        """Test that get_context returns None for non-existent session."""
        session_id = "non-existent-session"

        context = await storage.get_context(session_id)

        assert context is None

    @pytest.mark.asyncio
    async def test_log_agent_execution(self, storage):
        """Test logging agent execution."""
        session_id = "test-session"
        agent_name = "test-agent"
        transcript = "Hello world"
        response_text = "Hi there!"
        latency_ms = 150

        # Should not raise exception
        await storage.log_agent_execution(
            session_id, agent_name, transcript, response_text, latency_ms
        )

    @pytest.mark.asyncio
    async def test_delete_session(self, storage, sample_session, sample_context):
        """Test deleting session and context."""
        session_id = sample_session.id

        # Add session and context
        storage._sessions[session_id] = sample_session
        storage._contexts[session_id] = sample_context

        await storage.delete_session(session_id)

        # Verify deletion
        assert session_id not in storage._sessions
        assert session_id not in storage._contexts

    @pytest.mark.asyncio
    async def test_list_sessions(self, storage):
        """Test listing sessions."""
        # Add some test sessions
        for i in range(3):
            session_id = f"test-session-{i}"
            await storage.get_session(session_id)

        sessions = await storage.list_sessions(limit=10)

        assert len(sessions) == 3
        assert all(session_id.startswith("test-session-") for session_id in sessions)

    @pytest.mark.asyncio
    async def test_list_sessions_with_limit(self, storage):
        """Test listing sessions with limit."""
        # Add more sessions than limit
        for i in range(7):
            session_id = f"test-session-{i}"
            await storage.get_session(session_id)

        sessions = await storage.list_sessions(limit=3)

        assert len(sessions) <= 3

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, storage):
        """Test cleanup of expired sessions."""
        # Create old session
        old_session = Session(
            id="old-session",
            created_at=datetime.now() - timedelta(hours=2),
            last_active_at=datetime.now() - timedelta(hours=2),
            metadata={},
        )

        storage._sessions["old-session"] = old_session

        # Cleanup should remove expired session
        cleaned_count = await storage.cleanup_expired_sessions()

        assert cleaned_count >= 1
        assert "old-session" not in storage._sessions

    @pytest.mark.asyncio
    async def test_lru_eviction(self, storage):
        """Test LRU eviction when max sessions exceeded."""
        # Add sessions up to max limit
        for i in range(5):
            session_id = f"session-{i}"
            await storage.get_session(session_id)

        # Add one more session to trigger eviction
        await storage.get_session("session-5")

        # First session should be evicted
        sessions = await storage.list_sessions(limit=10)
        assert "session-0" not in sessions
        assert "session-5" in sessions

    @pytest.mark.asyncio
    async def test_get_stats(self, storage):
        """Test getting storage statistics."""
        # Add some data
        await storage.get_session("test-session")

        stats = await storage.get_stats()

        assert stats["storage_type"] == "MemoryStorage"
        assert stats["total_sessions"] >= 1
        assert stats["max_sessions"] == 5
        assert "memory_usage_estimate" in stats

    @pytest.mark.asyncio
    async def test_health_check(self, storage):
        """Test health check."""
        health = await storage.health_check()

        assert health["status"] == "healthy"
        assert health["storage_type"] == "MemoryStorage"
        assert "stats" in health

    @pytest.mark.asyncio
    async def test_concurrent_access(self, storage):
        """Test concurrent access to storage."""

        async def create_session(session_id):
            return await storage.get_session(session_id)

        # Create multiple sessions concurrently
        tasks = [create_session(f"session-{i}") for i in range(10)]
        sessions = await asyncio.gather(*tasks)

        # All sessions should be created successfully
        assert len(sessions) == 10
        assert all(session.id.startswith("session-") for session in sessions)

    @pytest.mark.asyncio
    async def test_error_handling_get_session(self, storage):
        """Test error handling in get_session."""
        # Mock storage to raise exception
        with pytest.raises(StorageError):
            # This should not happen in normal operation, but test error path
            storage._sessions = None  # This will cause an error
            await storage.get_session("test-session")

    @pytest.mark.asyncio
    async def test_error_handling_save_context(self, storage):
        """Test error handling in save_context."""
        # Mock storage to raise exception
        with pytest.raises(StorageError):
            storage._contexts = None  # This will cause an error
            await storage.save_context("test-session", Mock())

    @pytest.mark.asyncio
    async def test_context_update_updates_session_activity(self, storage):
        """Test that context updates update session activity."""
        session_id = "test-session"

        # Create session
        session = await storage.get_session(session_id)
        original_active_time = session.last_active_at

        # Wait a bit to ensure time difference
        await asyncio.sleep(0.01)

        # Save context (should update session activity)
        context = ConversationContext(
            session_id=session_id,
            history=[],
            created_at=datetime.now(),
            last_active_at=datetime.now(),
        )
        await storage.save_context(session_id, context)

        # Get session again and check activity was updated
        updated_session = await storage.get_session(session_id)
        assert updated_session.last_active_at > original_active_time

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, storage):
        """Test TTL-based expiration."""
        # Create session with very short TTL
        short_ttl_storage = MemoryStorage(max_sessions=100, ttl_minutes=0)  # 0 minutes

        session_id = "ttl-test-session"
        await short_ttl_storage.get_session(session_id)

        # Wait for TTL to expire
        await asyncio.sleep(0.1)

        # Cleanup should remove expired session
        cleaned_count = await short_ttl_storage.cleanup_expired_sessions()
        assert cleaned_count >= 1
