"""Mock MCP client for testing."""

from collections.abc import Callable
from typing import Any


class MockMCPClient:
    """Mock MCP client for testing."""

    def __init__(self):
        self._tools = {}
        self._tool_calls = []
        self._is_connected = False
        self._connection_url = None
        self._auth_token = None

    def set_tool_response(self, tool_name: str, response: dict[str, Any]) -> None:
        """Set a response for a specific tool.

        Args:
            tool_name: Name of the tool
            response: Response to return
        """
        self._tools[tool_name] = response

    def get_tool_calls(self) -> list[dict[str, Any]]:
        """Get all tool calls."""
        return self._tool_calls.copy()

    def clear_tool_calls(self) -> None:
        """Clear recorded tool calls."""
        self._tool_calls.clear()

    async def connect(self, url: str, auth_token: str | None = None) -> None:
        """Mock connect method."""
        self._connection_url = url
        self._auth_token = auth_token
        self._is_connected = True

    async def disconnect(self) -> None:
        """Mock disconnect method."""
        self._is_connected = False
        self._connection_url = None
        self._auth_token = None

    async def call_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Mock call_tool method."""
        call_data = {
            "tool_name": tool_name,
            "parameters": parameters,
            "correlation_id": correlation_id,
        }
        self._tool_calls.append(call_data)

        if tool_name in self._tools:
            response = self._tools[tool_name].copy()
            if correlation_id:
                response["correlation_id"] = correlation_id
            return response

        # Default response
        return {
            "success": True,
            "result": f"Mock result for {tool_name}",
            "correlation_id": correlation_id,
        }

    async def list_tools(self) -> list[dict[str, Any]]:
        """Mock list_tools method."""
        return [
            {
                "name": "weather_check",
                "description": "Check the weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "Location to check weather for",
                        },
                        "date": {
                            "type": "string",
                            "description": "Date to check weather for",
                        },
                    },
                    "required": ["location"],
                },
            },
            {
                "name": "send_message",
                "description": "Send a message to a Discord channel",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "Discord channel ID",
                        },
                        "content": {"type": "string", "description": "Message content"},
                    },
                    "required": ["channel_id", "content"],
                },
            },
        ]

    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._is_connected


class MockMCPTool:
    """Mock MCP tool for testing."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., Any] | None = None,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler
        self._calls: list[dict[str, Any]] = []

    def get_calls(self) -> list[dict[str, Any]]:
        """Get all calls to this tool."""
        return self._calls.copy()

    def clear_calls(self) -> None:
        """Clear recorded calls."""
        self._calls.clear()

    async def call(
        self, parameters: dict[str, Any], correlation_id: str | None = None
    ) -> dict[str, Any]:
        """Call the tool."""
        call_data = {"parameters": parameters, "correlation_id": correlation_id}
        self._calls.append(call_data)

        if self.handler:
            return await self.handler(parameters, correlation_id)
        else:
            # Default response
            return {
                "success": True,
                "result": f"Mock result for {self.name}",
                "correlation_id": correlation_id,
            }


def create_mock_mcp_client() -> MockMCPClient:
    """Create a mock MCP client for testing.

    Returns:
        Mock MCP client
    """
    return MockMCPClient()


def create_mock_mcp_tool(
    name: str,
    description: str,
    parameters: dict[str, Any],
    handler: Callable[..., Any] | None = None,
) -> MockMCPTool:
    """Create a mock MCP tool for testing.

    Args:
        name: Tool name
        description: Tool description
        parameters: Tool parameters schema
        handler: Optional handler function

    Returns:
        Mock MCP tool
    """
    return MockMCPTool(name, description, parameters, handler)


def create_mock_weather_tool() -> MockMCPTool:
    """Create a mock weather tool for testing.

    Returns:
        Mock weather tool
    """
    parameters = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "Location to check weather for",
            },
            "date": {"type": "string", "description": "Date to check weather for"},
        },
        "required": ["location"],
    }

    async def weather_handler(
        parameters: dict[str, Any], correlation_id: str | None = None
    ) -> dict[str, Any]:
        """Mock weather handler."""
        location = parameters.get("location", "Unknown")
        date = parameters.get("date", "today")

        return {
            "success": True,
            "result": {
                "location": location,
                "date": date,
                "weather": "sunny",
                "temperature": "75°F",
                "humidity": "60%",
                "wind": "5 mph",
            },
            "correlation_id": correlation_id,
        }

    return create_mock_mcp_tool(
        "weather_check", "Check the weather for a location", parameters, weather_handler
    )


def create_mock_discord_tool() -> MockMCPTool:
    """Create a mock Discord tool for testing.

    Returns:
        Mock Discord tool
    """
    parameters = {
        "type": "object",
        "properties": {
            "channel_id": {"type": "string", "description": "Discord channel ID"},
            "content": {"type": "string", "description": "Message content"},
        },
        "required": ["channel_id", "content"],
    }

    async def discord_handler(
        parameters: dict[str, Any], correlation_id: str | None = None
    ) -> dict[str, Any]:
        """Mock Discord handler."""
        channel_id = parameters.get("channel_id")
        content = parameters.get("content", "")

        return {
            "success": True,
            "result": {
                "channel_id": channel_id,
                "message_id": "123456789012345678",
                "content": content,
                "timestamp": "2024-01-01T12:00:00Z",
            },
            "correlation_id": correlation_id,
        }

    return create_mock_mcp_tool(
        "send_message",
        "Send a message to a Discord channel",
        parameters,
        discord_handler,
    )


def create_mock_voice_tool() -> MockMCPTool:
    """Create a mock voice tool for testing.

    Returns:
        Mock voice tool
    """
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["join", "leave", "mute", "unmute"],
                "description": "Voice action to perform",
            },
            "channel_id": {"type": "string", "description": "Voice channel ID"},
        },
        "required": ["action", "channel_id"],
    }

    async def voice_handler(
        parameters: dict[str, Any], correlation_id: str | None = None
    ) -> dict[str, Any]:
        """Mock voice handler."""
        action = parameters.get("action")
        channel_id = parameters.get("channel_id")

        return {
            "success": True,
            "result": {"action": action, "channel_id": channel_id, "status": "success"},
            "correlation_id": correlation_id,
        }

    return create_mock_mcp_tool(
        "voice_control", "Control voice channel operations", parameters, voice_handler
    )
