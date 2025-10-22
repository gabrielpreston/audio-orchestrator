"""
Unit tests for context types.

Tests the Session and ConversationContext data structures and their methods.
"""

from datetime import datetime

from services.orchestrator.context.types import ConversationContext, Session


class TestSession:
    """Test Session data structure."""

    def test_session_creation(self):
        """Test basic session creation."""
        now = datetime.now()
        session = Session(
            id="test-session-123",
            created_at=now,
            last_active_at=now,
            metadata={"user_id": "user-456", "channel": "general"},
        )

        assert session.id == "test-session-123"
        assert session.created_at == now
        assert session.last_active_at == now
        assert session.metadata == {"user_id": "user-456", "channel": "general"}

    def test_session_with_empty_metadata(self):
        """Test session creation with empty metadata."""
        now = datetime.now()
        session = Session(
            id="test-session-456", created_at=now, last_active_at=now, metadata={}
        )

        assert session.id == "test-session-456"
        assert session.metadata == {}


class TestConversationContext:
    """Test ConversationContext data structure."""

    def test_context_creation(self):
        """Test basic context creation."""
        now = datetime.now()
        context = ConversationContext(
            session_id="test-session-123",
            history=[],
            created_at=now,
            last_active_at=now,
            metadata={"agent_type": "echo"},
        )

        assert context.session_id == "test-session-123"
        assert context.history == []
        assert context.created_at == now
        assert context.last_active_at == now
        assert context.metadata == {"agent_type": "echo"}

    def test_context_without_metadata(self):
        """Test context creation without metadata."""
        now = datetime.now()
        context = ConversationContext(
            session_id="test-session-456",
            history=[],
            created_at=now,
            last_active_at=now,
        )

        assert context.session_id == "test-session-456"
        assert context.metadata is None

    def test_add_interaction(self):
        """Test adding user-agent interactions."""
        now = datetime.now()
        context = ConversationContext(
            session_id="test-session-123",
            history=[],
            created_at=now,
            last_active_at=now,
        )

        # Add first interaction
        context.add_interaction("Hello", "Hi there!")
        assert len(context.history) == 1
        assert context.history[0] == ("Hello", "Hi there!")

        # Add second interaction
        context.add_interaction("How are you?", "I'm doing well, thank you!")
        assert len(context.history) == 2
        assert context.history[1] == ("How are you?", "I'm doing well, thank you!")

    def test_get_recent_history(self):
        """Test getting recent conversation history."""
        now = datetime.now()
        context = ConversationContext(
            session_id="test-session-123",
            history=[],
            created_at=now,
            last_active_at=now,
        )

        # Add multiple interactions
        for i in range(15):
            context.add_interaction(f"User message {i}", f"Agent response {i}")

        # Test getting recent history with default limit
        recent = context.get_recent_history()
        assert len(recent) == 10
        assert recent[0] == ("User message 5", "Agent response 5")
        assert recent[-1] == ("User message 14", "Agent response 14")

        # Test getting recent history with custom limit
        recent = context.get_recent_history(max_turns=5)
        assert len(recent) == 5
        assert recent[0] == ("User message 10", "Agent response 10")
        assert recent[-1] == ("User message 14", "Agent response 14")

    def test_get_conversation_length(self):
        """Test getting conversation length."""
        now = datetime.now()
        context = ConversationContext(
            session_id="test-session-123",
            history=[],
            created_at=now,
            last_active_at=now,
        )

        # Empty conversation
        assert context.get_conversation_length() == 0

        # Add some interactions
        context.add_interaction("Hello", "Hi!")
        assert context.get_conversation_length() == 1

        context.add_interaction("How are you?", "Good!")
        assert context.get_conversation_length() == 2

    def test_is_empty(self):
        """Test checking if conversation is empty."""
        now = datetime.now()
        context = ConversationContext(
            session_id="test-session-123",
            history=[],
            created_at=now,
            last_active_at=now,
        )

        # Empty conversation
        assert context.is_empty() is True

        # Add interaction
        context.add_interaction("Hello", "Hi!")
        assert context.is_empty() is False

    def test_add_interaction_updates_last_active(self):
        """Test that adding interactions updates last_active_at."""
        now = datetime.now()
        context = ConversationContext(
            session_id="test-session-123",
            history=[],
            created_at=now,
            last_active_at=now,
        )

        # Wait a small amount of time
        import time

        time.sleep(0.001)

        # Add interaction
        context.add_interaction("Hello", "Hi!")

        # last_active_at should be updated
        assert context.last_active_at > now

    def test_get_recent_history_with_empty_conversation(self):
        """Test getting recent history from empty conversation."""
        now = datetime.now()
        context = ConversationContext(
            session_id="test-session-123",
            history=[],
            created_at=now,
            last_active_at=now,
        )

        recent = context.get_recent_history()
        assert recent == []

    def test_get_recent_history_with_fewer_than_limit(self):
        """Test getting recent history when conversation has fewer turns than limit."""
        now = datetime.now()
        context = ConversationContext(
            session_id="test-session-123",
            history=[],
            created_at=now,
            last_active_at=now,
        )

        # Add only 3 interactions
        for i in range(3):
            context.add_interaction(f"User {i}", f"Agent {i}")

        # Request 10 recent interactions
        recent = context.get_recent_history(max_turns=10)
        assert len(recent) == 3
        assert recent[0] == ("User 0", "Agent 0")
        assert recent[-1] == ("User 2", "Agent 2")
