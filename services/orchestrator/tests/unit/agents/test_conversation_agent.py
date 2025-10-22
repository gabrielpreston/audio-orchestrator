"""Unit tests for ConversationAgent."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from services.orchestrator.agents.conversation_agent import ConversationAgent
from services.orchestrator.agents.types import ConversationContext


@pytest.fixture
def mock_llm_service_url():
    """Mock LLM service URL."""
    return "http://mock-llm-service:8000"


@pytest.fixture
def mock_conversation_context():
    """Mock conversation context with history."""
    return ConversationContext(
        session_id="test-session-123",
        history=[
            ("Hello", "Hi there!"),
            ("How are you?", "I'm doing great, thanks!"),
        ],
        created_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def conversation_agent(mock_llm_service_url):
    """Create ConversationAgent instance."""
    return ConversationAgent(llm_service_url=mock_llm_service_url)


@pytest.mark.asyncio
async def test_conversation_agent_name(conversation_agent):
    """Test the name property of the ConversationAgent."""
    assert conversation_agent.name == "conversation"


@pytest.mark.asyncio
async def test_build_message_history(conversation_agent, mock_conversation_context):
    """Test building message history for LLM."""
    expected_messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "I'm doing great, thanks!"},
    ]
    messages = conversation_agent._build_message_history(mock_conversation_context)
    assert messages == expected_messages


@pytest.mark.asyncio
async def test_build_message_history_max_turns(
    conversation_agent, mock_conversation_context
):
    """Test building message history with max_turns limit."""
    conversation_agent.max_history = 1
    expected_messages = [
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "I'm doing great, thanks!"},
    ]
    messages = conversation_agent._build_message_history(mock_conversation_context)
    assert messages == expected_messages


@pytest.mark.asyncio
async def test_generate_response_success(conversation_agent, mock_llm_service_url):
    """Test successful LLM response generation."""
    mock_response_content = "This is a generated response."
    mock_httpx_post = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": mock_response_content}}]},
            raise_for_status=MagicMock(),
        )
    )

    with patch("httpx.AsyncClient.post", mock_httpx_post):
        messages = [{"role": "user", "content": "Test message"}]
        response_text = await conversation_agent._generate_response(messages)
        assert response_text == mock_response_content
        mock_httpx_post.assert_awaited_once_with(
            f"{mock_llm_service_url}/v1/chat/completions",
            json={
                "model": "gpt-3.5-turbo",
                "messages": messages,
                "max_tokens": 150,
                "temperature": 0.7,
            },
            headers={"Content-Type": "application/json"},
        )


@pytest.mark.asyncio
async def test_generate_response_http_error(conversation_agent):
    """Test HTTP error handling during LLM response generation."""
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_httpx_post = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Error", request=httpx.Request("POST", "/"), response=mock_response
        )
    )

    with patch("httpx.AsyncClient.post", mock_httpx_post):
        messages = [{"role": "user", "content": "Test message"}]
        with pytest.raises(httpx.HTTPStatusError):
            await conversation_agent._generate_response(messages)


@pytest.mark.asyncio
async def test_handle_success(
    conversation_agent, mock_conversation_context, mock_llm_service_url
):
    """Test successful handling of a transcript."""
    mock_response_content = "Agent's reply."
    mock_generate_response = AsyncMock(return_value=mock_response_content)

    with patch.object(conversation_agent, "_generate_response", mock_generate_response):
        transcript = "User's new message."
        response = await conversation_agent.handle(
            mock_conversation_context, transcript
        )
        assert response.response_text == mock_response_content
        mock_generate_response.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_error(conversation_agent, mock_conversation_context):
    """Test error handling in handle method."""
    mock_generate_response = AsyncMock(side_effect=Exception("LLM failed"))

    with patch.object(conversation_agent, "_generate_response", mock_generate_response):
        transcript = "User's new message."
        response = await conversation_agent.handle(
            mock_conversation_context, transcript
        )
        assert (
            response.response_text
            == "I'm sorry, I'm having trouble understanding right now."
        )
        mock_generate_response.assert_awaited_once()


@pytest.mark.asyncio
async def test_can_handle(conversation_agent, mock_conversation_context):
    """Test can_handle method always returns True."""
    assert (
        await conversation_agent.can_handle(mock_conversation_context, "any transcript")
        is True
    )


@pytest.mark.asyncio
async def test_health_check_llm_healthy(conversation_agent, mock_llm_service_url):
    """Test health check when LLM service is healthy."""
    mock_httpx_get = AsyncMock(
        return_value=MagicMock(status_code=200, raise_for_status=MagicMock())
    )

    with patch("httpx.AsyncClient.get", mock_httpx_get):
        health_status = await conversation_agent.health_check()
        assert health_status["llm_service_healthy"] is True
        assert health_status["agent_name"] == "conversation"
        assert health_status["max_history"] == 10
        mock_httpx_get.assert_awaited_once_with(f"{mock_llm_service_url}/health/ready")


@pytest.mark.asyncio
async def test_health_check_llm_unhealthy(conversation_agent, mock_llm_service_url):
    """Test health check when LLM service is unhealthy."""
    import httpx

    mock_httpx_get = AsyncMock(
        side_effect=httpx.RequestError(
            "Connection error", request=httpx.Request("GET", "/")
        )
    )

    with patch("httpx.AsyncClient.get", mock_httpx_get):
        health_status = await conversation_agent.health_check()
        assert health_status["llm_service_healthy"] is False
        mock_httpx_get.assert_awaited_once_with(f"{mock_llm_service_url}/health/ready")
