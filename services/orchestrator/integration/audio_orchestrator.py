"""Main audio orchestrator that coordinates all components.

This module provides the main AudioOrchestrator class that coordinates
the audio pipeline, I/O adapters, and agent framework into a complete
audio processing workflow.
"""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

from services.orchestrator.adapters.manager import AdapterManager
from services.orchestrator.agents.manager import AgentManager
from services.orchestrator.pipeline.pipeline import AudioPipeline
from services.orchestrator.pipeline.types import ProcessedSegment, ProcessingConfig
from .agent_integration import AgentIntegration
from .pipeline_integration import PipelineIntegration


logger = get_logger(__name__)


class AudioOrchestrator:
    """Main audio orchestrator that coordinates all components.

    This class provides the main interface for audio processing,
    coordinating between adapters, pipeline, and agents.
    """

    def __init__(
        self,
        adapter_manager: AdapterManager | None = None,
        agent_manager: AgentManager | None = None,
        audio_pipeline: AudioPipeline | None = None,
        config: ProcessingConfig | None = None,
    ) -> None:
        """Initialize the audio orchestrator.

        Args:
            adapter_manager: Manager for I/O adapters
            agent_manager: Manager for agents
            audio_pipeline: Audio processing pipeline
            config: Processing configuration
        """
        self.config = config or ProcessingConfig()

        # Initialize components
        self.adapter_manager = adapter_manager or AdapterManager()
        self.agent_manager = agent_manager or AgentManager()
        self.audio_pipeline = audio_pipeline or AudioPipeline(config=self.config)

        # Initialize integrations
        self.pipeline_integration = PipelineIntegration(
            self.adapter_manager,
            self.audio_pipeline,
            self.config,
            segment_callback=self.handle_processed_segment,
        )
        self.agent_integration = AgentIntegration(self.agent_manager)

        self._logger = get_logger(self.__class__.__name__)

        # Orchestrator state
        self._active_sessions: set[str] = set()
        self._is_initialized = False

        self._logger.info(
            "Audio orchestrator initialized",
            extra={
                "config": {
                    "target_sample_rate": self.config.target_sample_rate,
                    "target_channels": self.config.target_channels,
                    "wake_detection_enabled": self.config.wake_detection_enabled,
                },
            },
        )

    async def initialize(self) -> None:
        """Initialize the orchestrator and all components."""
        if self._is_initialized:
            self._logger.warning("Orchestrator already initialized")
            return

        try:
            # Initialize adapter manager
            await self.adapter_manager.health_check()

            # Initialize agent manager
            self.agent_manager.get_stats()

            # Initialize audio pipeline
            await self.audio_pipeline.health_check()

            self._is_initialized = True

            self._logger.info("Audio orchestrator initialization completed")

        except Exception as e:
            self._logger.error(
                "Error initializing audio orchestrator", extra={"error": str(e)}
            )
            raise

    async def start_session(self, session_id: str) -> None:
        """Start a new audio processing session.

        Args:
            session_id: Session identifier
        """
        if not self._is_initialized:
            await self.initialize()

        if session_id in self._active_sessions:
            self._logger.warning(
                "Session already active", extra={"session_id": session_id}
            )
            return

        try:
            # Start pipeline integration
            await self.pipeline_integration.start_processing(session_id)

            # Register session
            self._active_sessions.add(session_id)

            self._logger.info(
                "Audio processing session started", extra={"session_id": session_id}
            )

        except Exception as e:
            self._logger.error(
                "Error starting audio processing session",
                extra={"session_id": session_id, "error": str(e)},
            )
            raise

    async def stop_session(self, session_id: str) -> None:
        """Stop an audio processing session.

        Args:
            session_id: Session identifier
        """
        if session_id not in self._active_sessions:
            self._logger.warning("Session not active", extra={"session_id": session_id})
            return

        try:
            # Stop pipeline integration
            await self.pipeline_integration.stop_processing(session_id)

            # End agent session
            await self.agent_integration.end_session(session_id)

            # Unregister session
            self._active_sessions.remove(session_id)

            self._logger.info(
                "Audio processing session stopped", extra={"session_id": session_id}
            )

        except Exception as e:
            self._logger.error(
                "Error stopping audio processing session",
                extra={"session_id": session_id, "error": str(e)},
            )
            raise

    async def handle_processed_segment(
        self,
        processed_segment: ProcessedSegment,
        session_id: str,
    ) -> None:
        """Handle a processed audio segment.

        Args:
            processed_segment: Processed audio segment
            session_id: Session identifier
        """
        if session_id not in self._active_sessions:
            self._logger.warning("Session not active", extra={"session_id": session_id})
            return

        try:
            # Handle with agent integration
            await self.agent_integration.handle_processed_segment(
                processed_segment, session_id
            )

        except Exception as e:
            self._logger.error(
                "Error handling processed segment",
                extra={
                    "correlation_id": processed_segment.correlation_id,
                    "session_id": session_id,
                    "error": str(e),
                },
            )

    async def get_session_status(self, session_id: str) -> dict[str, Any]:
        """Get status for a specific session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary containing session status
        """
        return {
            "session_id": session_id,
            "is_active": session_id in self._active_sessions,
            "pipeline_status": await self.pipeline_integration.get_status(),
            "agent_status": await self.agent_integration.get_status(),
        }

    async def get_orchestrator_status(self) -> dict[str, Any]:
        """Get overall orchestrator status.

        Returns:
            Dictionary containing orchestrator status
        """
        return {
            "is_initialized": self._is_initialized,
            "active_sessions": len(self._active_sessions),
            "session_ids": list(self._active_sessions),
            "adapter_manager": await self.adapter_manager.health_check(),
            "agent_manager": self.agent_manager.get_stats(),
            "audio_pipeline": await self.audio_pipeline.health_check(),
            "pipeline_integration": await self.pipeline_integration.get_status(),
            "agent_integration": await self.agent_integration.get_status(),
        }

    async def health_check(self) -> dict[str, Any]:
        """Perform health check for the orchestrator.

        Returns:
            Health check results
        """
        return {
            "status": "healthy",
            "orchestrator_type": "AudioOrchestrator",
            "is_initialized": self._is_initialized,
            "active_sessions": len(self._active_sessions),
            "components": {
                "adapter_manager": await self.adapter_manager.health_check(),
                "agent_manager": self.agent_manager.get_stats(),
                "audio_pipeline": await self.audio_pipeline.health_check(),
                "pipeline_integration": await self.pipeline_integration.get_status(),
                "agent_integration": await self.agent_integration.get_status(),
            },
        }
