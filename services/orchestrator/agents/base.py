"""Abstract base class for all agents.

This module defines the core interface that all agents must implement,
providing a consistent contract for agent behavior and lifecycle management.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from services.common.logging import get_logger

from .types import AgentResponse, ConversationContext


logger = get_logger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all agents.

    This defines the core interface that all agents must implement.
    Agents are responsible for processing user input and generating responses.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the agent with optional configuration.

        Args:
            **kwargs: Agent-specific configuration parameters
        """
        self._logger = get_logger(self.__class__.__name__)
        self._config = kwargs
        self._logger.info("Agent initialized", extra={"agent_name": self.name})

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent identifier.

        This should be a short, descriptive name that uniquely identifies
        this agent type. Used for routing and logging.

        Returns:
            Agent name string
        """
        pass

    @abstractmethod
    async def handle(
        self, context: ConversationContext, transcript: str
    ) -> AgentResponse:
        """Handle a conversation turn.

        This is the main entry point for agent processing. The agent should
        analyze the user input and conversation context to generate an appropriate
        response.

        Args:
            context: Current conversation context with history
            transcript: User's transcribed speech input

        Returns:
            Agent response with text, audio, and/or actions

        Raises:
            AgentError: If the agent cannot process the input
        """
        pass

    async def can_handle(self, context: ConversationContext, transcript: str) -> bool:
        """Check if this agent can handle the given input.

        This is used for agent routing and selection. The default implementation
        returns True, but agents can override this to be more selective.

        Args:
            context: Current conversation context
            transcript: User's transcribed speech input

        Returns:
            True if this agent can handle the input, False otherwise
        """
        return True

    async def get_capabilities(self) -> list[str]:
        """Get a list of this agent's capabilities.

        This is used for agent discovery and documentation.

        Returns:
            List of capability strings
        """
        return [f"Process {self.name} requests"]

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value for this agent.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)

    def set_config(self, key: str, value: Any) -> None:
        """Set a configuration value for this agent.

        Args:
            key: Configuration key
            value: Configuration value
        """
        self._config[key] = value
        self._logger.debug("Agent config updated", extra={"key": key, "value": value})

    async def health_check(self) -> dict[str, Any]:
        """Perform a health check for this agent.

        This is used to verify that the agent is functioning correctly.

        Returns:
            Health check results
        """
        return {
            "agent_name": self.name,
            "status": "healthy",
            "capabilities": await self.get_capabilities(),
            "config_keys": list(self._config.keys()),
        }

    def __str__(self) -> str:
        """String representation of the agent."""
        return f"{self.__class__.__name__}(name={self.name})"

    def __repr__(self) -> str:
        """Detailed string representation of the agent."""
        return f"{self.__class__.__name__}(name={self.name}, config={self._config})"
