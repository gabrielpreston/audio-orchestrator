"""
MediaGateway integration for Discord adapters.

This module provides integration between the MediaGateway and Discord adapters,
enabling codec normalization and audio processing in the Discord voice pipeline.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from services.common.surfaces.audio_contract import AudioContract
from services.common.surfaces.media_gateway import MediaGateway
from services.common.surfaces.types import AudioFormat, PCMFrame

from .discord_sink import DiscordAudioSink
from .discord_source import DiscordAudioSource

logger = logging.getLogger(__name__)


class DiscordMediaGatewayIntegration:
    """
    Integration between MediaGateway and Discord adapters.

    This class manages the deployment of MediaGateway in Discord adapters,
    providing codec normalization, audio processing, and format conversion
    for the Discord voice pipeline.
    """

    def __init__(self, audio_source: DiscordAudioSource, audio_sink: DiscordAudioSink):
        """
        Initialize Discord MediaGateway integration.

        Args:
            audio_source: Discord audio source adapter
            audio_sink: Discord audio sink adapter
        """
        self.audio_source = audio_source
        self.audio_sink = audio_sink

        # MediaGateway components
        self._media_gateway: MediaGateway | None = None
        self._audio_contract: AudioContract | None = None

        # Integration state
        self._is_initialized = False
        self._is_connected = False
        self._processing_tasks: list[asyncio.Task[None]] = []

        # Event handlers
        self._event_handlers: dict[str, list[Callable[..., Any]]] = {}

        # Configuration
        self._canonical_format = AudioFormat(
            value={
                "sample_rate": 16000,
                "channels": 1,
                "bit_depth": 16,
                "frame_size_ms": 20,
            }
        )
        self._enable_codec_conversion = True
        self._enable_audio_normalization = True
        self._enable_drift_correction = True

    async def initialize(self) -> bool:
        """
        Initialize the MediaGateway integration.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing Discord MediaGateway integration")

            # Initialize MediaGateway
            self._media_gateway = MediaGateway()

            # Initialize AudioContract
            self._audio_contract = AudioContract()

            # Set up event routing
            await self._setup_event_routing()

            self._is_initialized = True
            logger.info("Discord MediaGateway integration initialized successfully")
            return True

        except Exception as e:
            logger.error("Failed to initialize Discord MediaGateway integration: %s", e)
            return False

    async def connect(self) -> bool:
        """
        Connect the MediaGateway integration.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._is_initialized:
            logger.error("Integration not initialized")
            return False

        try:
            logger.info("Connecting Discord MediaGateway integration")

            # Start processing tasks
            await self._start_processing_tasks()

            self._is_connected = True
            logger.info("Discord MediaGateway integration connected successfully")
            return True

        except Exception as e:
            logger.error("Failed to connect Discord MediaGateway integration: %s", e)
            return False

    async def disconnect(self) -> bool:
        """
        Disconnect the MediaGateway integration.

        Returns:
            True if disconnection successful, False otherwise
        """
        try:
            logger.info("Disconnecting Discord MediaGateway integration")

            # Stop processing tasks
            await self._stop_processing_tasks()

            self._is_connected = False
            logger.info("Discord MediaGateway integration disconnected successfully")
            return True

        except Exception as e:
            logger.error("Failed to disconnect Discord MediaGateway integration: %s", e)
            return False

    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            await self.disconnect()

            # Clean up components
            self._media_gateway = None
            self._audio_contract = None

            self._is_initialized = False
            logger.info("Discord MediaGateway integration cleaned up")

        except Exception as e:
            logger.error("Error during cleanup: %s", e)

    def is_connected(self) -> bool:
        """Check if integration is connected."""
        return self._is_connected

    async def process_audio_frame(self, frame: PCMFrame) -> PCMFrame | None:
        """
        Process audio frame through MediaGateway.

        Args:
            frame: Input audio frame

        Returns:
            Processed audio frame or None if processing failed
        """
        if not self._is_connected or not self._media_gateway:
            logger.error("Integration not connected or MediaGateway not available")
            return None

        try:
            # Process frame through MediaGateway
            # Note: MediaGateway doesn't have process_frame method yet
            processed_frame = frame  # Pass through for now

            if processed_frame:
                # Emit processed frame event
                await self._emit_event(
                    "audio.frame_processed",
                    {"frame": processed_frame, "timestamp": datetime.now().timestamp()},
                )

            return processed_frame

        except Exception as e:
            logger.error("Failed to process audio frame: %s", e)
            return None

    async def normalize_audio(
        self, audio_data: bytes, input_format: AudioFormat
    ) -> bytes | None:
        """
        Normalize audio data using AudioContract.

        Args:
            audio_data: Input audio data
            input_format: Input audio format

        Returns:
            Normalized audio data or None if processing failed
        """
        if not self._is_connected or not self._audio_contract:
            logger.error("Integration not connected or AudioContract not available")
            return None

        try:
            # Normalize audio using AudioContract
            # Note: AudioContract doesn't have normalize_audio method yet
            normalized_data = audio_data  # Pass through for now

            if normalized_data:
                # Emit normalized audio event
                await self._emit_event(
                    "audio.normalized",
                    {
                        "data_length": len(normalized_data),
                        "timestamp": datetime.now().timestamp(),
                    },
                )

            return normalized_data

        except Exception as e:
            logger.error("Failed to normalize audio: %s", e)
            return None

    async def convert_codec(
        self, audio_data: bytes, input_format: AudioFormat, output_format: AudioFormat
    ) -> bytes | None:
        """
        Convert audio codec using MediaGateway.

        Args:
            audio_data: Input audio data
            input_format: Input audio format
            output_format: Output audio format

        Returns:
            Converted audio data or None if conversion failed
        """
        if not self._is_connected or not self._media_gateway:
            logger.error("Integration not connected or MediaGateway not available")
            return None

        try:
            # Convert codec using MediaGateway
            # Note: MediaGateway doesn't have convert_codec method yet
            converted_data = audio_data  # Pass through for now

            if converted_data:
                # Emit converted audio event
                await self._emit_event(
                    "audio.codec_converted",
                    {
                        "input_format": input_format.value,
                        "output_format": output_format.value,
                        "data_length": len(converted_data),
                        "timestamp": datetime.now().timestamp(),
                    },
                )

            return converted_data

        except Exception as e:
            logger.error("Failed to convert codec: %s", e)
            return None

    async def register_event_handler(
        self, event_type: str, handler: Callable[..., Any]
    ) -> None:
        """
        Register event handler for specific event type.

        Args:
            event_type: Type of event to handle
            handler: Handler function
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        logger.debug("Registered event handler for %s", event_type)

    async def _setup_event_routing(self) -> None:
        """Set up event routing between components."""
        try:
            # Register MediaGateway event handlers
            if self._media_gateway:
                # MediaGateway doesn't have event handlers yet
                pass

            logger.debug("Event routing set up successfully")

        except Exception as e:
            logger.error("Failed to set up event routing: %s", e)

    async def _start_processing_tasks(self) -> None:
        """Start background processing tasks."""
        try:
            # Start audio processing task
            task = asyncio.create_task(self._audio_processing_loop())
            self._processing_tasks.append(task)

            # Start codec conversion task
            task = asyncio.create_task(self._codec_conversion_loop())
            self._processing_tasks.append(task)

            logger.debug("Processing tasks started")

        except Exception as e:
            logger.error("Failed to start processing tasks: %s", e)

    async def _stop_processing_tasks(self) -> None:
        """Stop background processing tasks."""
        try:
            # Cancel all tasks
            for task in self._processing_tasks:
                task.cancel()

            # Wait for tasks to complete
            if self._processing_tasks:
                await asyncio.gather(*self._processing_tasks, return_exceptions=True)

            self._processing_tasks.clear()
            logger.debug("Processing tasks stopped")

        except Exception as e:
            logger.error("Failed to stop processing tasks: %s", e)

    async def _audio_processing_loop(self) -> None:
        """Background task for audio processing."""
        try:
            while self._is_connected and self.audio_source:
                # Process audio frames from source
                frames = await self.audio_source.read_audio_frame()
                if frames:
                    for frame in frames:
                        # Process frame through MediaGateway
                        processed_frame = await self.process_audio_frame(frame)
                        if processed_frame:
                            # Send to sink
                            await self.audio_sink.play_audio_chunk(processed_frame)

                await asyncio.sleep(0.01)  # 10ms loop

        except asyncio.CancelledError:
            logger.debug("Audio processing loop cancelled")
        except Exception as e:
            logger.error("Error in audio processing loop: %s", e)

    async def _codec_conversion_loop(self) -> None:
        """Background task for codec conversion."""
        try:
            while self._is_connected:
                # Perform codec conversion tasks
                # This is a placeholder for future codec conversion logic
                await asyncio.sleep(0.1)  # 100ms loop

        except asyncio.CancelledError:
            logger.debug("Codec conversion loop cancelled")
        except Exception as e:
            logger.error("Error in codec conversion loop: %s", e)

    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit event to registered handlers."""
        try:
            if event_type in self._event_handlers:
                for handler in self._event_handlers[event_type]:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(data)
                        else:
                            handler(data)
                    except Exception as e:
                        logger.error("Error in event handler: %s", e)

        except Exception as e:
            logger.error("Error emitting event: %s", e)

    async def get_integration_metrics(self) -> dict[str, Any]:
        """
        Get integration metrics and statistics.

        Returns:
            Dictionary containing integration metrics
        """
        metrics = {
            "is_initialized": self._is_initialized,
            "is_connected": self._is_connected,
            "processing_tasks_count": len(self._processing_tasks),
            "event_handlers_count": sum(
                len(handlers) for handlers in self._event_handlers.values()
            ),
            "canonical_format": self._canonical_format.value,
            "enable_codec_conversion": self._enable_codec_conversion,
            "enable_audio_normalization": self._enable_audio_normalization,
            "enable_drift_correction": self._enable_drift_correction,
        }

        # Add component-specific metrics
        if self._media_gateway:
            # Note: MediaGateway doesn't have get_telemetry method yet
            metrics["media_gateway_metrics"] = {"status": "available"}

        if self._audio_contract:
            # Note: AudioContract doesn't have get_telemetry method yet
            metrics["audio_contract_metrics"] = {"status": "available"}

        return metrics
