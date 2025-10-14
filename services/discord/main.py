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

    # Check for MCP mode (subprocess mode)
    mcp_mode = os.getenv("DISCORD_MCP_MODE", "false").lower() == "true"

    if mcp_mode:
        # Run as MCP server subprocess
        from .mcp import MCPServer

        server = MCPServer(config)
        asyncio.run(server.serve())
    else:
        # Default: Run as HTTP API server with full bot capabilities
        import threading
        import time

        import uvicorn

        from .app import _bot, app

        # Start the full bot in a separate thread
        def run_bot_thread():
            from .discord_voice import run_bot

            global _bot
            _bot = asyncio.run(run_bot(config))

        # Start the full bot in a separate thread
        bot_thread = threading.Thread(target=run_bot_thread, daemon=True)
        bot_thread.start()

        # Wait for bot to be ready
        while _bot is None:
            time.sleep(0.1)

        # Start the HTTP server
        uvicorn.run(app, host="0.0.0.0", port=8001)


if __name__ == "__main__":
    main()
