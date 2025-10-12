"""Entrypoint for the Python Discord voice interface."""

from __future__ import annotations

import asyncio
import os

from services.common.logging import configure_logging

from .config import load_config


def main() -> None:
    config = load_config()
    configure_logging(
        config.telemetry.log_level,
        json_logs=config.telemetry.log_json,
        service_name="discord",
    )
    
    # Check running mode
    mcp_mode = os.getenv("DISCORD_MCP_MODE", "false").lower() == "true"
    http_mode = os.getenv("DISCORD_HTTP_MODE", "false").lower() == "true"
    full_bot_mode = os.getenv("DISCORD_FULL_BOT", "false").lower() == "true"
    
    if mcp_mode:
        # Run as MCP server subprocess
        from .mcp import MCPServer
        server = MCPServer(config)
        asyncio.run(server.serve())
    elif http_mode or full_bot_mode:
        # Run as HTTP API server (with optional full bot)
        from .app import app
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8001)
    else:
        # Run as full Discord bot only
        from .discord_voice import run_bot
        asyncio.run(run_bot(config))


if __name__ == "__main__":
    main()
