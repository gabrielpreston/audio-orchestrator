"""MCP manager for orchestrating multiple MCP connections."""

from __future__ import annotations

# import asyncio  # Unused import
from typing import Any, Awaitable, Callable, Dict, List

from services.common.logging import get_logger

from .mcp_client import StdioMCPClient
from .mcp_config import MCPConfig


logger = get_logger(__name__, service_name="orchestrator")


class MCPManager:
    """Manages multiple MCP connections and aggregates their tools."""

    def __init__(self, config_path: str = "./mcp.json"):
        self.config = MCPConfig(config_path)
        self.clients: Dict[str, StdioMCPClient] = {}
        self._logger = get_logger(__name__, service_name="orchestrator")
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
        """Connect to Discord service via HTTP (no MCP subprocess needed)."""
        # Discord service runs as separate container, we'll communicate via HTTP
        # No need to spawn subprocess - Discord service handles its own MCP server
        self._logger.info("mcp.discord_http_mode", note="Discord runs as separate container")

        # Create HTTP-based Discord client for inter-container communication
        class HTTPDiscordClient:
            def __init__(self):
                self.name = "discord"
                self.is_connected = True
                self.base_url = "http://discord:8001"  # Discord service port
                self._http_client = None
                self._logger = get_logger(__name__, service_name="orchestrator")

            async def _get_http_client(self):
                """Get or create HTTP client."""
                if self._http_client is None:
                    import httpx

                    self._http_client = httpx.AsyncClient(timeout=30.0)
                return self._http_client

            async def list_tools(self) -> List[Dict[str, Any]]:
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
                            },
                            "required": ["guild_id", "channel_id", "audio_url"],
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

            async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
                """Call Discord tool via HTTP."""
                try:
                    client = await self._get_http_client()

                    if name == "discord.play_audio":
                        response = await client.post(
                            f"{self.base_url}/mcp/play_audio", json=arguments, timeout=30.0
                        )
                        response.raise_for_status()
                        return response.json()

                    elif name == "discord.send_message":
                        response = await client.post(
                            f"{self.base_url}/mcp/send_message", json=arguments, timeout=30.0
                        )
                        response.raise_for_status()
                        return response.json()

                    else:
                        return {"error": f"Unknown tool: {name}"}

                except Exception as exc:
                    self._logger.error(
                        "mcp.discord_http_tool_call_failed", tool=name, error=str(exc)
                    )
                    return {"error": str(exc)}

            async def disconnect(self) -> None:
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

        try:
            result = await client.call_tool(tool_name, arguments)
            self._logger.debug(
                "mcp.tool_call_success",
                client=client_name,
                tool=tool_name,
            )
            return result
        except Exception as exc:
            self._logger.error(
                "mcp.tool_call_failed",
                client=client_name,
                tool=tool_name,
                error=str(exc),
            )
            raise

    async def call_discord_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Convenience method to call Discord tools."""
        return await self.call_tool("discord", tool_name, arguments)

    def get_client_status(self) -> Dict[str, bool]:
        """Get connection status of all clients."""
        return {name: client.is_connected for name, client in self.clients.items()}


__all__ = ["MCPManager"]
