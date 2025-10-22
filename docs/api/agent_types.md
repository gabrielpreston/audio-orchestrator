# Agent Types Reference

## Overview

This document provides a complete reference for all agent types and interfaces used in the audio orchestrator platform.

## Base Interfaces

### BaseAgent

Abstract base class for all agents.

```python
from abc import ABC, abstractmethod
from services.orchestrator.agents.types import ConversationContext, AgentResponse

class BaseAgent(ABC):
    """Abstract base class for all agents."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the agent name."""
        pass
    
    @abstractmethod
    async def handle(
        self,
        context: ConversationContext,
        transcript: str
    ) -> AgentResponse:
        """Process user input and generate response."""
        pass
    
    def can_handle(self, transcript: str, context: ConversationContext) -> bool:
        """Check if this agent can handle the given input."""
        return True
```

## Data Types

### AgentResponse

Represents the response from an agent.

```python
from dataclasses import dataclass
from typing import Optional, List, Any
from services.orchestrator.agents.types import ExternalAction

@dataclass
class AgentResponse:
    """Response from an agent."""
    
    response_text: Optional[str] = None          # Text response
    response_audio: Optional[AsyncIterator[AudioChunk]] = None  # Audio response
    actions: List[ExternalAction] = field(default_factory=list)  # External actions
    metadata: Optional[dict[str, Any]] = None    # Additional metadata
```

### ConversationContext

Maintains conversation state and history.

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Any

@dataclass
class ConversationContext:
    """Current conversation state and history."""
    
    session_id: str                              # Unique session identifier
    history: List[tuple[str, str]]              # (user_input, agent_response) pairs
    created_at: datetime                        # Session creation time
    last_active_at: datetime                    # Last activity time
    metadata: Optional[dict[str, Any]] = None  # Additional context metadata
    
    def add_turn(self, user_input: str, agent_response: str) -> None:
        """Add a conversation turn to history."""
        self.history.append((user_input, agent_response))
        self.last_active_at = datetime.now()
    
    def get_recent_history(self, max_turns: int = 10) -> List[tuple[str, str]]:
        """Get the most recent conversation turns."""
        return self.history[-max_turns:] if self.history else []
    
    def get_session_duration(self) -> float:
        """Get session duration in seconds."""
        return (self.last_active_at - self.created_at).total_seconds()
```

### ExternalAction

Represents an action the agent can take.

```python
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class ExternalAction:
    """External action that an agent can perform."""
    
    action_type: str                            # Type of action (e.g., "api_call", "file_operation")
    action_data: dict[str, Any]                 # Action-specific data
    priority: int = 0                           # Action priority (higher = more important)
    metadata: Optional[dict[str, Any]] = None  # Additional action metadata
```

## Built-in Agents

### EchoAgent

Simple agent that echoes user input.

```python
class EchoAgent(BaseAgent):
    """Agent that echoes user input back."""
    
    @property
    def name(self) -> str:
        return "echo"
    
    async def handle(
        self,
        context: ConversationContext,
        transcript: str
    ) -> AgentResponse:
        """Echo the user input."""
        return AgentResponse(
            response_text=f"You said: {transcript}",
            metadata={"agent": self.name}
        )
    
    def can_handle(self, transcript: str, context: ConversationContext) -> bool:
        """Handle all inputs."""
        return True
```

### SummarizationAgent

Agent that summarizes conversation history.

```python
class SummarizationAgent(BaseAgent):
    """Agent that summarizes conversation history."""
    
    def __init__(self, llm_service_url: str):
        self.llm_url = llm_service_url
    
    @property
    def name(self) -> str:
        return "summarization"
    
    async def handle(
        self,
        context: ConversationContext,
        transcript: str
    ) -> AgentResponse:
        """Generate summary of conversation history."""
        if not context.history:
            return AgentResponse(
                response_text="There's no conversation history to summarize yet."
            )
        
        # Build prompt from history
        history_text = "\n".join([
            f"User: {user}\nAssistant: {agent}"
            for user, agent in context.history
        ])
        
        # Call LLM service to generate summary
        summary = await self._generate_summary(history_text)
        
        return AgentResponse(
            response_text=summary,
            metadata={"agent": self.name, "history_length": len(context.history)}
        )
    
    def can_handle(self, transcript: str, context: ConversationContext) -> bool:
        """Handle summarization requests."""
        summary_keywords = ["summarize", "summary", "recap", "what did we discuss"]
        return any(keyword in transcript.lower() for keyword in summary_keywords)
    
    async def _generate_summary(self, history_text: str) -> str:
        """Generate summary using LLM service."""
        # Implementation would call LLM service
        return f"(Summary of {len(history_text.split())} words)"
```

### IntentClassificationAgent

Agent that classifies user intent and routes to specialized agents.

```python
class IntentClassificationAgent(BaseAgent):
    """Classifies user intent and routes to specialized agents."""
    
    def __init__(self, llm_service_url: str, agent_manager: 'AgentManager'):
        self.llm_url = llm_service_url
        self.agent_manager = agent_manager
    
    @property
    def name(self) -> str:
        return "intent_classifier"
    
    async def handle(
        self,
        context: ConversationContext,
        transcript: str
    ) -> AgentResponse:
        """Classify intent and route to appropriate agent."""
        # Classify user intent
        intent = await self._classify_intent(transcript)
        
        # Route to specialized agent
        agent = self._get_agent_for_intent(intent)
        return await agent.handle(context, transcript)
    
    def can_handle(self, transcript: str, context: ConversationContext) -> bool:
        """Handle all inputs for routing."""
        return True
    
    async def _classify_intent(self, transcript: str) -> str:
        """Classify user intent using LLM."""
        # Implementation would call LLM service for classification
        return "general"
    
    def _get_agent_for_intent(self, intent: str) -> BaseAgent:
        """Get agent based on classified intent."""
        intent_mapping = {
            "weather": "weather",
            "calculation": "calculator",
            "general": "conversation"
        }
        agent_name = intent_mapping.get(intent, "echo")
        return self.agent_manager.get_agent(agent_name)
```

### ConversationAgent

Agent for natural multi-turn conversations.

```python
class ConversationAgent(BaseAgent):
    """Agent for natural multi-turn conversations."""
    
    def __init__(self, llm_service_url: str, max_history: int = 10):
        self.llm_url = llm_service_url
        self.max_history = max_history
    
    @property
    def name(self) -> str:
        return "conversation"
    
    async def handle(
        self,
        context: ConversationContext,
        transcript: str
    ) -> AgentResponse:
        """Generate contextual response using conversation history."""
        # Build conversation history for LLM
        messages = self._build_message_history(context)
        messages.append({"role": "user", "content": transcript})
        
        # Call LLM service with history
        response_text = await self._generate_response(messages)
        
        return AgentResponse(
            response_text=response_text,
            metadata={"agent": self.name, "history_used": len(messages)}
        )
    
    def can_handle(self, transcript: str, context: ConversationContext) -> bool:
        """Handle general conversation."""
        return True
    
    def _build_message_history(
        self,
        context: ConversationContext
    ) -> List[dict[str, str]]:
        """Convert history to LLM message format."""
        messages = []
        for user_msg, agent_msg in context.get_recent_history(self.max_history):
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": agent_msg})
        return messages
    
    async def _generate_response(self, messages: List[dict[str, str]]) -> str:
        """Call LLM to generate response."""
        # Implementation would call LLM service
        return "(LLM response placeholder)"
```

## Agent Manager

### AgentManager

Manages agent registration and routing.

```python
class AgentManager:
    """Manages agent registration and routing."""
    
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._routing_enabled = True
    
    def register_agent(self, name: str, agent: BaseAgent) -> None:
        """Register an agent."""
        self._agents[name] = agent
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Get agent by name."""
        return self._agents.get(name)
    
    def list_agents(self) -> List[str]:
        """List all registered agent names."""
        return list(self._agents.keys())
    
    async def select_agent(
        self,
        transcript: str,
        context: ConversationContext
    ) -> BaseAgent:
        """Select appropriate agent for input."""
        if not self._routing_enabled:
            return self._agents.get("default", self._agents["echo"])
        
        # Find agents that can handle the input
        candidates = []
        for agent in self._agents.values():
            if agent.can_handle(transcript, context):
                candidates.append(agent)
        
        # Return first candidate or default
        return candidates[0] if candidates else self._agents.get("default")
    
    async def process_transcript(
        self,
        transcript: str,
        context: ConversationContext
    ) -> AgentResponse:
        """Process transcript with selected agent."""
        agent = await self.select_agent(transcript, context)
        return await agent.handle(context, transcript)
```

### AgentRegistry

Manages agent registration and statistics.

```python
class AgentRegistry:
    """Registry for managing agents."""
    
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._stats: Dict[str, int] = {}
    
    def register(self, name: str, agent: BaseAgent) -> None:
        """Register an agent."""
        self._agents[name] = agent
        self._stats[name] = 0
    
    def get(self, name: str) -> Optional[BaseAgent]:
        """Get agent by name."""
        return self._agents.get(name)
    
    def list_agents(self) -> List[str]:
        """List all registered agent names."""
        return list(self._agents.keys())
    
    def get_stats(self) -> Dict[str, int]:
        """Get agent usage statistics."""
        return self._stats.copy()
    
    def increment_usage(self, agent_name: str) -> None:
        """Increment usage count for agent."""
        if agent_name in self._stats:
            self._stats[agent_name] += 1
```

## Configuration

### Environment Variables

```bash
# Agent Configuration
AGENT_DEFAULT=conversation          # Default agent to use
AGENT_ROUTING_ENABLED=true         # Enable agent routing
AGENT_MAX_HISTORY=10               # Maximum conversation history

# LLM Service Configuration
LLM_SERVICE_URL=http://llm:8000    # LLM service URL
LLM_TIMEOUT=30                     # LLM request timeout

# Agent-Specific Configuration
WEATHER_API_KEY=your_api_key       # Weather API key
CALCULATOR_PRECISION=2             # Calculator decimal precision
```

### Configuration Examples

#### Echo Agent Configuration

```python
echo_config = {
    "enabled": True,
    "priority": 1
}
```

#### Conversation Agent Configuration

```python
conversation_config = {
    "llm_service_url": "http://llm:8000",
    "max_history": 10,
    "timeout": 30,
    "temperature": 0.7
}
```

#### Weather Agent Configuration

```python
weather_config = {
    "weather_api_key": "your_api_key",
    "weather_api_url": "https://api.openweathermap.org/data/2.5",
    "keywords": ["weather", "temperature", "forecast"],
    "priority": 5
}
```

## Error Handling

### Common Exceptions

```python
class AgentError(Exception):
    """Base exception for agent errors."""
    pass

class AgentNotAvailableError(AgentError):
    """Raised when agent is not available."""
    pass

class AgentConfigurationError(AgentError):
    """Raised when agent configuration is invalid."""
    pass

class AgentProcessingError(AgentError):
    """Raised when agent processing fails."""
    pass
```

### Error Handling Best Practices

1.  **Graceful Degradation:** Handle errors without crashing
2.  **Logging:** Log errors with context information
3.  **Retry Logic:** Implement retry for transient failures
4.  **User Feedback:** Provide meaningful error messages
5.  **Resource Cleanup:** Always clean up resources on error

## Performance Considerations

### Latency Requirements

-  **Agent Selection:** < 50ms for agent routing
-  **Response Generation:** < 2s for agent responses
-  **Context Processing:** < 100ms for context updates
-  **End-to-End:** < 2s total response time

### Memory Management

-  **Context History:** Limit conversation history size
-  **Agent State:** Avoid storing large objects in agent state
-  **Resource Cleanup:** Clean up resources after processing

### CPU Usage

-  **Agent Processing:** Minimize CPU usage in hot paths
-  **LLM Calls:** Use async operations for external calls
-  **Caching:** Cache frequently used data

## Testing

### Unit Testing

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_agent_handling():
    """Test agent input handling."""
    agent = MyAgent(config)
    context = ConversationContext(...)
    
    response = await agent.handle(context, "test input")
    
    assert isinstance(response, AgentResponse)
    assert response.response_text is not None
```

### Component Testing

```python
@pytest.mark.component
async def test_agent_routing():
    """Test agent selection and routing."""
    manager = AgentManager()
    # Register agents
    # Test routing logic
```

### Integration Testing

```python
@pytest.mark.integration
async def test_agent_integration():
    """Test agent with real services."""
    # Test with actual LLM service
    # Test with real external APIs
```

## Best Practices

### Agent Development

1.  **Single Responsibility:** Each agent should have a clear purpose
2.  **Error Handling:** Always handle exceptions gracefully
3.  **Logging:** Use structured logging with correlation IDs
4.  **Configuration:** Make agents configurable
5.  **Testing:** Write comprehensive tests
6.  **Documentation:** Document agent behavior and configuration

### Performance

1.  **Async Operations:** Use async/await for I/O operations
2.  **Resource Management:** Clean up resources properly
3.  **Caching:** Cache expensive operations when appropriate
4.  **Monitoring:** Track agent performance and usage

### Security

1.  **Input Validation:** Validate all inputs
2.  **Output Sanitization:** Sanitize outputs when necessary
3.  **Credential Management:** Handle credentials securely
4.  **Rate Limiting:** Implement rate limiting for external calls
