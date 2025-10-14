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
            import time

            import discord.errors

            from services.common.correlation import generate_correlation_id
            from services.common.logging import get_logger

            from .discord_voice import run_bot

            logger = get_logger(__name__, service_name="discord")
            correlation_id = generate_correlation_id()

            global _bot
            max_attempts = 3
            base_delay = 5.0

            for attempt in range(max_attempts):
                try:
                    logger.info(
                        "discord.bot_start_attempt",
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        correlation_id=correlation_id,
                    )
                    _bot = asyncio.run(run_bot(config))
                    logger.info(
                        "discord.bot_start_success",
                        attempt=attempt + 1,
                        correlation_id=correlation_id,
                    )
                    break
                except discord.errors.HTTPException as e:
                    if e.status == 429:  # Rate limited
                        retry_after = float(e.response.headers.get("retry-after", 60))
                        logger.warning(
                            "discord.rate_limited_retry",
                            attempt=attempt + 1,
                            max_attempts=max_attempts,
                            retry_after=retry_after,
                            correlation_id=correlation_id,
                        )
                        time.sleep(retry_after)
                    else:
                        logger.error(
                            "discord.http_error",
                            status=e.status,
                            error=str(e),
                            attempt=attempt + 1,
                            correlation_id=correlation_id,
                        )
                        if attempt == max_attempts - 1:
                            raise
                        time.sleep(base_delay * (2**attempt))
                except Exception as e:
                    logger.error(
                        "discord.startup_failed",
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        error=str(e),
                        error_type=type(e).__name__,
                        correlation_id=correlation_id,
                    )
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(base_delay * (2**attempt))

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
