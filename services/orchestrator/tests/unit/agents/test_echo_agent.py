"""Unit tests for echo agent."""

import pytest
from datetime import datetime

from services.orchestrator.agents.echo_agent import EchoAgent
from services.orchestrator.agents.types import ConversationContext


class TestEchoAgent:
    """Test EchoAgent class."""
    
    def test_echo_agent_creation(self):
        """Test creating an echo agent."""
        agent = EchoAgent()
        
        assert agent.name == "echo"
        assert isinstance(agent, EchoAgent)
    
    @pytest.mark.asyncio
    async def test_echo_agent_handle_basic(self):
        """Test basic echo functionality."""
        agent = EchoAgent()
        context = ConversationContext(
            session_id="test-session",
            history=[],
            created_at=datetime.now(),
            last_active_at=datetime.now()
        )
        
        response = await agent.handle(context, "Hello world")
        
        assert response.response_text == "You said: Hello world"
        assert response.response_audio is None
        assert response.actions == []
        assert response.metadata["agent_name"] == "echo"
        assert response.metadata["input_length"] == 11
    
    @pytest.mark.asyncio
    async def test_echo_agent_handle_empty_input(self):
        """Test handling empty input."""
        agent = EchoAgent()
        context = ConversationContext(
            session_id="test-session",
            history=[],
            created_at=datetime.now(),
            last_active_at=datetime.now()
        )
        
        response = await agent.handle(context, "")
        
        assert response.response_text == "I didn't hear anything. Could you try again?"
        assert response.metadata["echo_type"] == "simple"
    
    @pytest.mark.asyncio
    async def test_echo_agent_handle_long_input(self):
        """Test handling long input."""
        agent = EchoAgent()
        context = ConversationContext(
            session_id="test-session",
            history=[],
            created_at=datetime.now(),
            last_active_at=datetime.now()
        )
        
        long_text = "This is a very long message that should be truncated because it exceeds the maximum length allowed for a single response and should be handled appropriately by the echo agent."
        response = await agent.handle(context, long_text)
        
        # The echo agent doesn't actually truncate long text, it just echoes it back
        assert "You said:" in response.response_text
        assert long_text in response.response_text
    
    @pytest.mark.asyncio
    async def test_echo_agent_can_handle(self):
        """Test can_handle method."""
        agent = EchoAgent()
        context = ConversationContext(
            session_id="test-session",
            history=[],
            created_at=datetime.now(),
            last_active_at=datetime.now()
        )
        
        # Echo agent should be able to handle any input
        assert await agent.can_handle(context, "Hello") is True
        assert await agent.can_handle(context, "") is True
        assert await agent.can_handle(context, "Very long text...") is True
    
    @pytest.mark.asyncio
    async def test_echo_agent_get_capabilities(self):
        """Test get_capabilities method."""
        agent = EchoAgent()
        capabilities = await agent.get_capabilities()
        
        assert isinstance(capabilities, list)
        assert len(capabilities) > 0
        assert "Echo user input back" in capabilities
        assert "Handle any text input" in capabilities
    
    @pytest.mark.asyncio
    async def test_echo_agent_health_check(self):
        """Test health check."""
        agent = EchoAgent()
        health = await agent.health_check()
        
        assert health["agent_name"] == "echo"
        assert health["status"] == "healthy"
        assert "capabilities" in health
        assert "config_keys" in health
    
    def test_echo_agent_config(self):
        """Test configuration methods."""
        agent = EchoAgent()
        
        # Test getting config
        assert agent.get_config("nonexistent", "default") == "default"
        
        # Test setting config
        agent.set_config("test_key", "test_value")
        assert agent.get_config("test_key") == "test_value"
    
    def test_echo_agent_string_representation(self):
        """Test string representation."""
        agent = EchoAgent()
        
        assert "EchoAgent" in str(agent)
        assert "echo" in str(agent)
        
        assert "EchoAgent" in repr(agent)
        assert "echo" in repr(agent)
