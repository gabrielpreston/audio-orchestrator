"""MCP client implementation using the official MCP Python SDK."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from services.common.logging import get_logger

logger = get_logger(__name__, service_name="orchestrator")


class StdioMCPClient:
    """MCP client that connects to a subprocess via stdio using the official SDK."""

    def __init__(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self._session: ClientSession | None = None
        self._client = None
        self._logger = get_logger(__name__, service_name="orchestrator")
        self._notification_handlers: list[
            Callable[[str, dict[str, Any]], Awaitable[None]]
        ] = []

    async def connect(self) -> None:
        """Connect to the MCP server subprocess."""
        try:
            # Ensure PYTHONPATH is set for the subprocess
            env = self.env.copy()
            env.setdefault("PYTHONPATH", "/app")

            server_params = StdioServerParameters(
                command=self.command,
                args=self.args,
                env=env,
            )

            self._client = stdio_client(server_params)
            if self._client is None:
                raise RuntimeError("Failed to create stdio client")

            # Enter the context manager and get the streams
            read_stream, write_stream = await self._client.__aenter__()

            # Create a session from the streams
            from mcp import ClientSession

            self._session = ClientSession(read_stream, write_stream)

            # Initialize the session
            await self._session.initialize()

            self._logger.info(
                "mcp.client_connected",
                name=self.name,
                command=f"{self.command} {' '.join(self.args)}",
            )

            # Start listening for notifications
            _notification_task = asyncio.create_task(self._listen_for_notifications())
            # Store reference to prevent garbage collection

        except Exception as exc:
            self._logger.error(
                "mcp.client_connection_failed",
                name=self.name,
                error=str(exc),
            )
            raise

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
                self._logger.info("mcp.client_disconnected", name=self.name)
            except Exception as exc:
                self._logger.error(
                    "mcp.client_disconnect_failed",
                    name=self.name,
                    error=str(exc),
                )
            finally:
                self._session = None
                self._client = None

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools from the MCP server."""
        if not self._session:
            raise RuntimeError("Not connected to MCP server")

        try:
            result = await self._session.list_tools()
            tools = result.tools
            self._logger.debug(
                "mcp.tools_listed",
                name=self.name,
                tool_count=len(tools),
            )
            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                }
                for tool in tools
            ]
        except Exception as exc:
            self._logger.error(
                "mcp.list_tools_failed",
                name=self.name,
                error=str(exc),
            )
            raise

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the MCP server."""
        if not self._session:
            raise RuntimeError("Not connected to MCP server")

        try:
            result = await self._session.call_tool(name, arguments)
            self._logger.debug(
                "mcp.tool_called",
                name=self.name,
                tool_name=name,
                success=True,
            )
            return dict(result.content[0].json) if result.content else {}
        except Exception as exc:
            self._logger.error(
                "mcp.tool_call_failed",
                name=self.name,
                tool_name=name,
                error=str(exc),
            )
            raise

    def subscribe_notifications(
        self, handler: Callable[[str, dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Subscribe to MCP notifications."""
        self._notification_handlers.append(handler)
        self._logger.debug(
            "mcp.notification_subscribed",
            name=self.name,
            handler_count=len(self._notification_handlers),
        )

    async def _listen_for_notifications(self) -> None:
        """Background task to listen for notifications from the MCP server."""
        if not self._session:
            return

        try:
            # The MCP SDK handles notification listening internally
            # We need to implement a custom notification handler
            # For now, we'll use a polling approach or implement custom notification handling
            self._logger.debug("mcp.notification_listener_started", name=self.name)

            # Note: The official MCP SDK may not expose direct notification handling
            # We may need to implement this differently or use the server's notification system
            # This is a placeholder for the notification handling mechanism

        except Exception as exc:
            self._logger.error(
                "mcp.notification_listener_failed",
                name=self.name,
                error=str(exc),
            )

    async def _handle_notification(self, method: str, params: dict[str, Any]) -> None:
        """Handle incoming notifications."""
        for handler in self._notification_handlers:
            try:
                await handler(method, params)
            except Exception as exc:
                self._logger.error(
                    "mcp.notification_handler_failed",
                    name=self.name,
                    method=method,
                    error=str(exc),
                )

    @property
    def is_connected(self) -> bool:
        """Check if the client is connected."""
        return self._session is not None and self._client is not None


__all__ = ["StdioMCPClient"]
