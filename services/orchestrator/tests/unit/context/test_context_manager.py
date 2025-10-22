"""Tests for ContextManager implementation."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from services.orchestrator.context.manager import ContextManager
from services.orchestrator.context.memory_storage import MemoryStorage
from services.orchestrator.context.storage_interface import StorageError
from services.orchestrator.context.types import ConversationContext, Session


class TestContextManager:
    """Test cases for ContextManager."""

    @pytest.fixture
    def mock_storage(self):
        """Create mock storage for testing."""
        return AsyncMock(spec=MemoryStorage)

    @pytest.fixture
    def context_manager(self, mock_storage):
        """Create ContextManager with mock storage."""
        return ContextManager(mock_storage)

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
    async def test_get_context_returns_existing(
        self, context_manager, mock_storage, sample_context
    ):
        """Test that get_context returns existing context."""
        mock_storage.get_context.return_value = sample_context

        result = await context_manager.get_context("test-session-123")

        assert result == sample_context
        mock_storage.get_context.assert_called_once_with("test-session-123")

    @pytest.mark.asyncio
    async def test_get_context_creates_new_when_none_exists(
        self, context_manager, mock_storage, sample_session
    ):
        """Test that get_context creates new context when none exists."""
        mock_storage.get_context.return_value = None
        mock_storage.get_session.return_value = sample_session

        result = await context_manager.get_context("test-session-123")

        assert result.session_id == "test-session-123"
        assert result.history == []
        assert result.metadata["created_by"] == "ContextManager"
        mock_storage.get_session.assert_called_once_with("test-session-123")
        mock_storage.save_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_context(self, context_manager, mock_storage, sample_context):
        """Test updating context."""
        await context_manager.update_context(sample_context)

        mock_storage.save_context.assert_called_once_with(
            sample_context.session_id, sample_context
        )
        # Verify last_active_at was updated
        assert sample_context.last_active_at > sample_context.created_at

    @pytest.mark.asyncio
    async def test_save_context(self, context_manager, mock_storage, sample_context):
        """Test explicitly saving context."""
        await context_manager.save_context(sample_context)

        mock_storage.save_context.assert_called_once_with(
            sample_context.session_id, sample_context
        )

    @pytest.mark.asyncio
    async def test_add_interaction(self, context_manager, mock_storage, sample_context):
        """Test adding interaction to conversation."""
        mock_storage.get_context.return_value = sample_context

        result = await context_manager.add_interaction(
            "test-session-123", "Hello", "Hi there!"
        )

        assert len(result.history) == 2  # Original + new interaction
        assert result.history[-1] == ("Hello", "Hi there!")
        mock_storage.get_context.assert_called_once_with("test-session-123")
        mock_storage.save_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session(self, context_manager, mock_storage, sample_session):
        """Test getting session."""
        mock_storage.get_session.return_value = sample_session

        result = await context_manager.get_session("test-session-123")

        assert result == sample_session
        mock_storage.get_session.assert_called_once_with("test-session-123")

    @pytest.mark.asyncio
    async def test_delete_session(self, context_manager, mock_storage):
        """Test deleting session."""
        await context_manager.delete_session("test-session-123")

        mock_storage.delete_session.assert_called_once_with("test-session-123")

    @pytest.mark.asyncio
    async def test_list_sessions(self, context_manager, mock_storage):
        """Test listing sessions."""
        mock_storage.list_sessions.return_value = ["session-1", "session-2"]

        result = await context_manager.list_sessions(limit=10)

        assert result == ["session-1", "session-2"]
        mock_storage.list_sessions.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, context_manager, mock_storage):
        """Test cleaning up expired sessions."""
        mock_storage.cleanup_expired_sessions.return_value = 3

        result = await context_manager.cleanup_expired_sessions()

        assert result == 3
        mock_storage.cleanup_expired_sessions.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_agent_execution(self, context_manager, mock_storage):
        """Test logging agent execution."""
        await context_manager.log_agent_execution(
            "test-session-123", "test-agent", "Hello", "Hi!", 150
        )

        mock_storage.log_agent_execution.assert_called_once_with(
            "test-session-123", "test-agent", "Hello", "Hi!", 150
        )

    @pytest.mark.asyncio
    async def test_get_stats(self, context_manager, mock_storage):
        """Test getting statistics."""
        mock_stats = {"total_sessions": 5, "total_contexts": 3}
        mock_storage.get_stats.return_value = mock_stats

        result = await context_manager.get_stats()

        assert result["manager_type"] == "ContextManager"
        assert result["storage_backend"] == "MemoryStorage"
        assert result["storage_stats"] == mock_stats
        mock_storage.get_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, context_manager, mock_storage):
        """Test health check when storage is healthy."""
        mock_storage.health_check.return_value = {"status": "healthy"}

        result = await context_manager.health_check()

        assert result["status"] == "healthy"
        assert result["manager_type"] == "ContextManager"
        assert "storage_health" in result

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, context_manager, mock_storage):
        """Test health check when storage is unhealthy."""
        mock_storage.health_check.side_effect = Exception("Storage error")

        result = await context_manager.health_check()

        assert result["status"] == "unhealthy"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_error_handling_get_context(self, context_manager, mock_storage):
        """Test error handling in get_context."""
        mock_storage.get_context.side_effect = Exception("Storage error")

        with pytest.raises(StorageError) as exc_info:
            await context_manager.get_context("test-session-123")

        assert "Failed to get context for session test-session-123" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_error_handling_update_context(
        self, context_manager, mock_storage, sample_context
    ):
        """Test error handling in update_context."""
        mock_storage.save_context.side_effect = Exception("Storage error")

        with pytest.raises(StorageError) as exc_info:
            await context_manager.update_context(sample_context)

        assert "Failed to update context for session test-session-123" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_error_handling_add_interaction(self, context_manager, mock_storage):
        """Test error handling in add_interaction."""
        mock_storage.get_context.side_effect = Exception("Storage error")

        with pytest.raises(StorageError) as exc_info:
            await context_manager.add_interaction("test-session-123", "Hello", "Hi!")

        assert "Failed to add interaction for session test-session-123" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_error_handling_get_session(self, context_manager, mock_storage):
        """Test error handling in get_session."""
        mock_storage.get_session.side_effect = Exception("Storage error")

        with pytest.raises(StorageError) as exc_info:
            await context_manager.get_session("test-session-123")

        assert "Failed to get session test-session-123" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_handling_delete_session(self, context_manager, mock_storage):
        """Test error handling in delete_session."""
        mock_storage.delete_session.side_effect = Exception("Storage error")

        with pytest.raises(StorageError) as exc_info:
            await context_manager.delete_session("test-session-123")

        assert "Failed to delete session test-session-123" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_handling_list_sessions(self, context_manager, mock_storage):
        """Test error handling in list_sessions."""
        mock_storage.list_sessions.side_effect = Exception("Storage error")

        with pytest.raises(StorageError) as exc_info:
            await context_manager.list_sessions()

        assert "Failed to list sessions" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_handling_cleanup_expired_sessions(
        self, context_manager, mock_storage
    ):
        """Test error handling in cleanup_expired_sessions."""
        mock_storage.cleanup_expired_sessions.side_effect = Exception("Storage error")

        with pytest.raises(StorageError) as exc_info:
            await context_manager.cleanup_expired_sessions()

        assert "Failed to cleanup expired sessions" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_handling_log_agent_execution(
        self, context_manager, mock_storage
    ):
        """Test error handling in log_agent_execution."""
        mock_storage.log_agent_execution.side_effect = Exception("Storage error")

        with pytest.raises(StorageError) as exc_info:
            await context_manager.log_agent_execution(
                "test-session-123", "test-agent", "Hello", "Hi!", 150
            )

        assert "Failed to log agent execution for session test-session-123" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_error_handling_get_stats(self, context_manager, mock_storage):
        """Test error handling in get_stats."""
        mock_storage.get_stats.side_effect = Exception("Storage error")

        result = await context_manager.get_stats()

        assert result["manager_type"] == "ContextManager"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_context_metadata_includes_creation_info(
        self, context_manager, mock_storage, sample_session
    ):
        """Test that new context includes creation metadata."""
        mock_storage.get_context.return_value = None
        mock_storage.get_session.return_value = sample_session

        result = await context_manager.get_context("test-session-123")

        assert result.metadata["created_by"] == "ContextManager"
        assert result.metadata["storage_backend"] == "MemoryStorage"

    @pytest.mark.asyncio
    async def test_add_interaction_updates_last_active_time(
        self, context_manager, mock_storage, sample_context
    ):
        """Test that add_interaction updates last_active_at."""
        original_time = sample_context.last_active_at
        mock_storage.get_context.return_value = sample_context

        result = await context_manager.add_interaction(
            "test-session-123", "Hello", "Hi there!"
        )

        assert result.last_active_at > original_time
        assert len(result.history) == 2
