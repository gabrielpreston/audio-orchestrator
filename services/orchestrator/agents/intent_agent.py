"""
Intent Classification Agent

This agent classifies user intent and routes to specialized agents based on the
classified intent. It uses LLM integration for intelligent intent classification
and maintains a mapping of intents to appropriate agents.
"""

import logging
from typing import Any, TYPE_CHECKING

import httpx
from services.orchestrator.agents.base import BaseAgent
from services.orchestrator.agents.types import AgentResponse, ConversationContext

if TYPE_CHECKING:
    from services.orchestrator.agents.manager import AgentManager


class IntentClassificationAgent(BaseAgent):
    """Classifies user intent and routes to specialized agents."""

    def __init__(
        self,
        llm_service_url: str,
        agent_manager: "AgentManager",
        intent_classes: dict[str, str] | None = None,
        llm_model: str = "gpt-3.5-turbo",
    ):
        """Initialize the intent classification agent.

        Args:
            llm_service_url: URL of the LLM service for intent classification
            agent_manager: Agent manager for routing to specialized agents
            intent_classes: Optional mapping of intents to agent names. If None, uses defaults.
            llm_model: LLM model name to use for classification. Defaults to gpt-3.5-turbo.
        """
        self.llm_url = llm_service_url
        self.agent_manager = agent_manager
        self.llm_model = llm_model
        self._logger = logging.getLogger(__name__)

        # Intent classification configuration - use provided or defaults
        self.intent_classes = (
            intent_classes
            or {
                "echo": "echo",
                "summarize": "summarization",
                "general": "echo",  # Fixed: use echo agent for general intent
                "help": "echo",
                "weather": "echo",  # Fixed: use echo agent for weather intent
                "time": "echo",  # Fixed: use echo agent for time intent
            }
        )

        # Intent classification prompt template
        self.classification_prompt = """Classify the user's intent from the following transcript:

Transcript: "{transcript}"

Available intents: {intents}

Respond with only the intent name (one of: {intent_list}).

Examples:
- "hello" -> general
- "echo this back" -> echo
- "summarize our conversation" -> summarize
- "what time is it" -> time
- "help me" -> help

Intent:"""

    @property
    def name(self) -> str:
        """Return the agent name."""
        return "intent_classifier"

    async def handle(
        self, context: ConversationContext, transcript: str
    ) -> AgentResponse:
        """Classify intent and route to appropriate agent.

        Args:
            context: Conversation context with history
            transcript: User's transcript to classify

        Returns:
            AgentResponse from the routed agent
        """
        try:
            # Classify the user's intent
            intent = await self._classify_intent(transcript)
            self._logger.info(
                "Intent classified",
                extra={
                    "transcript": transcript[:100] + "..."
                    if len(transcript) > 100
                    else transcript,
                    "intent": intent,
                    "session_id": context.session_id,
                },
            )

            # Get the appropriate agent for the intent
            agent = self._get_agent_for_intent(intent)

            # Route to the specialized agent
            return await agent.handle(context, transcript)

        except Exception as e:
            self._logger.error(
                "Error in intent classification",
                extra={
                    "error": str(e),
                    "transcript": transcript[:100] + "..."
                    if len(transcript) > 100
                    else transcript,
                    "session_id": context.session_id,
                },
            )

            # Fallback to echo agent on error
            fallback_agent = self.agent_manager.registry.get("echo")
            if fallback_agent is None:
                return AgentResponse(response_text="Error: No fallback agent available")
            result = await fallback_agent.handle(context, transcript)
            return result

    async def _classify_intent(self, transcript: str) -> str:
        """Classify user intent using LLM.

        Args:
            transcript: User's transcript to classify

        Returns:
            Classified intent string
        """
        try:
            # Build the classification prompt
            intent_list = list(self.intent_classes.keys())
            prompt = self.classification_prompt.format(
                transcript=transcript,
                intents=", ".join(intent_list),
                intent_list=", ".join(intent_list),
            )

            # Call LLM service for classification
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.llm_url}/v1/chat/completions",
                    json={
                        "model": self.llm_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 10,
                        "temperature": 0.1,
                    },
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

                result = response.json()
                intent = str(result["choices"][0]["message"]["content"]).strip().lower()

                # Validate the intent is in our known intents
                if intent in self.intent_classes:
                    return intent
                else:
                    self._logger.warning(
                        "Unknown intent classified",
                        extra={"intent": intent, "transcript": transcript[:100]},
                    )
                    return "general"  # Default fallback

        except httpx.HTTPError as e:
            self._logger.error(
                "HTTP error in intent classification",
                extra={"error": str(e), "transcript": transcript[:100]},
            )
            return "general"  # Fallback to general intent

        except Exception as e:
            self._logger.error(
                "Error in intent classification",
                extra={"error": str(e), "transcript": transcript[:100]},
            )
            return "general"  # Fallback to general intent

    def _get_agent_for_intent(self, intent: str) -> BaseAgent:
        """Get agent based on classified intent.

        Args:
            intent: The classified intent

        Returns:
            The appropriate agent for the intent
        """
        agent_name = self.intent_classes.get(intent, "echo")
        agent = self.agent_manager.registry.get(agent_name)

        if agent is None:
            self._logger.warning(
                "Agent not found for intent",
                extra={"intent": intent, "agent_name": agent_name},
            )
            # Fallback to echo agent
            fallback_agent = self.agent_manager.registry.get("echo")
            if fallback_agent is None:
                # This should never happen in practice, but we need to return something
                from services.orchestrator.agents.echo_agent import EchoAgent

                return EchoAgent()
            return fallback_agent

        return agent

    async def can_handle(self, context: ConversationContext, transcript: str) -> bool:
        """Determine if this agent can handle the request.

        The intent classifier can handle any request as it routes to other agents.

        Args:
            context: Conversation context
            transcript: User's transcript

        Returns:
            Always True (intent classifier handles all requests)
        """
        return True

    async def health_check(self) -> dict[str, Any]:
        """Check the health of the intent classification agent.

        Returns:
            Health status dictionary
        """
        try:
            # Test LLM service connectivity
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.llm_url}/health/ready")
                llm_healthy = response.status_code == 200
        except Exception:
            llm_healthy = False

        return {
            "agent_name": self.name,
            "llm_service_healthy": llm_healthy,
            "intent_classes": list(self.intent_classes.keys()),
            "available_agents": list(self.agent_manager.registry.list_agents()),
        }
