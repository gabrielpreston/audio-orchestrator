"""Unit tests for agent manager."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from services.orchestrator.agents.manager import AgentManager
from services.orchestrator.agents.echo_agent import EchoAgent
from services.orchestrator.agents.types import ConversationContext, AgentResponse


class TestAgentManager:
    """Test AgentManager class."""
    
    def test_manager_creation(self):
        """Test creating an agent manager."""
        manager = AgentManager()
        
        assert manager.default_agent == "echo"
        assert len(manager.registry) == 0
    
    def test_manager_creation_with_agents(self):
        """Test creating a manager with initial agents."""
        agent = EchoAgent()
        manager = AgentManager(agents=[agent])
        
        assert len(manager.registry) == 1
        assert "echo" in manager.registry
    
    def test_register_agent(self):
        """Test registering an agent through the manager."""
        manager = AgentManager()
        agent = EchoAgent()
        
        manager.register_agent(agent)
        
        assert len(manager.registry) == 1
        assert "echo" in manager.registry
    
    @pytest.mark.asyncio
    async def test_select_agent_echo_keyword(self):
        """Test selecting echo agent based on keyword."""
        manager = AgentManager()
        agent = EchoAgent()
        manager.register_agent(agent)
        
        context = ConversationContext(
            session_id="test-session",
            history=[],
            created_at=datetime.now(),
            last_active_at=datetime.now()
        )
        
        selected_agent = await manager.select_agent("echo hello world", context)
        assert selected_agent.name == "echo"
    
    @pytest.mark.asyncio
    async def test_select_agent_default(self):
        """Test selecting default agent."""
        manager = AgentManager()
        agent = EchoAgent()
        manager.register_agent(agent)
        
        context = ConversationContext(
            session_id="test-session",
            history=[],
            created_at=datetime.now(),
            last_active_at=datetime.now()
        )
        
        selected_agent = await manager.select_agent("hello world", context)
        assert selected_agent.name == "echo"
    
    @pytest.mark.asyncio
    async def test_select_agent_no_default(self):
        """Test selecting agent when no default is available."""
        manager = AgentManager(default_agent="nonexistent")
        
        context = ConversationContext(
            session_id="test-session",
            history=[],
            created_at=datetime.now(),
            last_active_at=datetime.now()
        )
        
        with pytest.raises(ValueError, match="Default agent 'nonexistent' not found"):
            await manager.select_agent("hello world", context)
    
    @pytest.mark.asyncio
    async def test_process_transcript(self):
        """Test processing a transcript."""
        manager = AgentManager()
        agent = EchoAgent()
        manager.register_agent(agent)
        
        context = ConversationContext(
            session_id="test-session",
            history=[],
            created_at=datetime.now(),
            last_active_at=datetime.now()
        )
        
        response = await manager.process_transcript("hello world", context)
        
        assert isinstance(response, AgentResponse)
        assert response.response_text is not None
        assert "hello world" in response.response_text
    
    @pytest.mark.asyncio
    async def test_process_transcript_error(self):
        """Test processing a transcript with error."""
        manager = AgentManager()
        
        # Create a mock agent that raises an exception
        mock_agent = Mock(spec=EchoAgent)
        mock_agent.name = "mock_agent"
        mock_agent.can_handle = AsyncMock(return_value=True)
        mock_agent.handle = AsyncMock(side_effect=Exception("Test error"))
        
        manager.register_agent(mock_agent)
        
        context = ConversationContext(
            session_id="test-session",
            history=[],
            created_at=datetime.now(),
            last_active_at=datetime.now()
        )
        
        with pytest.raises(Exception, match="Test error"):
            await manager.process_transcript("hello world", context)
    
    @pytest.mark.asyncio
    async def test_get_agent_capabilities(self):
        """Test getting agent capabilities."""
        manager = AgentManager()
        agent = EchoAgent()
        manager.register_agent(agent)
        
        capabilities = await manager.get_agent_capabilities()
        
        assert "echo" in capabilities
        assert isinstance(capabilities["echo"], list)
        assert len(capabilities["echo"]) > 0
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        manager = AgentManager()
        agent = EchoAgent()
        manager.register_agent(agent)
        
        health = await manager.health_check()
        
        assert health["manager_status"] == "healthy"
        assert health["total_agents"] == 1
        assert "echo" in health["agents"]
        assert health["agents"]["echo"]["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_health_check_with_error(self):
        """Test health check with agent error."""
        manager = AgentManager()
        
        # Create a mock agent that raises an exception during health check
        mock_agent = Mock(spec=EchoAgent)
        mock_agent.name = "mock_agent"
        mock_agent.health_check = AsyncMock(side_effect=Exception("Health check error"))
        
        manager.register_agent(mock_agent)
        
        health = await manager.health_check()
        
        assert health["manager_status"] == "healthy"
        assert health["total_agents"] == 1
        assert "mock_agent" in health["agents"]
        assert health["agents"]["mock_agent"]["status"] == "unhealthy"
        assert "Health check error" in health["agents"]["mock_agent"]["error"]
    
    def test_get_stats(self):
        """Test getting manager statistics."""
        manager = AgentManager()
        agent = EchoAgent()
        manager.register_agent(agent)
        
        stats = manager.get_stats()
        
        assert stats["total_agents"] == 1
        assert stats["default_agent"] == "echo"
        assert "echo" in stats["registered_agents"]
        assert "registry_stats" in stats
