---
title: Testing Audio Agents
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-22
---

# Testing Audio Agents

## Overview

This guide covers comprehensive testing strategies for audio agents in the audio orchestrator platform. It includes unit testing, component testing, integration testing, and end-to-end testing approaches.

## Testing Framework

The platform uses pytest with async support for testing agents:

```python
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from services.orchestrator.agents.base import BaseAgent
from services.orchestrator.agents.types import ConversationContext, AgentResponse
```

## Unit Testing

### Basic Agent Testing

Test individual agent methods in isolation:

```python
"""Unit tests for MyAgent."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

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
    async def test_error_handling(self, my_agent, conversation_context):
        """Test error handling in agent."""
        # Mock an error in processing
        with patch.object(my_agent, '_process_transcript', side_effect=Exception("Processing error")):
            response = await my_agent.handle(conversation_context, "Test input")
            
            assert isinstance(response, AgentResponse)
            assert "error" in response.response_text.lower()
            assert "error" in response.metadata
```

### Testing External Dependencies

Mock external services and APIs:

```python
"""Test agent with external dependencies."""

import pytest
from unittest.mock import AsyncMock, patch
import httpx

from services.orchestrator.agents.weather_agent import WeatherAgent


@pytest.fixture
def weather_agent():
    """Create weather agent for testing."""
    config = {
        "weather_api_key": "test_key",
        "weather_api_url": "https://api.test.com"
    }
    return WeatherAgent(config)


@pytest.mark.asyncio
async def test_weather_agent_success(weather_agent, conversation_context):
    """Test successful weather request."""
    # Mock successful API response
    mock_response = {
        "main": {"temp": 20, "humidity": 60},
        "weather": [{"description": "clear sky"}]
    }
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get.return_value.json.return_value = mock_response
        mock_client.return_value.__aenter__.return_value.get.return_value.raise_for_status.return_value = None
        
        response = await weather_agent.handle(conversation_context, "What's the weather in London?")
        
        assert isinstance(response, AgentResponse)
        assert "20" in response.response_text
        assert "clear sky" in response.response_text
        assert response.metadata["location"] == "London"


@pytest.mark.asyncio
async def test_weather_agent_api_failure(weather_agent, conversation_context):
    """Test weather agent when API fails."""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get.side_effect = httpx.HTTPError("API Error")
        
        response = await weather_agent.handle(conversation_context, "What's the weather in London?")
        
        assert isinstance(response, AgentResponse)
        assert "trouble" in response.response_text.lower()
        assert "error" in response.metadata


@pytest.mark.asyncio
async def test_weather_agent_no_location(weather_agent, conversation_context):
    """Test weather agent when no location is provided."""
    response = await weather_agent.handle(conversation_context, "Tell me about the weather")
    
    assert isinstance(response, AgentResponse)
    assert "location" in response.response_text.lower()
```

### Testing Agent Configuration

Test agent behavior with different configurations:

```python
"""Test agent configuration handling."""

import pytest
from services.orchestrator.agents.my_agent import MyAgent


def test_agent_with_different_configs():
    """Test agent with different configuration options."""
    # Test with keywords
    config_with_keywords = {
        "keywords": ["help", "assist", "support"],
        "priority": 5
    }
    agent1 = MyAgent(config_with_keywords)
    
    # Test with empty keywords
    config_empty_keywords = {
        "keywords": [],
        "priority": 1
    }
    agent2 = MyAgent(config_empty_keywords)
    
    # Test with missing config
    config_missing = {}
    agent3 = MyAgent(config_missing)
    
    # Verify agents are created successfully
    assert agent1.name == "my_agent"
    assert agent2.name == "my_agent"
    assert agent3.name == "my_agent"


def test_agent_configuration_validation():
    """Test agent configuration validation."""
    # Test invalid configuration
    invalid_config = {
        "keywords": "not_a_list",  # Should be a list
        "priority": "not_a_number"  # Should be a number
    }
    
    # Agent should handle invalid config gracefully
    agent = MyAgent(invalid_config)
    assert agent.name == "my_agent"
```

## Component Testing

### Testing Agent Manager

Test agent registration and routing:

```python
"""Component tests for AgentManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.orchestrator.agents.manager import AgentManager
from services.orchestrator.agents.types import ConversationContext


@pytest.fixture
def agent_manager():
    """Create agent manager for testing."""
    return AgentManager()


@pytest.fixture
def mock_agents():
    """Create mock agents for testing."""
    agent1 = AsyncMock()
    agent1.name = "agent1"
    agent1.can_handle.return_value = True
    
    agent2 = AsyncMock()
    agent2.name = "agent2"
    agent2.can_handle.return_value = False
    
    return [agent1, agent2]


@pytest.mark.asyncio
async def test_agent_registration(agent_manager, mock_agents):
    """Test agent registration."""
    # Register agents
    for agent in mock_agents:
        agent_manager.register_agent(agent.name, agent)
    
    # Verify registration
    assert len(agent_manager.list_agents()) == 2
    assert "agent1" in agent_manager.list_agents()
    assert "agent2" in agent_manager.list_agents()


@pytest.mark.asyncio
async def test_agent_selection(agent_manager, mock_agents, conversation_context):
    """Test agent selection logic."""
    # Register agents
    for agent in mock_agents:
        agent_manager.register_agent(agent.name, agent)
    
    # Test selection
    selected_agent = await agent_manager.select_agent("test input", conversation_context)
    
    # Should select agent1 (can_handle returns True)
    assert selected_agent.name == "agent1"


@pytest.mark.asyncio
async def test_agent_processing(agent_manager, mock_agents, conversation_context):
    """Test agent processing workflow."""
    # Register agents
    for agent in mock_agents:
        agent_manager.register_agent(agent.name, agent)
    
    # Mock agent response
    mock_response = MagicMock()
    mock_agents[0].handle.return_value = mock_response
    
    # Process transcript
    response = await agent_manager.process_transcript("test input", conversation_context)
    
    # Verify processing
    assert response == mock_response
    mock_agents[0].handle.assert_called_once_with(conversation_context, "test input")
```

### Testing Agent Registry

Test agent registry functionality:

```python
"""Component tests for AgentRegistry."""

import pytest
from unittest.mock import MagicMock

from services.orchestrator.agents.registry import AgentRegistry


@pytest.fixture
def agent_registry():
    """Create agent registry for testing."""
    return AgentRegistry()


@pytest.fixture
def mock_agent():
    """Create mock agent for testing."""
    agent = MagicMock()
    agent.name = "test_agent"
    return agent


def test_agent_registration(agent_registry, mock_agent):
    """Test agent registration in registry."""
    # Register agent
    agent_registry.register("test_agent", mock_agent)
    
    # Verify registration
    assert "test_agent" in agent_registry.list_agents()
    assert agent_registry.get("test_agent") == mock_agent


def test_agent_retrieval(agent_registry, mock_agent):
    """Test agent retrieval from registry."""
    # Register agent
    agent_registry.register("test_agent", mock_agent)
    
    # Retrieve agent
    retrieved_agent = agent_registry.get("test_agent")
    assert retrieved_agent == mock_agent
    
    # Test non-existent agent
    non_existent = agent_registry.get("non_existent")
    assert non_existent is None


def test_agent_statistics(agent_registry, mock_agent):
    """Test agent usage statistics."""
    # Register agent
    agent_registry.register("test_agent", mock_agent)
    
    # Check initial stats
    stats = agent_registry.get_stats()
    assert stats["test_agent"] == 0
    
    # Increment usage
    agent_registry.increment_usage("test_agent")
    agent_registry.increment_usage("test_agent")
    
    # Check updated stats
    stats = agent_registry.get_stats()
    assert stats["test_agent"] == 2
```

## Integration Testing

### Testing with Real Services

Test agents with actual external services:

```python
"""Integration tests for agents with real services."""

import pytest
import httpx
from datetime import datetime

from services.orchestrator.agents.weather_agent import WeatherAgent
from services.orchestrator.agents.types import ConversationContext


@pytest.fixture
def weather_agent_real():
    """Create weather agent with real API key."""
    config = {
        "weather_api_key": "real_api_key",  # Use real API key for integration tests
        "weather_api_url": "https://api.openweathermap.org/data/2.5"
    }
    return WeatherAgent(config)


@pytest.fixture
def conversation_context():
    """Create conversation context for testing."""
    return ConversationContext(
        session_id="integration_test",
        history=[],
        created_at=datetime.now(),
        last_active_at=datetime.now()
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_weather_agent_real_api(weather_agent_real, conversation_context):
    """Test weather agent with real API."""
    # This test requires a real API key and network access
    response = await weather_agent_real.handle(conversation_context, "What's the weather in London?")
    
    assert isinstance(response, AgentResponse)
    assert response.response_text is not None
    assert "London" in response.response_text
    assert response.metadata["location"] == "London"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_weather_agent_invalid_location(weather_agent_real, conversation_context):
    """Test weather agent with invalid location."""
    response = await weather_agent_real.handle(conversation_context, "What's the weather in InvalidCity123?")
    
    assert isinstance(response, AgentResponse)
    # Should handle invalid location gracefully
    assert "error" in response.response_text.lower() or "not found" in response.response_text.lower()
```

### Testing Agent Orchestration

Test agents working together:

```python
"""Integration tests for agent orchestration."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.orchestrator.agents.manager import AgentManager
from services.orchestrator.agents.types import ConversationContext


@pytest.fixture
def orchestrated_agents():
    """Create multiple agents for orchestration testing."""
    manager = AgentManager()
    
    # Create mock agents
    echo_agent = AsyncMock()
    echo_agent.name = "echo"
    echo_agent.can_handle.return_value = True
    echo_agent.handle.return_value = MagicMock(response_text="Echo response")
    
    weather_agent = AsyncMock()
    weather_agent.name = "weather"
    weather_agent.can_handle.return_value = False
    weather_agent.handle.return_value = MagicMock(response_text="Weather response")
    
    # Register agents
    manager.register_agent("echo", echo_agent)
    manager.register_agent("weather", weather_agent)
    
    return manager


@pytest.mark.asyncio
async def test_agent_orchestration(orchestrated_agents, conversation_context):
    """Test multiple agents working together."""
    # Test with input that echo agent can handle
    response = await orchestrated_agents.process_transcript("Hello", conversation_context)
    
    assert response.response_text == "Echo response"
    
    # Test with input that weather agent can handle
    weather_agent = orchestrated_agents.get_agent("weather")
    weather_agent.can_handle.return_value = True
    
    response = await orchestrated_agents.process_transcript("What's the weather?", conversation_context)
    
    assert response.response_text == "Weather response"
```

## End-to-End Testing

### Testing Complete Workflows

Test complete agent workflows from input to output:

```python
"""End-to-end tests for agent workflows."""

import pytest
from datetime import datetime

from services.orchestrator.agents.manager import AgentManager
from services.orchestrator.agents.types import ConversationContext


@pytest.fixture
def e2e_agent_manager():
    """Create agent manager for E2E testing."""
    manager = AgentManager()
    
    # Register real agents (not mocks)
    from services.orchestrator.agents.echo_agent import EchoAgent
    from services.orchestrator.agents.weather_agent import WeatherAgent
    
    manager.register_agent("echo", EchoAgent({}))
    manager.register_agent("weather", WeatherAgent({
        "weather_api_key": "test_key",
        "weather_api_url": "https://api.test.com"
    }))
    
    return manager


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_complete_conversation_flow(e2e_agent_manager):
    """Test complete conversation flow with multiple turns."""
    # Create conversation context
    context = ConversationContext(
        session_id="e2e_test",
        history=[],
        created_at=datetime.now(),
        last_active_at=datetime.now()
    )
    
    # First turn - echo agent
    response1 = await e2e_agent_manager.process_transcript("Hello", context)
    assert "Hello" in response1.response_text
    
    # Add to context
    context.add_turn("Hello", response1.response_text)
    
    # Second turn - weather agent
    response2 = await e2e_agent_manager.process_transcript("What's the weather in London?", context)
    assert "weather" in response2.response_text.lower()
    
    # Add to context
    context.add_turn("What's the weather in London?", response2.response_text)
    
    # Verify context history
    assert len(context.history) == 2
    assert context.history[0][0] == "Hello"
    assert context.history[1][0] == "What's the weather in London?"
```

### Testing Performance Requirements

Test agent performance against requirements:

```python
"""Performance tests for agents."""

import pytest
import time
from datetime import datetime

from services.orchestrator.agents.manager import AgentManager
from services.orchestrator.agents.types import ConversationContext


@pytest.mark.performance
@pytest.mark.asyncio
async def test_agent_response_latency():
    """Test agent response latency meets requirements."""
    manager = AgentManager()
    
    # Register fast agent
    from services.orchestrator.agents.echo_agent import EchoAgent
    manager.register_agent("echo", EchoAgent({}))
    
    context = ConversationContext(
        session_id="perf_test",
        history=[],
        created_at=datetime.now(),
        last_active_at=datetime.now()
    )
    
    # Measure response time
    start_time = time.time()
    response = await manager.process_transcript("Test input", context)
    end_time = time.time()
    
    response_time = end_time - start_time
    
    # Should be under 2 seconds
    assert response_time < 2.0
    assert response.response_text is not None


@pytest.mark.performance
@pytest.mark.asyncio
async def test_agent_concurrent_processing():
    """Test agent handling concurrent requests."""
    import asyncio
    
    manager = AgentManager()
    from services.orchestrator.agents.echo_agent import EchoAgent
    manager.register_agent("echo", EchoAgent({}))
    
    async def process_request(session_id):
        context = ConversationContext(
            session_id=session_id,
            history=[],
            created_at=datetime.now(),
            last_active_at=datetime.now()
        )
        return await manager.process_transcript(f"Request {session_id}", context)
    
    # Process multiple requests concurrently
    tasks = [process_request(f"session_{i}") for i in range(10)]
    responses = await asyncio.gather(*tasks)
    
    # All requests should complete successfully
    assert len(responses) == 10
    for response in responses:
        assert response.response_text is not None
```

## Test Data and Fixtures

### Creating Test Data

Create reusable test data and fixtures:

```python
"""Test data and fixtures for agent testing."""

import pytest
from datetime import datetime
from typing import List, Dict, Any

from services.orchestrator.agents.types import ConversationContext, AgentResponse


@pytest.fixture
def sample_conversation_contexts():
    """Create sample conversation contexts for testing."""
    return [
        ConversationContext(
            session_id="session_1",
            history=[("Hello", "Hi there!")],
            created_at=datetime.now(),
            last_active_at=datetime.now()
        ),
        ConversationContext(
            session_id="session_2",
            history=[
                ("Hello", "Hi there!"),
                ("How are you?", "I'm doing well, thanks!")
            ],
            created_at=datetime.now(),
            last_active_at=datetime.now()
        ),
        ConversationContext(
            session_id="session_3",
            history=[],
            created_at=datetime.now(),
            last_active_at=datetime.now()
        )
    ]


@pytest.fixture
def sample_transcripts():
    """Create sample transcripts for testing."""
    return [
        "Hello",
        "How are you?",
        "What's the weather like?",
        "Can you help me?",
        "Calculate 2 + 2",
        "Tell me a joke",
        "What time is it?",
        "Goodbye"
    ]


@pytest.fixture
def sample_agent_configs():
    """Create sample agent configurations for testing."""
    return {
        "echo": {
            "enabled": True,
            "priority": 1
        },
        "weather": {
            "weather_api_key": "test_key",
            "weather_api_url": "https://api.test.com",
            "keywords": ["weather", "temperature", "forecast"],
            "priority": 5
        },
        "calculator": {
            "precision": 2,
            "keywords": ["calculate", "math", "compute"],
            "priority": 3
        }
    }


@pytest.fixture
def mock_external_responses():
    """Create mock external service responses."""
    return {
        "weather_api": {
            "success": {
                "main": {"temp": 20, "humidity": 60},
                "weather": [{"description": "clear sky"}]
            },
            "error": {"error": "Invalid API key"}
        },
        "llm_service": {
            "success": {
                "response": "This is a test response from the LLM service.",
                "tokens_used": 50
            },
            "error": {"error": "Service unavailable"}
        }
    }
```

### Test Utilities

Create utility functions for testing:

```python
"""Test utilities for agent testing."""

import pytest
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

from services.orchestrator.agents.types import ConversationContext, AgentResponse


def create_mock_agent(name: str, can_handle: bool = True, response_text: str = "Mock response"):
    """Create a mock agent for testing."""
    agent = AsyncMock()
    agent.name = name
    agent.can_handle.return_value = can_handle
    agent.handle.return_value = AgentResponse(
        response_text=response_text,
        metadata={"agent": name}
    )
    return agent


def create_conversation_context(
    session_id: str = "test_session",
    history: List[tuple[str, str]] = None
) -> ConversationContext:
    """Create a conversation context for testing."""
    if history is None:
        history = []
    
    return ConversationContext(
        session_id=session_id,
        history=history,
        created_at=datetime.now(),
        last_active_at=datetime.now()
    )


def assert_agent_response(response: AgentResponse, expected_text: str = None, expected_agent: str = None):
    """Assert agent response properties."""
    assert isinstance(response, AgentResponse)
    
    if expected_text:
        assert expected_text in response.response_text
    
    if expected_agent:
        assert response.metadata["agent"] == expected_agent


def assert_conversation_context(context: ConversationContext, expected_session_id: str, expected_history_length: int = None):
    """Assert conversation context properties."""
    assert context.session_id == expected_session_id
    
    if expected_history_length is not None:
        assert len(context.history) == expected_history_length
```

## Continuous Integration

### Test Configuration

Configure tests for CI/CD:

```python
"""Test configuration for CI/CD."""

import pytest
import os
from typing import List

# Test markers
pytest_plugins = ["pytest_asyncio"]


def pytest_configure(config):
    """Configure pytest for CI/CD."""
    # Add custom markers
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "component: Component tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "performance: Performance tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection for CI/CD."""
    # Skip integration tests if no API keys
    if not os.getenv("WEATHER_API_KEY"):
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="No API key available"))
    
    # Skip performance tests in CI
    if os.getenv("CI"):
        for item in items:
            if "performance" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Performance tests skipped in CI"))
```

### GitHub Actions Configuration

```yaml
# .github/workflows/test-agents.yml
name: Test Agents

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test-agents:
    runs-on: ubuntu-latest
    
    strategy:
      matrix:
        python-version: [3.11]
        test-type: [unit, component, integration]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -r services/requirements-dev.txt
        pip install pytest pytest-asyncio
    
    - name: Run unit tests
      if: matrix.test-type == 'unit'
      run: pytest -m unit --cov=services/orchestrator_enhanced/agents
    
    - name: Run component tests
      if: matrix.test-type == 'component'
      run: pytest -m component --cov=services/orchestrator_enhanced/agents
    
    - name: Run integration tests
      if: matrix.test-type == 'integration'
      env:
        WEATHER_API_KEY: ${{ secrets.WEATHER_API_KEY }}
        LLM_SERVICE_URL: http://localhost:8000
      run: pytest -m integration --cov=services/orchestrator_enhanced/agents
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

## Best Practices

### Testing Best Practices

1.  **Test Isolation:** Each test should be independent
2.  **Mock External Dependencies:** Use mocks for external services
3.  **Test Edge Cases:** Test error conditions and edge cases
4.  **Performance Testing:** Test against performance requirements
5.  **Documentation:** Document test cases and expected behavior

### Code Quality

1.  **Test Coverage:** Maintain high test coverage
2.  **Test Naming:** Use descriptive test names
3.  **Test Organization:** Organize tests logically
4.  **Test Data:** Use realistic test data
5.  **Test Maintenance:** Keep tests up to date

### Debugging

1.  **Logging:** Use structured logging in tests
2.  **Debugging Tools:** Use debugging tools when needed
3.  **Test Output:** Make test output clear and informative
4.  **Error Messages:** Provide helpful error messages
5.  **Test Reports:** Generate comprehensive test reports
