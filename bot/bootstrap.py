"""Bootstrap module for loading configuration and starting the orchestrator."""

import asyncio
import logging
from typing import Optional

from config.settings import Settings
from io_adapters import get_input_adapter, get_output_adapter
from audio_pipeline.types import ConversationContext


# Configure structured logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point for the audio orchestrator."""
    try:
        # Load configuration
        settings = Settings()
        logger.info("Configuration loaded successfully")

        # Set up logging level from config
        logging.getLogger().setLevel(getattr(logging, settings.log_level.upper()))

        # Get adapters from registry
        input_adapter_class = get_input_adapter(settings.default_adapter)
        output_adapter_class = get_output_adapter(settings.default_adapter)

        if not input_adapter_class or not output_adapter_class:
            logger.error(f"Adapters not found for: {settings.default_adapter}")
            return

        # Instantiate adapters
        input_adapter = input_adapter_class()
        output_adapter = output_adapter_class()

        logger.info(f"Using adapters: {settings.default_adapter}")

        # TODO: Initialize orchestrator engine
        # TODO: Set up agent manager
        # TODO: Configure STT/TTS services

        # Start input adapter
        await input_adapter.start()
        logger.info("Input adapter started")

        # TODO: Run main audio handling loop
        # This would typically be:
        # async for chunk in input_adapter.get_audio_stream():
        #     # Process audio through pipeline
        #     # Route to appropriate agent
        #     # Generate response
        #     # Play response audio

        logger.info("Audio orchestrator started successfully")

        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            await input_adapter.stop()
            logger.info("Input adapter stopped")

    except Exception as e:
        logger.error(f"Failed to start audio orchestrator: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
