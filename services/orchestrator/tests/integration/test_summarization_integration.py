"""Integration tests for SummarizationAgent with LLM service."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest

from services.orchestrator.agents.summarization_agent import SummarizationAgent
from services.orchestrator.agents.types import ConversationContext


class TestSummarizationIntegration:
    """Integration tests for SummarizationAgent with LLM service."""

    @pytest.fixture
    def agent(self) -> SummarizationAgent:
        """Create a SummarizationAgent instance for integration testing."""
        return SummarizationAgent(llm_service_url="http://test-llm:8000")

    @pytest.fixture
    def context_long_conversation(self) -> ConversationContext:
        """Create a conversation context with longer history."""
        return ConversationContext(
            session_id="integration-test-session",
            history=[
                ("Hello", "Hi there! How can I help you today?"),
                (
                    "I'm working on a project",
                    "That sounds interesting! What kind of project is it?",
                ),
                (
                    "It's a software development project",
                    "Great! What technologies are you using?",
                ),
                (
                    "Python and FastAPI",
                    "Excellent choices! Python is great for backend development.",
                ),
                (
                    "I'm having some issues with testing",
                    "Testing can be tricky. What specific problems are you facing?",
                ),
                (
                    "Unit tests are failing",
                    "Let's debug those unit tests. Can you share the error messages?",
                ),
                (
                    "The tests are timing out",
                    "Timeout issues often indicate async problems. Are you using pytest-asyncio?",
                ),
                (
                    "Yes, but the fixtures aren't working",
                    "Fixture issues in pytest-asyncio are common. Let me help you fix them.",
                ),
                (
                    "Can you summarize our conversation?",
                    "I'd be happy to summarize our conversation about your software project.",
                ),
            ],
            created_at=datetime.now(),
            last_active_at=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_llm_service_integration_success(
        self, agent: SummarizationAgent, context_long_conversation: ConversationContext
    ) -> None:
        """Test successful integration with LLM service."""
        # Mock successful LLM response
        mock_llm_response = {
            "choices": [
                {
                    "message": {
                        "content": "This conversation covered a software development project discussion, including technology choices (Python/FastAPI), testing challenges, and debugging assistance with pytest-asyncio fixtures."
                    }
                }
            ]
        }

        mock_http_response = Mock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_llm_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_http_response
            )

            response = await agent.handle(
                context_long_conversation, "summarize our conversation"
            )

            assert response.response_text is not None
            assert "software development project" in response.response_text
            assert response.metadata["summary_type"] == "conversation_summary"
            assert response.metadata["history_length"] == 9

    @pytest.mark.asyncio
    async def test_llm_service_integration_timeout(
        self, agent: SummarizationAgent, context_long_conversation: ConversationContext
    ) -> None:
        """Test LLM service timeout handling."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = (
                httpx.TimeoutException("Request timeout")
            )

            response = await agent.handle(
                context_long_conversation, "summarize our conversation"
            )

            assert response.response_text is not None
            assert "trouble generating a summary" in response.response_text
            assert response.metadata["summary_type"] == "fallback"

    @pytest.mark.asyncio
    async def test_llm_service_integration_connection_error(
        self, agent: SummarizationAgent, context_long_conversation: ConversationContext
    ) -> None:
        """Test LLM service connection error handling."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = (
                httpx.ConnectError("Connection failed")
            )

            response = await agent.handle(
                context_long_conversation, "summarize our conversation"
            )

            assert response.response_text is not None
            assert "trouble generating a summary" in response.response_text
            assert response.metadata["summary_type"] == "fallback"

    @pytest.mark.asyncio
    async def test_llm_service_integration_http_error(
        self, agent: SummarizationAgent, context_long_conversation: ConversationContext
    ) -> None:
        """Test LLM service HTTP error handling."""
        mock_http_response = Mock()
        mock_http_response.status_code = 500
        mock_http_response.text = "Internal Server Error"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_http_response
            )

            response = await agent.handle(
                context_long_conversation, "summarize our conversation"
            )

            assert response.response_text is not None
            assert "trouble generating a summary" in response.response_text
            assert response.metadata["summary_type"] == "fallback"

    @pytest.mark.asyncio
    async def test_llm_service_integration_invalid_json(
        self, agent: SummarizationAgent, context_long_conversation: ConversationContext
    ) -> None:
        """Test LLM service invalid JSON response handling."""
        mock_http_response = Mock()
        mock_http_response.status_code = 200
        mock_http_response.json.side_effect = ValueError("Invalid JSON")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_http_response
            )

            response = await agent.handle(
                context_long_conversation, "summarize our conversation"
            )

            assert response.response_text is not None
            assert "trouble generating a summary" in response.response_text
            assert response.metadata["summary_type"] == "fallback"

    @pytest.mark.asyncio
    async def test_llm_service_integration_missing_choices(
        self, agent: SummarizationAgent, context_long_conversation: ConversationContext
    ) -> None:
        """Test LLM service response missing choices field."""
        mock_llm_response = {"message": "Success but no choices"}

        mock_http_response = Mock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_llm_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_http_response
            )

            response = await agent.handle(
                context_long_conversation, "summarize our conversation"
            )

            assert response.response_text is not None
            assert "trouble generating a summary" in response.response_text
            assert response.metadata["summary_type"] == "fallback"

    @pytest.mark.asyncio
    async def test_llm_service_integration_empty_choices(
        self, agent: SummarizationAgent, context_long_conversation: ConversationContext
    ) -> None:
        """Test LLM service response with empty choices array."""
        mock_llm_response: dict[str, Any] = {"choices": []}

        mock_http_response = Mock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_llm_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_http_response
            )

            response = await agent.handle(
                context_long_conversation, "summarize our conversation"
            )

            assert response.response_text is not None
            assert "trouble generating a summary" in response.response_text
            assert response.metadata["summary_type"] == "fallback"

    @pytest.mark.asyncio
    async def test_llm_service_integration_missing_content(
        self, agent: SummarizationAgent, context_long_conversation: ConversationContext
    ) -> None:
        """Test LLM service response missing content field."""
        mock_llm_response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant"
                        # Missing "content" field
                    }
                }
            ]
        }

        mock_http_response = Mock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_llm_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_http_response
            )

            response = await agent.handle(
                context_long_conversation, "summarize our conversation"
            )

            assert response.response_text is not None
            assert "trouble generating a summary" in response.response_text
            assert response.metadata["summary_type"] == "fallback"

    @pytest.mark.asyncio
    async def test_llm_service_integration_health_check(
        self, agent: SummarizationAgent
    ) -> None:
        """Test health check integration with LLM service."""
        mock_health_response = Mock()
        mock_health_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_health_response
            )

            health = await agent.health_check()

            assert health["llm_service_healthy"] is True
            assert health["llm_error"] is None

    @pytest.mark.asyncio
    async def test_llm_service_integration_health_check_failure(
        self, agent: SummarizationAgent
    ) -> None:
        """Test health check when LLM service is down."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                httpx.ConnectError("Service unavailable")
            )

            health = await agent.health_check()

            assert health["llm_service_healthy"] is False
            assert "Service unavailable" in health["llm_error"]

    @pytest.mark.asyncio
    async def test_llm_service_integration_request_format(
        self, agent: SummarizationAgent, context_long_conversation: ConversationContext
    ) -> None:
        """Test that LLM service receives correctly formatted request."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Test summary"}}]
            }
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            await agent.handle(context_long_conversation, "summarize our conversation")

            # Verify the request was made with correct format
            mock_client.return_value.__aenter__.return_value.post.assert_called_once()
            call_args = mock_client.return_value.__aenter__.return_value.post.call_args

            assert call_args[0][0] == "http://test-llm:8000/v1/chat/completions"

            request_data = call_args[1]["json"]
            assert request_data["model"] == "gpt-3.5-turbo"
            assert len(request_data["messages"]) == 2
            assert request_data["messages"][0]["role"] == "system"
            assert request_data["messages"][1]["role"] == "user"
            assert request_data["max_tokens"] == 500
            assert request_data["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_llm_service_integration_conversation_history_format(
        self, agent: SummarizationAgent, context_long_conversation: ConversationContext
    ) -> None:
        """Test that conversation history is properly formatted for LLM."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Test summary"}}]
            }
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            await agent.handle(context_long_conversation, "summarize our conversation")

            # Get the request data to verify history formatting
            call_args = mock_client.return_value.__aenter__.return_value.post.call_args
            request_data = call_args[1]["json"]
            user_message = request_data["messages"][1]["content"]

            # Verify history formatting
            assert "Turn 1:" in user_message
            assert "User: Hello" in user_message
            assert "Assistant: Hi there! How can I help you today?" in user_message
            assert "Turn 9:" in user_message
            assert "User: Can you summarize our conversation?" in user_message
