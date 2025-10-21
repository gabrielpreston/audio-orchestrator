"""Unit tests for the EchoAgent."""

import pytest
from datetime import datetime
from agents.echo_agent import EchoAgent
from audio_pipeline.types import ConversationContext


@pytest.mark.asyncio
async def test_echo_agent_handles_transcript():
    """Test that EchoAgent returns the transcript as response text."""
    # Arrange
    agent = EchoAgent()
    context = ConversationContext(
        session_id="test-session",
        history=[],
        created_at=datetime.now(),
        last_active_at=datetime.now(),
    )
    transcript = "hello world"

    # Act
    response = await agent.handle(context, transcript)

    # Assert
    assert response.response_text == "hello world"
    assert response.response_audio is None
    assert response.actions == []
