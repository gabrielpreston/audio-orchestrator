"""Entrypoint for the Python Discord voice interface."""

from __future__ import annotations

import asyncio

from .config import load_config
from .discord_voice import run_bot


def main() -> None:
    config = load_config()
    asyncio.run(run_bot(config))


if __name__ == "__main__":
    main()
