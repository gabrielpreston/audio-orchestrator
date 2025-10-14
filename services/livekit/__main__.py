"""LiveKit agent service entry point."""

import asyncio
import sys
from pathlib import Path

# Add common services to path
sys.path.insert(0, str(Path(__file__).parent.parent / "common"))

from .livekit_agent import main

if __name__ == "__main__":
    asyncio.run(main())
