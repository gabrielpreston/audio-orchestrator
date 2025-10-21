"""Unit tests for agent registry."""

from unittest.mock import Mock

import pytest

from services.orchestrator.agents.base import BaseAgent
from services.orchestrator.agents.echo_agent import EchoAgent
from services.orchestrator.agents.registry import AgentRegistry


class TestAgentRegistry:
    """Test AgentRegistry class."""

    def test_registry_creation(self):
        """Test creating an agent registry."""
        registry = AgentRegistry()

        assert len(registry) == 0
        assert registry.list_agents() == []

    def test_register_agent(self):
        """Test registering an agent."""
        registry = AgentRegistry()
        agent = EchoAgent()

        registry.register(agent)

        assert len(registry) == 1
        assert "echo" in registry
        assert registry.get("echo") == agent

    def test_register_duplicate_agent(self):
        """Test registering a duplicate agent."""
        registry = AgentRegistry()
        agent1 = EchoAgent()
        agent2 = EchoAgent()

        registry.register(agent1)

        with pytest.raises(ValueError, match="Agent 'echo' is already registered"):
            registry.register(agent2)

    def test_register_invalid_agent(self):
        """Test registering an invalid agent."""
        registry = AgentRegistry()

        with pytest.raises(ValueError, match="Agent must be a BaseAgent instance"):
            registry.register("not_an_agent")  # type: ignore

    def test_get_agent(self):
        """Test getting an agent."""
        registry = AgentRegistry()
        agent = EchoAgent()

        registry.register(agent)

        retrieved_agent = registry.get("echo")
        assert retrieved_agent == agent

        # Test getting non-existent agent
        assert registry.get("nonexistent") is None

    def test_list_agents(self):
        """Test listing agents."""
        registry = AgentRegistry()
        agent1 = EchoAgent()
        agent2 = Mock(spec=BaseAgent)
        agent2.name = "mock_agent"

        registry.register(agent1)
        registry.register(agent2)

        agents = registry.list_agents()
        assert len(agents) == 2
        assert "echo" in agents
        assert "mock_agent" in agents

    def test_get_agent_info(self):
        """Test getting agent information."""
        registry = AgentRegistry()
        agent = EchoAgent()

        registry.register(agent)

        info = registry.get_agent_info("echo")
        assert info is not None
        assert info["name"] == "echo"
        assert info["class"] == "EchoAgent"
        assert "config" in info

        # Test getting info for non-existent agent
        assert registry.get_agent_info("nonexistent") is None

    def test_unregister_agent(self):
        """Test unregistering an agent."""
        registry = AgentRegistry()
        agent = EchoAgent()

        registry.register(agent)
        assert len(registry) == 1

        # Test unregistering existing agent
        result = registry.unregister("echo")
        assert result is True
        assert len(registry) == 0
        assert "echo" not in registry

        # Test unregistering non-existent agent
        result = registry.unregister("nonexistent")
        assert result is False

    def test_clear_registry(self):
        """Test clearing the registry."""
        registry = AgentRegistry()
        agent1 = EchoAgent()
        agent2 = Mock(spec=BaseAgent)
        agent2.name = "mock_agent"

        registry.register(agent1)
        registry.register(agent2)
        assert len(registry) == 2

        registry.clear()
        assert len(registry) == 0
        assert registry.list_agents() == []

    def test_registry_iteration(self):
        """Test iterating over the registry."""
        registry = AgentRegistry()
        agent1 = EchoAgent()
        agent2 = Mock(spec=BaseAgent)
        agent2.name = "mock_agent"

        registry.register(agent1)
        registry.register(agent2)

        agents = list(registry)
        assert len(agents) == 2
        assert agent1 in agents
        assert agent2 in agents

    def test_registry_contains(self):
        """Test checking if agent is in registry."""
        registry = AgentRegistry()
        agent = EchoAgent()

        registry.register(agent)

        assert "echo" in registry
        assert "nonexistent" not in registry

    def test_get_stats(self):
        """Test getting registry statistics."""
        registry = AgentRegistry()
        agent1 = EchoAgent()
        agent2 = Mock(spec=BaseAgent)
        agent2.name = "mock_agent"

        registry.register(agent1)
        registry.register(agent2)

        stats = registry.get_stats()
        assert stats["total_agents"] == 2
        assert "echo" in stats["agent_names"]
        assert "mock_agent" in stats["agent_names"]
        assert "EchoAgent" in stats["agent_classes"]
