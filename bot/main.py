"""Main entry point for the audio orchestrator application."""

import asyncio
from .bootstrap import main


if __name__ == "__main__":
    asyncio.run(main())
