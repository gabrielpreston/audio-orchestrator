"""Entrypoint for the Python Discord voice bot."""

from __future__ import annotations

import asyncio

from .config import load_config
from .discord_voice import run_bot
from .logging import configure_logging


def main() -> None:
    config = load_config()
    configure_logging(config.telemetry.log_level, config.telemetry.log_json)
    asyncio.run(run_bot(config))


if __name__ == "__main__":
    main()
