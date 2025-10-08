"""Manifest and MCP transport management."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import MCPConfig
from .logging import get_logger


@dataclass(slots=True)
class Manifest:
    """Represents a loaded MCP manifest."""

    name: str
    path: Path
    content: Dict[str, Any]


class MCPManager:
    """Loads manifests and maintains keepalive tasks for MCP transports."""

    def __init__(self, config: MCPConfig) -> None:
        self._config = config
        self._manifests: List[Manifest] = []
        self._logger = get_logger(__name__)
        self._keepalive_task: Optional[asyncio.Task[None]] = None
        self._shutdown = asyncio.Event()

    @property
    def manifests(self) -> List[Manifest]:
        return list(self._manifests)

    async def __aenter__(self) -> "MCPManager":
        self._manifests = self._load_manifests()
        self._keepalive_task = asyncio.create_task(self._keepalive())
        await self._register_if_needed()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self._shutdown.set()
        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass

    def _load_manifests(self) -> List[Manifest]:
        manifests: List[Manifest] = []
        for path in self._config.manifest_paths:
            try:
                with path.open("r", encoding="utf-8") as handle:
                    content = json.load(handle)
                name = content.get("name") or path.stem
                manifests.append(Manifest(name=name, path=path, content=content))
                self._logger.info(
                    "mcp.manifest_loaded",
                    extra={"manifest": name, "path": str(path)},
                )
            except FileNotFoundError:
                self._logger.warning(
                    "mcp.manifest_missing",
                    extra={"path": str(path)},
                )
            except json.JSONDecodeError as exc:
                self._logger.error(
                    "mcp.manifest_invalid",
                    extra={"path": str(path), "error": str(exc)},
                )
        return manifests

    async def _register_if_needed(self) -> None:
        if not self._config.registration_url:
            return
        if not self._manifests:
            return
        await asyncio.sleep(0)
        self._logger.info(
            "mcp.registration_stub",
            extra={
                "registration_url": self._config.registration_url,
                "manifest_count": len(self._manifests),
            },
        )

    async def _keepalive(self) -> None:
        if not self._config.websocket_url and not self._config.command_path:
            return
        interval = max(self._config.heartbeat_interval_seconds, 5.0)
        while not self._shutdown.is_set():
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            self._logger.debug(
                "mcp.heartbeat",
                extra={
                    "websocket": self._config.websocket_url,
                    "command": str(self._config.command_path) if self._config.command_path else None,
                },
            )


__all__ = ["MCPManager", "Manifest"]
