"""Entrypoint for the Python Discord voice interface."""

from __future__ import annotations

import asyncio

from services.common.logging import configure_logging

from .config import load_config


def main() -> None:
    config = load_config()
    configure_logging(
        config.telemetry.log_level,
        json_logs=config.telemetry.log_json,
        service_name="discord",
    )
    from .discord_voice import run_bot  # Local import so logging is configured first

    asyncio.run(run_bot(config))


if __name__ == "__main__":
    main()
