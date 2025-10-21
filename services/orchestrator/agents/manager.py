"""Agent manager for selection and routing.

This module provides the main interface for agent management, including
agent selection, routing, and coordination within the orchestrator service.
"""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

from .base import BaseAgent
from .registry import AgentRegistry
from .types import AgentResponse, ConversationContext


logger = get_logger(__name__)


class AgentManager:
    """Manages agent selection and routing.

    This is the main interface for agent management within the orchestrator.
    It handles agent registration, selection, and coordination.
    """

    def __init__(
        self, agents: list[BaseAgent] | None = None, default_agent: str = "echo"
    ) -> None:
        """Initialize the agent manager.

        Args:
            agents: List of agents to register initially
            default_agent: Name of the default agent to use
        """
        self.registry = AgentRegistry()
        self.default_agent = default_agent
        self._logger = get_logger(__name__)

        # Register initial agents
        if agents:
            for agent in agents:
                self.registry.register(agent)

        self._logger.info(
            "Agent manager initialized",
            extra={
                "default_agent": self.default_agent,
                "registered_agents": len(self.registry),
            },
        )

    def register_agent(self, agent: BaseAgent) -> None:
        """Register a new agent.

        Args:
            agent: Agent instance to register
        """
        self.registry.register(agent)
        self._logger.info(
            "Agent registered via manager", extra={"agent_name": agent.name}
        )

    async def select_agent(
        self, transcript: str, context: ConversationContext
    ) -> BaseAgent:
        """Select appropriate agent based on transcript and context.

        This implements the core routing logic for agent selection.
        The current implementation uses simple keyword-based routing.

        Args:
            transcript: User's transcribed speech
            context: Current conversation context

        Returns:
            Selected agent instance

        Raises:
            ValueError: If no suitable agent is found
        """
        self._logger.debug(
            "Selecting agent",
            extra={
                "session_id": context.session_id,
                "transcript_length": len(transcript),
                "available_agents": self.registry.list_agents(),
            },
        )

        # Simple keyword-based routing
        transcript_lower = transcript.lower()

        # Check for specific agent requests
        if "echo" in transcript_lower or transcript_lower.startswith("echo"):
            agent = self.registry.get("echo")
            if agent:
                self._logger.info("Selected echo agent based on keyword")
                return agent

        # Check if any agent can handle the input
        for agent_name in self.registry.list_agents():
            agent = self.registry.get(agent_name)
            if agent:
                try:
                    can_handle = await agent.can_handle(context, transcript)
                    if can_handle:
                        self._logger.info(
                            "Selected agent based on capability",
                            extra={"agent_name": agent_name},
                        )
                        return agent
                except Exception as e:
                    self._logger.warning(
                        "Error checking agent capability",
                        extra={"agent_name": agent_name, "error": str(e)},
                    )
                    continue

        # Fall back to default agent
        default_agent = self.registry.get(self.default_agent)
        if not default_agent:
            raise ValueError(f"Default agent '{self.default_agent}' not found")

        self._logger.info(
            "Using default agent", extra={"agent_name": self.default_agent}
        )
        return default_agent

    async def process_transcript(
        self, transcript: str, context: ConversationContext
    ) -> AgentResponse:
        """Process a transcript through the appropriate agent.

        This is the main entry point for transcript processing.
        It selects the appropriate agent and processes the transcript.

        Args:
            transcript: User's transcribed speech
            context: Current conversation context

        Returns:
            Agent response with text, audio, and/or actions
        """
        try:
            # Select appropriate agent
            agent = await self.select_agent(transcript, context)

            # Process transcript
            response = await agent.handle(context, transcript)

            # Log the interaction
            self._logger.info(
                "Transcript processed",
                extra={
                    "session_id": context.session_id,
                    "agent_name": agent.name,
                    "has_text": bool(response.response_text),
                    "has_audio": bool(response.response_audio),
                    "action_count": len(response.actions),
                },
            )

            return response

        except Exception as e:
            self._logger.error(
                "Error processing transcript",
                extra={
                    "session_id": context.session_id,
                    "error": str(e),
                    "transcript_length": len(transcript),
                },
            )
            raise

    async def get_agent_capabilities(self) -> dict[str, list[str]]:
        """Get capabilities of all registered agents.

        Returns:
            Dictionary mapping agent names to their capabilities
        """
        capabilities = {}
        for agent in self.registry:
            try:
                agent_capabilities = await agent.get_capabilities()
                capabilities[agent.name] = agent_capabilities
            except Exception as e:
                self._logger.warning(
                    "Error getting agent capabilities",
                    extra={"agent_name": agent.name, "error": str(e)},
                )
                capabilities[agent.name] = ["Error retrieving capabilities"]

        return capabilities

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on all agents.

        Returns:
            Health check results for all agents
        """
        health_results = {}

        for agent in self.registry:
            try:
                agent_health = await agent.health_check()
                health_results[agent.name] = agent_health
            except Exception as e:
                self._logger.warning(
                    "Error during agent health check",
                    extra={"agent_name": agent.name, "error": str(e)},
                )
                health_results[agent.name] = {"status": "unhealthy", "error": str(e)}

        return {
            "manager_status": "healthy",
            "total_agents": len(self.registry),
            "agents": health_results,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get manager statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_agents": len(self.registry),
            "default_agent": self.default_agent,
            "registered_agents": self.registry.list_agents(),
            "registry_stats": self.registry.get_stats(),
        }
