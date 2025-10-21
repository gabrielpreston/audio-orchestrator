"""Agent registry for managing available agents.

This module provides a registry system for discovering, registering, and managing
agents within the orchestrator service.
"""

from __future__ import annotations

from typing import Any, Optional

from services.common.logging import get_logger

from .base import BaseAgent

logger = get_logger(__name__)


class AgentRegistry:
    """Registry for managing available agents.
    
    This provides a centralized way to register, discover, and manage agents
    within the orchestrator service.
    """
    
    def __init__(self) -> None:
        """Initialize the agent registry."""
        self._agents: dict[str, BaseAgent] = {}
        self._logger = get_logger(__name__)
        self._logger.info("Agent registry initialized")
    
    def register(self, agent: BaseAgent) -> None:
        """Register an agent by name.
        
        Args:
            agent: Agent instance to register
            
        Raises:
            ValueError: If agent name is already registered
        """
        if not isinstance(agent, BaseAgent):
            raise ValueError("Agent must be a BaseAgent instance")
        
        agent_name = agent.name
        if agent_name in self._agents:
            raise ValueError(f"Agent '{agent_name}' is already registered")
        
        self._agents[agent_name] = agent
        self._logger.info(
            "Agent registered",
            extra={
                "agent_name": agent_name,
                "agent_class": agent.__class__.__name__,
                "total_agents": len(self._agents)
            }
        )
    
    def get(self, name: str) -> Optional[BaseAgent]:
        """Get agent by name.
        
        Args:
            name: Agent name to retrieve
            
        Returns:
            Agent instance if found, None otherwise
        """
        return self._agents.get(name)
    
    def list_agents(self) -> list[str]:
        """List all registered agent names.
        
        Returns:
            List of agent names
        """
        return list(self._agents.keys())
    
    def get_agent_info(self, name: str) -> Optional[dict[str, Any]]:
        """Get detailed information about an agent.
        
        Args:
            name: Agent name
            
        Returns:
            Agent information dictionary or None if not found
        """
        agent = self.get(name)
        if not agent:
            return None
        
        return {
            "name": agent.name,
            "class": agent.__class__.__name__,
            "capabilities": [],  # Will be populated by manager
            "config": agent._config
        }
    
    def unregister(self, name: str) -> bool:
        """Unregister an agent by name.
        
        Args:
            name: Agent name to unregister
            
        Returns:
            True if agent was unregistered, False if not found
        """
        if name not in self._agents:
            return False
        
        del self._agents[name]
        self._logger.info(
            "Agent unregistered",
            extra={"agent_name": name, "total_agents": len(self._agents)}
        )
        return True
    
    def clear(self) -> None:
        """Clear all registered agents."""
        agent_count = len(self._agents)
        self._agents.clear()
        self._logger.info(
            "All agents unregistered",
            extra={"previous_count": agent_count}
        )
    
    def __len__(self) -> int:
        """Get the number of registered agents."""
        return len(self._agents)
    
    def __contains__(self, name: str) -> bool:
        """Check if an agent is registered."""
        return name in self._agents
    
    def __iter__(self):
        """Iterate over registered agents."""
        return iter(self._agents.values())
    
    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_agents": len(self._agents),
            "agent_names": list(self._agents.keys()),
            "agent_classes": [agent.__class__.__name__ for agent in self._agents.values()]
        }
