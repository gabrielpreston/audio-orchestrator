"""Tests for the SummarizationAgent."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock, patch

import httpx
import pytest

from services.orchestrator.agents.summarization_agent import SummarizationAgent
from services.orchestrator.agents.types import AgentResponse, ConversationContext


class TestSummarizationAgent:
    """Test cases for SummarizationAgent."""

    @pytest.fixture
    def agent(self) -> SummarizationAgent:
        """Create a SummarizationAgent instance for testing."""
        return SummarizationAgent(llm_service_url="http://test-llm:8000")

    @pytest.fixture
    def context_with_history(self) -> ConversationContext:
        """Create a conversation context with history."""
        return ConversationContext(
            session_id="test-session",
            history=[
                ("Hello", "Hi there! How can I help you?"),
                (
                    "What's the weather like?",
                    "I don't have access to weather data, but I can help with other things.",
                ),
                (
                    "Can you summarize our conversation?",
                    "I'd be happy to summarize our conversation.",
                ),
            ],
            created_at=datetime.now(),
            last_active_at=datetime.now(),
        )

    @pytest.fixture
    def context_empty(self) -> ConversationContext:
        """Create an empty conversation context."""
        return ConversationContext(
            session_id="test-session",
            history=[],
            created_at=datetime.now(),
            last_active_at=datetime.now(),
        )

    def test_agent_name(self, agent: SummarizationAgent) -> None:
        """Test that agent has correct name."""
        assert agent.name == "summarization"

    def test_agent_initialization(self) -> None:
        """Test agent initialization with LLM URL."""
        llm_url = "http://test-llm:8000"
        agent = SummarizationAgent(llm_service_url=llm_url)

        assert agent.llm_url == llm_url
        assert agent.name == "summarization"

    def test_agent_initialization_strips_trailing_slash(self) -> None:
        """Test that LLM URL trailing slash is stripped."""
        agent = SummarizationAgent(llm_service_url="http://test-llm:8000/")
        assert agent.llm_url == "http://test-llm:8000"

    @pytest.mark.asyncio
    async def test_handle_empty_history(
        self, agent: SummarizationAgent, context_empty: ConversationContext
    ) -> None:
        """Test handling request with no conversation history."""
        response = await agent.handle(context_empty, "summarize our conversation")

        assert isinstance(response, AgentResponse)
        assert response.response_text is not None
        assert "no conversation history" in response.response_text.lower()
        assert response.metadata["agent_name"] == "summarization"
        assert response.metadata["history_length"] == 0
        assert response.metadata["summary_type"] == "no_history"

    @pytest.mark.asyncio
    async def test_handle_with_history_success(
        self, agent: SummarizationAgent, context_with_history: ConversationContext
    ) -> None:
        """Test successful summarization with conversation history."""
        mock_summary = "This conversation covered greetings, weather inquiries, and summarization requests."

        with patch.object(
            agent, "_generate_summary", return_value=mock_summary
        ) as mock_generate:
            response = await agent.handle(
                context_with_history, "summarize our conversation"
            )

            assert isinstance(response, AgentResponse)
            assert response.response_text == mock_summary
            assert response.metadata["agent_name"] == "summarization"
            assert response.metadata["history_length"] == 3
            assert response.metadata["summary_type"] == "conversation_summary"

            # Verify _generate_summary was called with correct arguments
            mock_generate.assert_called_once()
            call_args = mock_generate.call_args[0]
            assert "Turn 1:" in call_args[0]  # history_text
            assert "summarize our conversation" in call_args[1]  # user_request

    @pytest.mark.asyncio
    async def test_handle_llm_service_error(
        self, agent: SummarizationAgent, context_with_history: ConversationContext
    ) -> None:
        """Test handling when LLM service fails."""
        with patch.object(
            agent, "_generate_summary", side_effect=Exception("LLM service unavailable")
        ):
            response = await agent.handle(
                context_with_history, "summarize our conversation"
            )

            assert isinstance(response, AgentResponse)
            assert response.response_text is not None
            assert "trouble generating a summary" in response.response_text
            assert response.metadata["summary_type"] == "fallback"
            assert "error" in response.metadata

    @pytest.mark.asyncio
    async def test_can_handle_summarization_keywords(
        self, agent: SummarizationAgent, context_with_history: ConversationContext
    ) -> None:
        """Test that agent can handle summarization keywords."""
        test_cases = [
            "summarize our conversation",
            "give me a summary",
            "what did we talk about",
            "recap our discussion",
            "overview of our chat",
            "sum up the conversation",
            "key points from our talk",
        ]

        for transcript in test_cases:
            result = await agent.can_handle(context_with_history, transcript)
            assert result, f"Should handle: {transcript}"

    @pytest.mark.asyncio
    async def test_can_handle_short_requests(
        self, agent: SummarizationAgent, context_with_history: ConversationContext
    ) -> None:
        """Test that agent can handle short summarization requests."""
        test_cases = [
            "what did we",
            "tell me about",
            "show me what",
            "give me a summary",
        ]

        for transcript in test_cases:
            result = await agent.can_handle(context_with_history, transcript)
            assert result, f"Should handle short request: {transcript}"

    @pytest.mark.asyncio
    async def test_can_handle_non_summarization(
        self, agent: SummarizationAgent, context_with_history: ConversationContext
    ) -> None:
        """Test that agent rejects non-summarization requests."""
        test_cases = [
            "hello there",
            "what's the weather like",
            "play some music",
            "tell me a joke",
            "how are you doing",
        ]

        for transcript in test_cases:
            result = await agent.can_handle(context_with_history, transcript)
            assert not result, f"Should not handle: {transcript}"

    def test_build_conversation_history(
        self, agent: SummarizationAgent, context_with_history: ConversationContext
    ) -> None:
        """Test building conversation history for LLM."""
        history_text = agent._build_conversation_history(context_with_history)

        assert "Turn 1:" in history_text
        assert "User: Hello" in history_text
        assert "Assistant: Hi there! How can I help you?" in history_text
        assert "Turn 2:" in history_text
        assert "User: What's the weather like?" in history_text

    def test_build_conversation_history_empty(
        self, agent: SummarizationAgent, context_empty: ConversationContext
    ) -> None:
        """Test building conversation history for empty context."""
        history_text = agent._build_conversation_history(context_empty)

        assert history_text == "No conversation history available."

    @pytest.mark.asyncio
    async def test_generate_summary_success(self, agent: SummarizationAgent) -> None:
        """Test successful summary generation."""
        history_text = "Turn 1:\nUser: Hello\nAssistant: Hi there!\n"
        user_request = "summarize our conversation"
        expected_summary = "This conversation started with a greeting."

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": expected_summary}}]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )
            summary = await agent._generate_summary(history_text, user_request)

            assert summary == expected_summary

    @pytest.mark.asyncio
    async def test_generate_summary_http_error(self, agent: SummarizationAgent) -> None:
        """Test summary generation with HTTP error."""
        history_text = "Turn 1:\nUser: Hello\nAssistant: Hi there!\n"
        user_request = "summarize our conversation"

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )
            with pytest.raises(Exception, match="LLM service error: 500"):
                await agent._generate_summary(history_text, user_request)

    @pytest.mark.asyncio
    async def test_generate_summary_invalid_response(
        self, agent: SummarizationAgent
    ) -> None:
        """Test summary generation with invalid response format."""
        history_text = "Turn 1:\nUser: Hello\nAssistant: Hi there!\n"
        user_request = "summarize our conversation"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid": "response"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )
            with pytest.raises(Exception, match="Invalid response from LLM service"):
                await agent._generate_summary(history_text, user_request)

    def test_build_summarization_prompt(self, agent: SummarizationAgent) -> None:
        """Test building summarization prompt."""
        history_text = "Turn 1:\nUser: Hello\nAssistant: Hi there!\n"
        user_request = "summarize our conversation"

        prompt = agent._build_summarization_prompt(history_text, user_request)

        assert "Please provide a clear and concise summary" in prompt
        assert f"User's request: {user_request}" in prompt
        assert f"Conversation history:\n{history_text}" in prompt
        assert "Please provide a summary that:" in prompt
        assert "Summary:" in prompt

    @pytest.mark.asyncio
    async def test_get_capabilities(self, agent: SummarizationAgent) -> None:
        """Test getting agent capabilities."""
        capabilities = await agent.get_capabilities()

        assert isinstance(capabilities, list)
        assert "Summarize conversation history" in capabilities
        assert "Provide conversation overviews" in capabilities
        assert "Generate contextual summaries" in capabilities
        assert "Handle summarization requests" in capabilities

    @pytest.mark.asyncio
    async def test_health_check_llm_healthy(self, agent: SummarizationAgent) -> None:
        """Test health check when LLM service is healthy."""
        mock_response = Mock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            health = await agent.health_check()

            assert health["agent_name"] == "summarization"
            assert health["status"] == "healthy"
            assert health["llm_service_url"] == "http://test-llm:8000"
            assert health["llm_service_healthy"] is True
            assert health["llm_error"] is None

    @pytest.mark.asyncio
    async def test_health_check_llm_unhealthy(self, agent: SummarizationAgent) -> None:
        """Test health check when LLM service is unhealthy."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                httpx.ConnectError("Connection failed")
            )

            health = await agent.health_check()

            assert health["agent_name"] == "summarization"
            assert health["status"] == "healthy"  # Agent itself is healthy
            assert health["llm_service_url"] == "http://test-llm:8000"
            assert health["llm_service_healthy"] is False
            assert "Connection failed" in health["llm_error"]

    @pytest.mark.asyncio
    async def test_handle_with_different_user_requests(
        self, agent: SummarizationAgent, context_with_history: ConversationContext
    ) -> None:
        """Test handling different types of summarization requests."""
        test_cases = [
            "summarize our conversation",
            "give me a recap",
            "what did we discuss",
            "overview please",
        ]

        with patch.object(agent, "_generate_summary", return_value="Test summary"):
            for request in test_cases:
                response = await agent.handle(context_with_history, request)

                assert isinstance(response, AgentResponse)
                assert response.response_text == "Test summary"
                assert response.metadata["agent_name"] == "summarization"

    @pytest.mark.asyncio
    async def test_handle_logging(
        self, agent: SummarizationAgent, context_with_history: ConversationContext
    ) -> None:
        """Test that agent logs appropriately during handling."""
        with (
            patch.object(agent, "_generate_summary", return_value="Test summary"),
            patch.object(agent._logger, "info") as mock_logger,
        ):
            await agent.handle(context_with_history, "summarize our conversation")

            # Check that appropriate logging occurred
            mock_logger.assert_called()
            call_args = mock_logger.call_args
            assert "Processing summarization request" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_error_logging(
        self, agent: SummarizationAgent, context_with_history: ConversationContext
    ) -> None:
        """Test that agent logs errors appropriately."""
        with (
            patch.object(
                agent, "_generate_summary", side_effect=Exception("Test error")
            ),
            patch.object(agent._logger, "error") as mock_logger,
        ):
            await agent.handle(context_with_history, "summarize our conversation")

            # Check that error was logged
            mock_logger.assert_called()
            call_args = mock_logger.call_args
            assert "Failed to generate summary" in call_args[0][0]
