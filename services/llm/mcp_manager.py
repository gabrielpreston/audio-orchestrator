"""MCP manager for orchestrating multiple MCP connections."""

from __future__ import annotations

# import asyncio  # Unused import
from typing import Any, Awaitable, Callable, Dict, List

from services.common.logging import get_logger

from .mcp_client import StdioMCPClient
from .mcp_config import MCPConfig

logger = get_logger(__name__, service_name="llm")


class MCPManager:
    """Manages multiple MCP connections and aggregates their tools."""

    def __init__(self, config_path: str = "./mcp.json"):
        self.config = MCPConfig(config_path)
        self.clients: Dict[str, StdioMCPClient] = {}
        self._logger = get_logger(__name__, service_name="llm")
        self._notification_handlers: List[Callable[[str, str, Dict[str, Any]], Awaitable[None]]] = (
            []
        )

    async def initialize(self) -> None:
        """Initialize the MCP manager and connect to all configured servers."""
        self.config.load()

        # Connect to Discord service first (required)
        await self._connect_discord()

        # Connect to external MCP servers from mcp.json
        await self._connect_external_servers()

        self._logger.info(
            "mcp.manager_initialized",
            client_count=len(self.clients),
            clients=list(self.clients.keys()),
        )

    async def shutdown(self) -> None:
        """Shutdown all MCP connections."""
        for name, client in self.clients.items():
            try:
                await client.disconnect()
                self._logger.info("mcp.client_shutdown", name=name)
            except Exception as exc:
                self._logger.error(
                    "mcp.client_shutdown_failed",
                    name=name,
                    error=str(exc),
                )

        self.clients.clear()
        self._logger.info("mcp.manager_shutdown")

    async def _connect_discord(self) -> None:
        """Connect to Discord service via HTTP."""
        # Discord service runs as full bot with HTTP server in its own container
        self._logger.info(
            "mcp.discord_http_mode",
            note="Discord runs as full bot with HTTP server in separate container",
        )

        # Use HTTP client directly since Discord service supports HTTP by default
        await self._connect_discord_http_fallback()

    async def _connect_discord_http_fallback(self) -> None:
        """Fallback to HTTP-based Discord client."""

        # Create HTTP-based Discord client for inter-container communication
        class HTTPDiscordClient:
            def __init__(self):
                self.name = "discord"
                self.is_connected = True
                self.base_url = "http://discord:8001"  # Discord service port
                self._http_client = None
                self._logger = get_logger(__name__, service_name="llm")

            async def _get_http_client(self):
                """Get or create HTTP client."""
                if self._http_client is None:
                    import httpx

                    self._http_client = httpx.AsyncClient(timeout=30.0)
                return self._http_client

            async def list_tools(self):
                """Return Discord MCP tools that can be called via HTTP."""
                return [
                    {
                        "name": "discord.play_audio",
                        "description": "Play audio in Discord voice channel",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "guild_id": {"type": "string"},
                                "channel_id": {"type": "string"},
                                "audio_url": {"type": "string"},
                                "audio_data": {
                                    "type": "string",
                                    "description": "Base64 encoded audio data",
                                },
                            },
                            "required": ["guild_id", "channel_id"],
                        },
                    },
                    {
                        "name": "discord.send_message",
                        "description": "Send a text message to Discord channel",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "guild_id": {"type": "string"},
                                "channel_id": {"type": "string"},
                                "message": {"type": "string"},
                            },
                            "required": ["guild_id", "channel_id", "message"],
                        },
                    },
                ]

            async def call_tool(self, name, arguments):
                """Call Discord tool via HTTP."""
                try:
                    client = await self._get_http_client()

                    # Add detailed logging for MCP tool calls
                    self._logger.info(
                        "mcp.discord_tool_call_attempt",
                        tool=name,
                        arguments=arguments,
                        has_audio_data="audio_data" in arguments,
                        has_audio_url="audio_url" in arguments,
                    )

                    if name == "discord.play_audio":
                        import os

                        from services.common.retry import post_with_discord_retry

                        # Get retry configuration from environment
                        max_attempts = max(1, int(os.getenv("MCP_DISCORD_RETRY_MAX_ATTEMPTS", "3")))
                        max_delay = float(os.getenv("MCP_DISCORD_RETRY_MAX_DELAY", "15.0"))
                        base_delay = float(os.getenv("MCP_DISCORD_RETRY_BASE_DELAY", "1.0"))
                        jitter = os.getenv("MCP_DISCORD_RETRY_JITTER", "true").lower() == "true"

                        response = await post_with_discord_retry(
                            client,
                            f"{self.base_url}/mcp/play_audio",
                            json=arguments,
                            timeout=30.0,
                            max_attempts=max_attempts,
                            max_delay=max_delay,
                            base_delay=base_delay,
                            jitter=jitter,
                        )
                        result = response.json()

                        self._logger.info(
                            "mcp.discord_play_audio_success",
                            tool=name,
                            status_code=response.status_code,
                            result=result,
                        )
                        return result

                    elif name == "discord.send_message":
                        import os

                        from services.common.retry import post_with_discord_retry

                        # Get retry configuration from environment
                        max_attempts = max(1, int(os.getenv("MCP_DISCORD_RETRY_MAX_ATTEMPTS", "3")))
                        max_delay = float(os.getenv("MCP_DISCORD_RETRY_MAX_DELAY", "15.0"))
                        base_delay = float(os.getenv("MCP_DISCORD_RETRY_BASE_DELAY", "1.0"))
                        jitter = os.getenv("MCP_DISCORD_RETRY_JITTER", "true").lower() == "true"

                        response = await post_with_discord_retry(
                            client,
                            f"{self.base_url}/mcp/send_message",
                            json=arguments,
                            timeout=30.0,
                            max_attempts=max_attempts,
                            max_delay=max_delay,
                            base_delay=base_delay,
                            jitter=jitter,
                        )
                        result = response.json()

                        self._logger.info(
                            "mcp.discord_send_message_success",
                            tool=name,
                            status_code=response.status_code,
                            result=result,
                        )
                        return result

                    else:
                        self._logger.warning(
                            "mcp.discord_unknown_tool",
                            tool=name,
                            available_tools=["discord.play_audio", "discord.send_message"],
                        )
                        return {"error": f"Unknown tool: {name}"}

                except Exception as exc:
                    self._logger.error(
                        "mcp.discord_http_tool_call_failed",
                        tool=name,
                        error=str(exc),
                        arguments=arguments,
                    )
                    return {"error": str(exc)}

            async def disconnect(self):
                """Clean up HTTP client."""
                if self._http_client:
                    await self._http_client.aclose()
                    self._http_client = None

        client = HTTPDiscordClient()
        self.clients["discord"] = client  # type: ignore
        self._logger.info("mcp.discord_http_client_created")

    async def _connect_external_servers(self) -> None:
        """Connect to external MCP servers from mcp.json."""
        enabled_servers = self.config.get_enabled_servers()

        for name, server_config in enabled_servers.items():
            if name == "discord":
                continue  # Already connected

            try:
                # Pass command and args separately
                client = StdioMCPClient(
                    name=name,
                    command=server_config.command,
                    args=server_config.args,
                    env=server_config.env,
                )

                await client.connect()
                self.clients[name] = client

                self._logger.info(
                    "mcp.external_server_connected",
                    name=name,
                    command=server_config.command,
                )

            except Exception as exc:
                self._logger.error(
                    "mcp.external_server_connection_failed",
                    name=name,
                    error=str(exc),
                )
                # Continue with other servers even if one fails

    async def _handle_discord_notification(self, method: str, params: Dict[str, Any]) -> None:
        """Handle notifications from Discord service."""
        self._logger.debug(
            "mcp.discord_notification_received",
            method=method,
            params=params,
        )

        # Forward to registered handlers
        for handler in self._notification_handlers:
            try:
                await handler("discord", method, params)
            except Exception as exc:
                self._logger.error(
                    "mcp.notification_handler_failed",
                    handler=handler.__name__,
                    error=str(exc),
                )

    def subscribe_notifications(
        self, handler: Callable[[str, str, Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Subscribe to notifications from any MCP client."""
        self._notification_handlers.append(handler)
        self._logger.debug(
            "mcp.notification_subscribed",
            handler_count=len(self._notification_handlers),
        )

    async def list_all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """List all available tools from all connected clients."""
        all_tools = {}

        for name, client in self.clients.items():
            if not client.is_connected:
                continue

            try:
                tools = await client.list_tools()
                all_tools[name] = tools
                self._logger.debug(
                    "mcp.tools_retrieved",
                    client=name,
                    tool_count=len(tools),
                )
            except Exception as exc:
                self._logger.error(
                    "mcp.tools_retrieval_failed",
                    client=name,
                    error=str(exc),
                )
                all_tools[name] = []

        return all_tools

    async def call_tool(
        self, client_name: str, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool on a specific MCP client."""
        client = self.clients.get(client_name)
        if not client:
            raise ValueError(f"Unknown MCP client: {client_name}")

        if not client.is_connected:
            raise RuntimeError(f"MCP client {client_name} is not connected")

        # Add detailed logging for MCP tool calls
        self._logger.info(
            "mcp.tool_call_attempt",
            client=client_name,
            tool=tool_name,
            arguments=arguments,
        )

        try:
            result = await client.call_tool(tool_name, arguments)
            self._logger.info(
                "mcp.tool_call_success",
                client=client_name,
                tool=tool_name,
                result=result,
            )
            return result
        except Exception as exc:
            self._logger.error(
                "mcp.tool_call_failed",
                client=client_name,
                tool=tool_name,
                error=str(exc),
                arguments=arguments,
            )
            raise

    async def call_discord_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Convenience method to call Discord tools."""
        return await self.call_tool("discord", tool_name, arguments)

    def get_client_status(self) -> Dict[str, bool]:
        """Get connection status of all clients."""
        return {name: client.is_connected for name, client in self.clients.items()}


__all__ = ["MCPManager"]
