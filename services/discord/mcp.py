"""Minimal MCP server implementation for the Discord voice bot."""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, TYPE_CHECKING

from services.common.logging import get_logger

from .config import BotConfig

if TYPE_CHECKING:  # pragma: no cover - runtime only
    from .discord_voice import VoiceBot


ToolHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


@dataclass(slots=True)
class ToolDefinition:
    """Describes an exposed MCP tool."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: ToolHandler


class MCPServer:
    """JSON-RPC MCP server that exposes Discord capabilities."""

    def __init__(self, config: BotConfig) -> None:
        self._config = config
        self._logger = get_logger(__name__, service_name="discord")
        self._voice_bot: Optional["VoiceBot"] = None
        self._tools: Dict[str, ToolDefinition] = {}
        self._incoming: "asyncio.Queue[Optional[Dict[str, Any]]]" = asyncio.Queue()
        self._shutdown = asyncio.Event()
        self._writer_lock = asyncio.Lock()
        self._reader_task: Optional[asyncio.Task[None]] = None
        self._initialized = False
        self._pending_notifications: List[Dict[str, Any]] = []
        self._register_default_tools()

    def attach_voice_bot(self, voice_bot: "VoiceBot") -> None:
        """Attach the running Discord client used to service tool calls."""

        self._voice_bot = voice_bot

    async def shutdown(self) -> None:
        """Stop serving new MCP requests and tear down background tasks."""

        if self._shutdown.is_set():
            return
        self._shutdown.set()
        self._incoming.put_nowait(None)
        if self._reader_task:
            self._reader_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._reader_task

    async def serve(self) -> None:
        """Serve MCP requests over stdio until shutdown."""

        self._reader_task = asyncio.create_task(self._pump_stdin())
        try:
            while True:
                message = await self._incoming.get()
                if message is None:
                    if self._shutdown.is_set():
                        break
                    continue
                await self._handle_message(message)
        finally:
            self._shutdown.set()
            if self._reader_task:
                self._reader_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._reader_task

    async def publish_transcript(self, payload: Dict[str, object]) -> None:
        """Send a transcript notification to connected MCP clients."""

        if self._shutdown.is_set():
            return
        message: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": "discord/transcript",
            "params": payload,
        }
        if not self._initialized:
            self._pending_notifications.append(message)
            self._logger.info(
                "mcp.transcript_buffered",
                correlation_id=payload.get("correlation_id"),
                reason="not_initialized",
            )
            return
        await self._send(message)
        self._logger.info(
            "mcp.transcript_sent",
            correlation_id=payload.get("correlation_id"),
            text_length=len(str(payload.get("text", ""))),
        )

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        if "method" not in message:
            self._logger.debug("mcp.ignored_message", message=message)
            return
        if "id" not in message:
            self._logger.debug(
                "mcp.notification_ignored",
                method=message.get("method"),
            )
            return
        await self._handle_request(message)

    async def _handle_request(self, request: Dict[str, Any]) -> None:
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})
        try:
            if method in {"initialize", "mcp/initialize"}:
                await self._handle_initialize(request_id)
            elif method in {"tools/list", "mcp/tools/list"}:
                await self._handle_list_tools(request_id)
            elif method in {"tools/call", "mcp/tools/call"}:
                await self._handle_call_tool(request_id, params)
            elif method == "ping":
                await self._send_response(request_id, {"ok": True})
            else:
                await self._send_error(
                    request_id,
                    -32601,
                    f"Method {method!r} not found",
                )
        except ValueError as exc:
            await self._send_error(request_id, -32602, str(exc))
        except Exception as exc:  # noqa: BLE001
            self._logger.exception(
                "mcp.request_failed",
                method=method,
                request_id=request_id,
            )
            await self._send_error(request_id, -32000, "Server error", {"error": str(exc)})

    async def _handle_initialize(self, request_id: Any) -> None:
        self._initialized = True
        result = {
            "protocolVersion": "1.0",
            "server": {"name": "discord.voice-interface", "version": "0.1.0"},
            "capabilities": {
                "tools": {"listChanged": True},
                "notifications": {"subscriptions": ["discord/transcript"]},
            },
            "discord": {
                "defaultGuildId": self._config.discord.guild_id,
                "defaultVoiceChannelId": self._config.discord.voice_channel_id,
            },
        }
        await self._send_response(request_id, result)
        if self._pending_notifications:
            buffered = list(self._pending_notifications)
            self._pending_notifications.clear()
            for notification in buffered:
                await self._send(notification)

    async def _handle_list_tools(self, request_id: Any) -> None:
        tools = [
            {
                "name": definition.name,
                "description": definition.description,
                "inputSchema": definition.input_schema,
            }
            for definition in self._tools.values()
        ]
        await self._send_response(request_id, {"tools": tools})

    async def _handle_call_tool(self, request_id: Any, params: Dict[str, Any]) -> None:
        name = params.get("name")
        if not isinstance(name, str):
            raise ValueError("Tool name must be a string")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be an object")
        definition = self._tools.get(name)
        if not definition:
            raise ValueError(f"Unknown tool: {name}")
        result = await definition.handler(arguments)
        await self._send_response(
            request_id,
            {
                "content": [
                    {
                        "type": "application/json",
                        "json": result,
                    }
                ]
            },
        )

    def _register_default_tools(self) -> None:
        self._tools = {
            "discord.join_voice": ToolDefinition(
                name="discord.join_voice",
                description="Connect the bot to the provided guild voice channel.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "guild_id": {"type": "integer"},
                        "channel_id": {"type": "integer"},
                    },
                    "required": ["guild_id", "channel_id"],
                },
                handler=self._tool_join_voice,
            ),
            "discord.leave_voice": ToolDefinition(
                name="discord.leave_voice",
                description="Disconnect the bot from the specified guild voice channel.",
                input_schema={
                    "type": "object",
                    "properties": {"guild_id": {"type": "integer"}},
                    "required": ["guild_id"],
                },
                handler=self._tool_leave_voice,
            ),
            "discord.send_message": ToolDefinition(
                name="discord.send_message",
                description="Send a message into a Discord text channel.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "channel_id": {"type": "integer"},
                        "content": {"type": "string"},
                    },
                    "required": ["channel_id", "content"],
                },
                handler=self._tool_send_message,
            ),
            "discord.play_audio": ToolDefinition(
                name="discord.play_audio",
                description="Play an audio URL inside a connected voice channel.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "guild_id": {"type": "integer"},
                        "channel_id": {"type": "integer"},
                        "audio_url": {"type": "string"},
                    },
                    "required": ["guild_id", "channel_id", "audio_url"],
                },
                handler=self._tool_play_audio,
            ),
        }

    def _require_voice_bot(self) -> "VoiceBot":
        if not self._voice_bot:
            raise RuntimeError("Voice bot not attached")
        return self._voice_bot

    @staticmethod
    def _require_int(arguments: Dict[str, Any], name: str) -> int:
        if name not in arguments:
            raise ValueError(f"Missing required argument: {name}")
        value = arguments[name]
        try:
            return int(value)
        except (TypeError, ValueError) as exc:  # noqa: F841
            raise ValueError(f"Argument {name} must be an integer") from None

    @staticmethod
    def _require_str(arguments: Dict[str, Any], name: str) -> str:
        if name not in arguments:
            raise ValueError(f"Missing required argument: {name}")
        value = arguments[name]
        if not isinstance(value, str):
            raise ValueError(f"Argument {name} must be a string")
        return value

    async def _tool_join_voice(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        guild_id = self._require_int(arguments, "guild_id")
        channel_id = self._require_int(arguments, "channel_id")
        bot = self._require_voice_bot()
        return await bot.join_voice_channel(guild_id, channel_id)

    async def _tool_leave_voice(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        guild_id = self._require_int(arguments, "guild_id")
        bot = self._require_voice_bot()
        return await bot.leave_voice_channel(guild_id)

    async def _tool_send_message(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        channel_id = self._require_int(arguments, "channel_id")
        content = self._require_str(arguments, "content")
        bot = self._require_voice_bot()
        return await bot.send_text_message(channel_id, content)

    async def _tool_play_audio(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        guild_id = self._require_int(arguments, "guild_id")
        channel_id = self._require_int(arguments, "channel_id")
        audio_url = self._require_str(arguments, "audio_url")
        bot = self._require_voice_bot()
        return await bot.play_audio_from_url(guild_id, channel_id, audio_url)

    async def _pump_stdin(self) -> None:
        loop = asyncio.get_running_loop()

        def reader() -> None:
            for raw in sys.stdin:
                if self._shutdown.is_set():
                    break
                text = raw.strip()
                if not text:
                    continue
                try:
                    message = json.loads(text)
                except json.JSONDecodeError as exc:  # noqa: PERF203
                    self._logger.error(
                        "mcp.invalid_message",
                        error=str(exc),
                        payload=text,
                    )
                    continue
                loop.call_soon_threadsafe(self._incoming.put_nowait, message)
            if not self._shutdown.is_set():
                self._logger.debug("mcp.stdin_closed")

        await asyncio.to_thread(reader)

    async def _send(self, message: Dict[str, Any]) -> None:
        data = json.dumps(message, separators=(",", ":"))
        async with self._writer_lock:
            await asyncio.to_thread(self._write_line, data)

    async def _send_response(self, request_id: Any, result: Any) -> None:
        await self._send({"jsonrpc": "2.0", "id": request_id, "result": result})

    async def _send_error(self, request_id: Any, code: int, message: str, data: Any = None) -> None:
        payload: Dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
        if data is not None:
            payload["error"]["data"] = data
        await self._send(payload)

    @staticmethod
    def _write_line(data: str) -> None:
        sys.stdout.write(f"{data}\n")
        sys.stdout.flush()


__all__ = ["MCPServer", "ToolDefinition", "ToolHandler"]
