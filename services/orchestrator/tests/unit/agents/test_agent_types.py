"""Unit tests for agent types."""

from datetime import datetime

import pytest

from services.orchestrator.agents.types import (
    AgentResponse,
    ConversationContext,
    ExternalAction,
)


class TestExternalAction:
    """Test ExternalAction class."""

    def test_external_action_creation(self):
        """Test creating an external action."""
        action = ExternalAction(
            action_type="send_message",
            parameters={"message": "Hello", "channel": "general"},
        )

        assert action.action_type == "send_message"
        assert action.parameters == {"message": "Hello", "channel": "general"}
        assert action.metadata == {}

    def test_external_action_with_metadata(self):
        """Test creating an external action with metadata."""
        action = ExternalAction(
            action_type="api_call",
            parameters={"url": "https://api.example.com"},
            metadata={"priority": "high", "timeout": 30},
        )

        assert action.action_type == "api_call"
        assert action.parameters == {"url": "https://api.example.com"}
        assert action.metadata == {"priority": "high", "timeout": 30}

    def test_external_action_validation(self):
        """Test external action validation."""
        with pytest.raises(ValueError, match="action_type cannot be empty"):
            ExternalAction(action_type="", parameters={})

        with pytest.raises(ValueError, match="parameters must be a dictionary"):
            ExternalAction(action_type="test", parameters="not_a_dict")  # type: ignore


class TestAgentResponse:
    """Test AgentResponse class."""

    def test_agent_response_text_only(self):
        """Test creating an agent response with text only."""
        response = AgentResponse(response_text="Hello world")

        assert response.response_text == "Hello world"
        assert response.response_audio is None
        assert response.actions == []
        assert response.metadata == {}

    def test_agent_response_with_actions(self):
        """Test creating an agent response with actions."""
        action = ExternalAction(
            action_type="send_message", parameters={"message": "Hello"}
        )
        response = AgentResponse(response_text="Hello world", actions=[action])

        assert response.response_text == "Hello world"
        assert len(response.actions) == 1
        assert response.actions[0].action_type == "send_message"

    def test_agent_response_with_metadata(self):
        """Test creating an agent response with metadata."""
        response = AgentResponse(
            response_text="Hello world", metadata={"confidence": 0.95, "model": "gpt-4"}
        )

        assert response.response_text == "Hello world"
        assert response.metadata == {"confidence": 0.95, "model": "gpt-4"}

    def test_agent_response_validation(self):
        """Test agent response validation."""
        with pytest.raises(ValueError, match="response_text must be a string"):
            AgentResponse(response_text=123)  # type: ignore

        with pytest.raises(
            ValueError, match="all actions must be ExternalAction instances"
        ):
            AgentResponse(actions=["not_an_action"])  # type: ignore


class TestConversationContext:
    """Test ConversationContext class."""

    def test_conversation_context_creation(self):
        """Test creating a conversation context."""
        now = datetime.now()
        context = ConversationContext(
            session_id="test-session",
            history=[("Hello", "Hi there!")],
            created_at=now,
            last_active_at=now,
        )

        assert context.session_id == "test-session"
        assert context.history == [("Hello", "Hi there!")]
        assert context.created_at == now
        assert context.last_active_at == now
        assert context.metadata is None

    def test_conversation_context_with_metadata(self):
        """Test creating a conversation context with metadata."""
        now = datetime.now()
        context = ConversationContext(
            session_id="test-session",
            history=[],
            created_at=now,
            last_active_at=now,
            metadata={"user_id": "123", "language": "en"},
        )

        assert context.metadata == {"user_id": "123", "language": "en"}

    def test_conversation_context_validation(self):
        """Test conversation context validation."""
        now = datetime.now()

        with pytest.raises(ValueError, match="session_id cannot be empty"):
            ConversationContext(
                session_id="", history=[], created_at=now, last_active_at=now
            )

        with pytest.raises(ValueError, match="history must be a list"):
            ConversationContext(
                session_id="test",
                history="not_a_list",  # type: ignore
                created_at=now,
                last_active_at=now,
            )

    def test_add_turn(self):
        """Test adding a conversation turn."""
        now = datetime.now()
        context = ConversationContext(
            session_id="test-session", history=[], created_at=now, last_active_at=now
        )

        context.add_turn("Hello", "Hi there!")

        assert len(context.history) == 1
        assert context.history[0] == ("Hello", "Hi there!")
        assert context.last_active_at > now

    def test_get_recent_history(self):
        """Test getting recent history."""
        now = datetime.now()
        context = ConversationContext(
            session_id="test-session",
            history=[
                ("Hello", "Hi!"),
                ("How are you?", "I'm good!"),
                ("What's the weather?", "It's sunny!"),
            ],
            created_at=now,
            last_active_at=now,
        )

        recent = context.get_recent_history(max_turns=2)
        assert len(recent) == 2
        assert recent[0] == ("How are you?", "I'm good!")
        assert recent[1] == ("What's the weather?", "It's sunny!")

    def test_get_conversation_summary(self):
        """Test getting conversation summary."""
        now = datetime.now()
        context = ConversationContext(
            session_id="test-session",
            history=[("Hello", "Hi!"), ("How are you?", "I'm good!")],
            created_at=now,
            last_active_at=now,
        )

        summary = context.get_conversation_summary()
        assert "2 turns" in summary
        assert "test-session" not in summary  # Should not include session ID
