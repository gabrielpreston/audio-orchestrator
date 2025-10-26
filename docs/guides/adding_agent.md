---
title: Adding a New Agent
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-22
---

# Adding a New Agent

## Overview

<!-- markdownlint-disable MD013 -->
Agents process user input and generate responses using various strategies (echo, summarization, intent classification, conversation, etc.). The agent framework provides a clean abstraction layer that allows the system to route user input to specialized agents based on context and requirements.
<!-- markdownlint-enable MD013 -->

## Architecture

The agent system consists of several key components:

-  **`BaseAgent`** - Abstract base class for all agents
-  **`AgentManager`** - Routes input to appropriate agents
-  **`AgentRegistry`** - Manages available agents
-  **`ConversationContext`** - Maintains conversation state
-  **`AgentResponse`** - Standardized response format

## Interface Requirements

### BaseAgent Interface

All agents must implement the `BaseAgent` interface:

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

## Step-by-Step Guide

### 1. Create Agent File

Create your agent file in the agents directory:

```bash
services/orchestrator_enhanced/agents/my_agent.py
```

### 2. Implement Agent Interface

Implement all required methods from the `BaseAgent` interface:

```python
"""Custom agent implementation."""

import logging
from typing import Optional

from services.orchestrator.agents.base import BaseAgent
from services.orchestrator.agents.types import ConversationContext, AgentResponse

logger = logging.getLogger(__name__)


class MyAgent(BaseAgent):
    """Custom agent for [your use case]."""
    
    def __init__(self, config: dict):
        """Initialize the agent with configuration."""
        self.config = config
        self._logger = logging.getLogger(__name__)
    
    @property
    def name(self) -> str:
        """Return the agent name."""
        return "my_agent"
    
    async def handle(
        self,
        context: ConversationContext,
        transcript: str
    ) -> AgentResponse:
        """Process user input and generate response."""
        try:
            # Process the transcript
            response_text = await self._process_transcript(transcript, context)
            
            # Create response
            return AgentResponse(
                response_text=response_text,
                response_audio=None,  # Optional audio response
                actions=[],  # Optional external actions
                metadata={"agent": self.name}
            )
        except Exception as e:
            self._logger.error(f"Error processing transcript: {e}")
            return AgentResponse(
                response_text="I'm sorry, I encountered an error processing your request.",
                metadata={"agent": self.name, "error": str(e)}
            )
    
    def can_handle(self, transcript: str, context: ConversationContext) -> bool:
        """Check if this agent can handle the given input."""
        # Implement your logic to determine if this agent should handle the input
        # For example, check for specific keywords, patterns, or context
        return self._should_handle(transcript, context)
    
    async def _process_transcript(self, transcript: str, context: ConversationContext) -> str:
        """Process the transcript and generate a response."""
        # Implement your agent's core logic here
        # This could involve:
        # - Calling external APIs
        # - Processing with LLM services
        # - Analyzing conversation history
        # - Generating contextual responses
        
        # Example: Simple keyword-based response
        if "hello" in transcript.lower():
            return "Hello! How can I help you today?"
        elif "help" in transcript.lower():
            return "I'm here to assist you. What would you like to know?"
        else:
            return f"I heard you say: '{transcript}'. How can I help with that?"
    
    def _should_handle(self, transcript: str, context: ConversationContext) -> bool:
        """Determine if this agent should handle the input."""
        # Example: Handle inputs containing specific keywords
        keywords = self.config.get("keywords", [])
        return any(keyword.lower() in transcript.lower() for keyword in keywords)
```

### 3. Register Agent

Register your agent in the agent manager:

```python
# In services/orchestrator_enhanced/agents/manager.py

from .my_agent import MyAgent

class AgentManager:
    def __init__(self):
        # ... existing code ...
        
        # Register your agent
        self.register_agent("my_agent", MyAgent)
```

### 4. Add Configuration

Add configuration options for your agent:

```python
# In services/orchestrator_enhanced/config.py

# My Agent Configuration
MY_AGENT_ENABLED = env.bool("MY_AGENT_ENABLED", default=True)
MY_AGENT_KEYWORDS = env.list("MY_AGENT_KEYWORDS", default=["help", "assist"])
MY_AGENT_PRIORITY = env.int("MY_AGENT_PRIORITY", default=5)
```

Add to `.env.sample`:

```bash
# My Agent Configuration
MY_AGENT_ENABLED=true
MY_AGENT_KEYWORDS=help,assist,support
MY_AGENT_PRIORITY=5
```

### 5. Write Tests

Create comprehensive tests for your agent:

```python
"""Tests for MyAgent."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.orchestrator.agents.my_agent import MyAgent
from services.orchestrator.agents.types import ConversationContext, AgentResponse


@pytest.fixture
def agent_config():
    """Test configuration for agent."""
    return {
        "keywords": ["help", "assist"],
        "priority": 5,
        "enabled": True
    }


@pytest.fixture
def my_agent(agent_config):
    """Create agent instance for testing."""
    return MyAgent(agent_config)


@pytest.fixture
def conversation_context():
    """Create test conversation context."""
    return ConversationContext(
        session_id="test_session",
        history=[("Hello", "Hi there!")],
        created_at=datetime.now(),
        last_active_at=datetime.now()
    )


class TestMyAgent:
    """Test MyAgent functionality."""
    
    def test_agent_name(self, my_agent):
        """Test agent name property."""
        assert my_agent.name == "my_agent"
    
    def test_can_handle_with_keywords(self, my_agent, conversation_context):
        """Test can_handle with matching keywords."""
        assert my_agent.can_handle("Can you help me?", conversation_context) is True
        assert my_agent.can_handle("I need assistance", conversation_context) is True
    
    def test_can_handle_without_keywords(self, my_agent, conversation_context):
        """Test can_handle without matching keywords."""
        assert my_agent.can_handle("What's the weather?", conversation_context) is False
    
    @pytest.mark.asyncio
    async def test_handle_greeting(self, my_agent, conversation_context):
        """Test handling greeting input."""
        response = await my_agent.handle(conversation_context, "Hello there!")
        
        assert isinstance(response, AgentResponse)
        assert "Hello" in response.response_text
        assert response.metadata["agent"] == "my_agent"
    
    @pytest.mark.asyncio
    async def test_handle_help_request(self, my_agent, conversation_context):
        """Test handling help request."""
        response = await my_agent.handle(conversation_context, "I need help with something")
        
        assert isinstance(response, AgentResponse)
        assert "help" in response.response_text.lower()
        assert response.metadata["agent"] == "my_agent"
    
    @pytest.mark.asyncio
    async def test_handle_general_input(self, my_agent, conversation_context):
        """Test handling general input."""
        response = await my_agent.handle(conversation_context, "Tell me about the weather")
        
        assert isinstance(response, AgentResponse)
        assert "weather" in response.response_text
        assert response.metadata["agent"] == "my_agent"
    
    @pytest.mark.asyncio
    async def test_error_handling(self, my_agent, conversation_context):
        """Test error handling in agent."""
        # Mock an error in processing
        with patch.object(my_agent, '_process_transcript', side_effect=Exception("Processing error")):
            response = await my_agent.handle(conversation_context, "Test input")
            
            assert isinstance(response, AgentResponse)
            assert "error" in response.response_text.lower()
            assert "error" in response.metadata
```

## Example: Weather Agent

Here's a complete example of a weather agent:

```python
"""Weather agent for providing weather information."""

import logging
from typing import Optional
import httpx

from services.orchestrator.agents.base import BaseAgent
from services.orchestrator.agents.types import ConversationContext, AgentResponse

logger = logging.getLogger(__name__)


class WeatherAgent(BaseAgent):
    """Agent that provides weather information."""
    
    def __init__(self, config: dict):
        """Initialize weather agent."""
        self.config = config
        self.api_key = config.get("weather_api_key")
        self.base_url = config.get("weather_api_url", "https://api.openweathermap.org/data/2.5")
        self._logger = logging.getLogger(__name__)
    
    @property
    def name(self) -> str:
        """Return the agent name."""
        return "weather"
    
    async def handle(
        self,
        context: ConversationContext,
        transcript: str
    ) -> AgentResponse:
        """Process weather-related requests."""
        try:
            # Extract location from transcript
            location = self._extract_location(transcript)
            if not location:
                return AgentResponse(
                    response_text="I need to know which city you'd like weather for. Please specify a location.",
                    metadata={"agent": self.name}
                )
            
            # Get weather data
            weather_data = await self._get_weather_data(location)
            if not weather_data:
                return AgentResponse(
                    response_text=f"Sorry, I couldn't get weather data for {location}.",
                    metadata={"agent": self.name}
                )
            
            # Format response
            response_text = self._format_weather_response(weather_data, location)
            
            return AgentResponse(
                response_text=response_text,
                metadata={"agent": self.name, "location": location}
            )
            
        except Exception as e:
            self._logger.error(f"Weather agent error: {e}")
            return AgentResponse(
                response_text="I'm sorry, I'm having trouble getting weather information right now.",
                metadata={"agent": self.name, "error": str(e)}
            )
    
    def can_handle(self, transcript: str, context: ConversationContext) -> bool:
        """Check if this is a weather-related request."""
        weather_keywords = [
            "weather", "temperature", "forecast", "rain", "sunny", "cloudy",
            "hot", "cold", "humidity", "wind", "storm"
        ]
        return any(keyword in transcript.lower() for keyword in weather_keywords)
    
    def _extract_location(self, transcript: str) -> Optional[str]:
        """Extract location from transcript."""
        # Simple location extraction - in practice, you might use NLP
        words = transcript.lower().split()
        
        # Look for common location indicators
        location_indicators = ["in", "at", "for", "weather in", "forecast for"]
        
        for i, word in enumerate(words):
            if word in location_indicators and i + 1 < len(words):
                # Extract the next few words as potential location
                location_words = words[i + 1:i + 4]  # Take up to 3 words
                return " ".join(location_words).title()
        
        return None
    
    async def _get_weather_data(self, location: str) -> Optional[dict]:
        """Get weather data from API."""
        if not self.api_key:
            self._logger.warning("No weather API key configured")
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/weather"
                params = {
                    "q": location,
                    "appid": self.api_key,
                    "units": "metric"
                }
                
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                return response.json()
                
        except Exception as e:
            self._logger.error(f"Failed to get weather data: {e}")
            return None
    
    def _format_weather_response(self, weather_data: dict, location: str) -> str:
        """Format weather data into a readable response."""
        try:
            main = weather_data["main"]
            weather = weather_data["weather"][0]
            
            temp = main["temp"]
            description = weather["description"]
            humidity = main["humidity"]
            
            response = f"The weather in {location} is {description} with a temperature of {temp}°C and {humidity}% humidity."
            
            return response
            
        except KeyError as e:
            self._logger.error(f"Unexpected weather data format: {e}")
            return f"Weather information for {location} is available, but I couldn't format it properly."
```

## Example: Calculator Agent

Here's another example of a calculator agent:

```python
"""Calculator agent for mathematical operations."""

import logging
import re
from typing import Optional

from services.orchestrator.agents.base import BaseAgent
from services.orchestrator.agents.types import ConversationContext, AgentResponse

logger = logging.getLogger(__name__)


class CalculatorAgent(BaseAgent):
    """Agent that performs mathematical calculations."""
    
    def __init__(self, config: dict):
        """Initialize calculator agent."""
        self.config = config
        self._logger = logging.getLogger(__name__)
    
    @property
    def name(self) -> str:
        """Return the agent name."""
        return "calculator"
    
    async def handle(
        self,
        context: ConversationContext,
        transcript: str
    ) -> AgentResponse:
        """Process mathematical calculations."""
        try:
            # Extract mathematical expression
            expression = self._extract_expression(transcript)
            if not expression:
                return AgentResponse(
                    response_text="I can help with calculations. Please provide a mathematical expression.",
                    metadata={"agent": self.name}
                )
            
            # Calculate result
            result = self._calculate(expression)
            if result is None:
                return AgentResponse(
                    response_text="I couldn't understand that mathematical expression. Please try again.",
                    metadata={"agent": self.name}
                )
            
            # Format response
            response_text = f"The result of {expression} is {result}"
            
            return AgentResponse(
                response_text=response_text,
                metadata={"agent": self.name, "expression": expression, "result": result}
            )
            
        except Exception as e:
            self._logger.error(f"Calculator agent error: {e}")
            return AgentResponse(
                response_text="I'm sorry, I encountered an error with that calculation.",
                metadata={"agent": self.name, "error": str(e)}
            )
    
    def can_handle(self, transcript: str, context: ConversationContext) -> bool:
        """Check if this is a mathematical request."""
        math_patterns = [
            r'\d+\s*[+\-*/]\s*\d+',  # Basic operations
            r'calculate', r'compute', r'math', r'add', r'subtract', r'multiply', r'divide',
            r'plus', r'minus', r'times', r'equals'
        ]
        
        transcript_lower = transcript.lower()
        return any(re.search(pattern, transcript_lower) for pattern in math_patterns)
    
    def _extract_expression(self, transcript: str) -> Optional[str]:
        """Extract mathematical expression from transcript."""
        # Simple pattern matching for basic expressions
        patterns = [
            r'(\d+\s*[+\-*/]\s*\d+(?:\s*[+\-*/]\s*\d+)*)',  # Basic operations
            r'calculate\s+([0-9+\-*/.\s]+)',  # "calculate 2 + 3"
            r'what\s+is\s+([0-9+\-*/.\s]+)',  # "what is 2 + 3"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _calculate(self, expression: str) -> Optional[float]:
        """Safely calculate mathematical expression."""
        try:
            # Clean the expression
            expression = expression.replace(' ', '')
            
            # Validate expression (basic safety check)
            if not re.match(r'^[0-9+\-*/.()\s]+$', expression):
                return None
            
            # Evaluate the expression
            result = eval(expression)
            return float(result)
            
        except Exception as e:
            self._logger.error(f"Calculation error: {e}")
            return None
```

## Testing Strategies

### Unit Tests

-  Test individual methods in isolation
-  Mock external dependencies (APIs, services, etc.)
-  Test error conditions and edge cases
-  Verify response format and metadata

### Component Tests

-  Test agent with mocked dependencies
-  Test routing logic and agent selection
-  Test conversation context handling
-  Verify agent registration and configuration

### Integration Tests

-  Test agent with real external services when possible
-  Test agent within the full orchestrator system
-  Verify end-to-end agent functionality
-  Test performance and latency requirements

### Manual Testing

-  Test with real user inputs
-  Verify agent behavior in different contexts
-  Test conversation flow and context management
-  Validate response quality and accuracy

## Common Pitfalls and Solutions

### 1. Agent Selection Issues

**Problem:** Agent not being selected for appropriate inputs
**Solution:** Implement robust `can_handle()` logic with proper keyword matching and context analysis

### 2. External Service Failures

**Problem:** Agent crashes when external services are unavailable
**Solution:** Implement proper error handling and graceful degradation

### 3. Context Management

**Problem:** Agent doesn't maintain conversation context properly
**Solution:** Use `ConversationContext` effectively and update context as needed

### 4. Performance Issues

**Problem:** Agent causes high latency or resource usage
**Solution:** Implement caching, async operations, and resource management

### 5. Response Formatting

**Problem:** Agent responses are inconsistent or poorly formatted
**Solution:** Follow `AgentResponse` format and include proper metadata

## Best Practices

1.  **Error Handling:** Always handle exceptions gracefully
2.  **Logging:** Use structured logging with correlation IDs
3.  **Configuration:** Make agents configurable through environment variables
4.  **Testing:** Write comprehensive tests for all code paths
5.  **Documentation:** Document agent behavior and configuration options
6.  **Performance:** Consider latency and resource usage
7.  **Security:** Validate inputs and handle sensitive data properly
8.  **Maintainability:** Write clear, well-documented code

## Integration with Orchestrator

Once your agent is implemented and tested, it can be used by the orchestrator:

```python
# In orchestrator configuration
AGENT_DEFAULT = "my_agent"
AGENT_ROUTING_ENABLED = true

# The orchestrator will automatically use your agent
# when these environment variables are set
```

## Next Steps

1.  Implement your agent following this guide
2.  Write comprehensive tests
3.  Test with real inputs and scenarios
4.  Submit a pull request with your implementation
5.  Update this documentation if you discover new patterns

## Resources

-  [Agent Types Reference](../api/agent_types.md)
-  [Agent Testing Guide](../guides/testing_agents.md)
-  [Configuration Reference](../api/configuration.md)
-  [Orchestrator Integration](../architecture/orchestrator.md)
