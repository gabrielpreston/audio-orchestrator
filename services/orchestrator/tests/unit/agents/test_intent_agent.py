"""
Unit tests for IntentClassificationAgent.

Tests the intent classification agent's ability to classify user intents
and route to appropriate specialized agents.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.orchestrator.agents.intent_agent import IntentClassificationAgent
from services.orchestrator.agents.types import AgentResponse, ConversationContext
from services.orchestrator.agents.manager import AgentManager
from services.orchestrator.agents.registry import AgentRegistry


class TestIntentClassificationAgent:
    """Test cases for IntentClassificationAgent."""

    @pytest.fixture
    def mock_agent_manager(self):
        """Create a mock agent manager."""
        manager = MagicMock(spec=AgentManager)
        manager.registry = MagicMock(spec=AgentRegistry)
        return manager

    @pytest.fixture
    def mock_echo_agent(self):
        """Create a mock echo agent."""
        agent = MagicMock()
        agent.handle = AsyncMock(
            return_value=AgentResponse(response_text="Echo: hello")
        )
        return agent

    @pytest.fixture
    def mock_summarization_agent(self):
        """Create a mock summarization agent."""
        agent = MagicMock()
        agent.handle = AsyncMock(
            return_value=AgentResponse(response_text="Summary: conversation")
        )
        return agent

    @pytest.fixture
    def intent_agent(self, mock_agent_manager):
        """Create an IntentClassificationAgent instance."""
        return IntentClassificationAgent(
            llm_service_url="http://llm:8000", agent_manager=mock_agent_manager
        )

    @pytest.fixture
    def context(self):
        """Create a test conversation context."""
        from datetime import datetime, timezone

        return ConversationContext(
            session_id="test-session",
            history=[("user", "Hello"), ("agent", "Hi there!")],
            created_at=datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            last_active_at=datetime(2023, 1, 1, 0, 1, 0, tzinfo=timezone.utc),
        )

    def test_name_property(self, intent_agent):
        """Test the agent name property."""
        assert intent_agent.name == "intent_classifier"

    @pytest.mark.asyncio
    async def test_can_handle_always_true(self, intent_agent, context):
        """Test that can_handle always returns True."""
        result = await intent_agent.can_handle(context, "any transcript")
        assert result is True

    @pytest.mark.asyncio
    async def test_handle_successful_classification(
        self, intent_agent, context, mock_echo_agent, mock_agent_manager
    ):
        """Test successful intent classification and routing."""
        # Setup mocks
        mock_agent_manager.registry.get.return_value = mock_echo_agent

        with patch.object(intent_agent, "_classify_intent", return_value="echo"):
            response = await intent_agent.handle(context, "echo this back")

            assert response.response_text == "Echo: hello"
            mock_echo_agent.handle.assert_called_once_with(context, "echo this back")

    @pytest.mark.asyncio
    async def test_handle_summarization_intent(
        self, intent_agent, context, mock_summarization_agent, mock_agent_manager
    ):
        """Test routing to summarization agent."""
        # Setup mocks
        mock_agent_manager.registry.get.return_value = mock_summarization_agent

        with patch.object(intent_agent, "_classify_intent", return_value="summarize"):
            response = await intent_agent.handle(context, "summarize our conversation")

            assert response.response_text == "Summary: conversation"
            mock_summarization_agent.handle.assert_called_once_with(
                context, "summarize our conversation"
            )

    @pytest.mark.asyncio
    async def test_handle_unknown_intent_fallback(
        self, intent_agent, context, mock_echo_agent, mock_agent_manager
    ):
        """Test fallback to echo agent for unknown intent."""
        # Setup mocks
        mock_agent_manager.registry.get.return_value = mock_echo_agent

        with patch.object(intent_agent, "_classify_intent", return_value="unknown"):
            response = await intent_agent.handle(context, "some unknown request")

            assert response.response_text == "Echo: hello"
            # Should fallback to echo agent
            mock_agent_manager.registry.get.assert_called_with("echo")

    @pytest.mark.asyncio
    async def test_handle_classification_error_fallback(
        self, intent_agent, context, mock_echo_agent, mock_agent_manager
    ):
        """Test fallback to echo agent when classification fails."""
        # Setup mocks
        mock_agent_manager.registry.get.return_value = mock_echo_agent

        with patch.object(
            intent_agent,
            "_classify_intent",
            side_effect=Exception("Classification failed"),
        ):
            response = await intent_agent.handle(context, "some request")

            assert response.response_text == "Echo: hello"
            mock_echo_agent.handle.assert_called_once_with(context, "some request")

    @pytest.mark.asyncio
    async def test_classify_intent_success(self, intent_agent):
        """Test successful intent classification via LLM."""
        mock_response = {"choices": [{"message": {"content": "echo"}}]}

        with patch("httpx.AsyncClient") as mock_client:
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response_obj
            )

            intent = await intent_agent._classify_intent("echo this back")

            assert intent == "echo"

    @pytest.mark.asyncio
    async def test_classify_intent_unknown_intent(self, intent_agent):
        """Test classification with unknown intent."""
        mock_response = {"choices": [{"message": {"content": "unknown_intent"}}]}

        with patch("httpx.AsyncClient") as mock_client:
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response_obj
            )

            intent = await intent_agent._classify_intent("some request")

            assert intent == "general"  # Should fallback to general

    @pytest.mark.asyncio
    async def test_classify_intent_http_error(self, intent_agent):
        """Test classification with HTTP error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = (
                Exception("HTTP error")
            )

            intent = await intent_agent._classify_intent("some request")

            assert intent == "general"  # Should fallback to general

    def test_get_agent_for_intent_known_intent(
        self, intent_agent, mock_echo_agent, mock_agent_manager
    ):
        """Test getting agent for known intent."""
        mock_agent_manager.registry.get.return_value = mock_echo_agent

        agent = intent_agent._get_agent_for_intent("echo")

        assert agent == mock_echo_agent
        mock_agent_manager.registry.get.assert_called_with("echo")

    def test_get_agent_for_intent_unknown_intent(
        self, intent_agent, mock_echo_agent, mock_agent_manager
    ):
        """Test getting agent for unknown intent."""
        mock_agent_manager.registry.get.return_value = mock_echo_agent

        agent = intent_agent._get_agent_for_intent("unknown")

        assert agent == mock_echo_agent
        mock_agent_manager.registry.get.assert_called_with(
            "echo"
        )  # Should fallback to echo

    def test_get_agent_for_intent_agent_not_found(
        self, intent_agent, mock_echo_agent, mock_agent_manager
    ):
        """Test getting agent when agent is not found."""
        # First call returns None (agent not found), second call returns echo agent
        mock_agent_manager.registry.get.side_effect = [None, mock_echo_agent]

        agent = intent_agent._get_agent_for_intent("echo")

        assert agent == mock_echo_agent
        # Should try echo first, then fallback to echo again
        assert mock_agent_manager.registry.get.call_count == 2

    @pytest.mark.asyncio
    async def test_health_check_llm_healthy(self, intent_agent):
        """Test health check when LLM service is healthy."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            health = await intent_agent.health_check()

            assert health["agent_name"] == "intent_classifier"
            assert health["llm_service_healthy"] is True
            assert "intent_classes" in health
            assert "available_agents" in health

    @pytest.mark.asyncio
    async def test_health_check_llm_unhealthy(self, intent_agent):
        """Test health check when LLM service is unhealthy."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                Exception("Connection failed")
            )

            health = await intent_agent.health_check()

            assert health["agent_name"] == "intent_classifier"
            assert health["llm_service_healthy"] is False
            assert "intent_classes" in health
            assert "available_agents" in health

    def test_intent_classes_default(self, intent_agent):
        """Test default intent classes configuration."""
        expected_intents = {
            "echo": "echo",
            "summarize": "summarization",
            "general": "echo",  # Fixed: use echo agent for general intent
            "help": "echo",
            "weather": "echo",  # Fixed: use echo agent for weather intent
            "time": "echo",  # Fixed: use echo agent for time intent
        }
        assert intent_agent.intent_classes == expected_intents

    def test_intent_classes_custom(self, mock_agent_manager):
        """Test custom intent classes configuration."""
        custom_intents = {
            "greeting": "echo",
            "question": "conversation",
            "command": "echo",
        }

        agent = IntentClassificationAgent(
            llm_service_url="http://llm:8000",
            agent_manager=mock_agent_manager,
            intent_classes=custom_intents,
        )

        assert agent.intent_classes == custom_intents

    def test_classification_prompt_format(self, intent_agent):
        """Test that classification prompt is properly formatted."""
        transcript = "hello world"
        prompt = intent_agent.classification_prompt.format(
            transcript=transcript,
            intents="echo, summarize, general, help, weather, time",
            intent_list="echo, summarize, general, help, weather, time",
        )

        assert transcript in prompt
        assert "Available intents:" in prompt
        assert "Examples:" in prompt
