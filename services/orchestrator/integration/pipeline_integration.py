"""Integration between audio pipeline and I/O adapters.

This module provides the integration layer between the audio pipeline
and the I/O adapters, enabling seamless audio processing workflows.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from services.common.logging import get_logger

from ..adapters.manager import AdapterManager
from ..adapters.types import AudioChunk
from ..pipeline.pipeline import AudioPipeline
from ..pipeline.types import ProcessedSegment, ProcessingConfig

logger = get_logger(__name__)


class PipelineIntegration:
    """Integration between audio pipeline and I/O adapters.
    
    This class coordinates the flow of audio data from input adapters
    through the audio pipeline to output adapters.
    """
    
    def __init__(
        self,
        adapter_manager: AdapterManager,
        audio_pipeline: AudioPipeline,
        config: ProcessingConfig | None = None,
    ) -> None:
        """Initialize the pipeline integration.
        
        Args:
            adapter_manager: Manager for I/O adapters
            audio_pipeline: Audio processing pipeline
            config: Processing configuration
        """
        self.adapter_manager = adapter_manager
        self.audio_pipeline = audio_pipeline
        self.config = config or ProcessingConfig()
        self._logger = get_logger(self.__class__.__name__)
        
        # Processing state
        self._is_processing = False
        self._processing_tasks: set[asyncio.Task[None]] = set()
        
        self._logger.info(
            "Pipeline integration initialized",
            extra={
                "pipeline_config": {
                    "target_sample_rate": self.config.target_sample_rate,
                    "target_channels": self.config.target_channels,
                    "wake_detection_enabled": self.config.wake_detection_enabled,
                },
            }
        )
    
    async def start_processing(self, session_id: str) -> None:
        """Start processing audio for a session.
        
        Args:
            session_id: Session identifier
        """
        if self._is_processing:
            self._logger.warning(
                "Processing already started",
                extra={"session_id": session_id}
            )
            return
        
        self._is_processing = True
        
        try:
            # Get input and output adapters
            input_adapter = self.adapter_manager.get_input_adapter("discord")
            output_adapter = self.adapter_manager.get_output_adapter("discord")
            
            if not input_adapter or not output_adapter:
                raise ValueError("Required adapters not available")
            
            self._logger.info(
                "Starting audio processing",
                extra={"session_id": session_id}
            )
            
            # Start input adapter
            await input_adapter.start_capture()
            
            # Create processing task
            processing_task = asyncio.create_task(
                self._process_audio_stream(input_adapter, output_adapter, session_id)
            )
            self._processing_tasks.add(processing_task)
            
            # Clean up completed tasks
            processing_task.add_done_callback(self._processing_tasks.discard)
            
        except Exception as e:
            self._is_processing = False
            self._logger.error(
                "Error starting audio processing",
                extra={"session_id": session_id, "error": str(e)}
            )
            raise
    
    async def stop_processing(self, session_id: str) -> None:
        """Stop processing audio for a session.
        
        Args:
            session_id: Session identifier
        """
        if not self._is_processing:
            self._logger.warning(
                "Processing not started",
                extra={"session_id": session_id}
            )
            return
        
        self._is_processing = False
        
        try:
            # Cancel all processing tasks
            for task in self._processing_tasks:
                task.cancel()
            
            # Wait for tasks to complete
            if self._processing_tasks:
                await asyncio.gather(*self._processing_tasks, return_exceptions=True)
            
            # Stop input adapter
            input_adapter = self.adapter_manager.get_input_adapter("discord")
            if input_adapter:
                await input_adapter.stop_capture()
            
            self._logger.info(
                "Audio processing stopped",
                extra={"session_id": session_id}
            )
            
        except Exception as e:
            self._logger.error(
                "Error stopping audio processing",
                extra={"session_id": session_id, "error": str(e)}
            )
            raise
    
    async def _process_audio_stream(
        self,
        input_adapter,
        output_adapter,
        session_id: str,
    ) -> None:
        """Process audio stream from input to output.
        
        Args:
            input_adapter: Audio input adapter
            output_adapter: Audio output adapter
            session_id: Session identifier
        """
        try:
            # Get audio stream from input adapter
            audio_stream = input_adapter.get_audio_stream()
            
            # Process audio through pipeline
            async for processed_segment in self.audio_pipeline.process_audio_stream(
                audio_stream, session_id
            ):
                # Handle processed segment
                await self._handle_processed_segment(
                    processed_segment, output_adapter, session_id
                )
                
        except asyncio.CancelledError:
            self._logger.info(
                "Audio processing cancelled",
                extra={"session_id": session_id}
            )
            raise
        except Exception as e:
            self._logger.error(
                "Error in audio stream processing",
                extra={"session_id": session_id, "error": str(e)}
            )
            raise
    
    async def _handle_processed_segment(
        self,
        processed_segment: ProcessedSegment,
        output_adapter,
        session_id: str,
    ) -> None:
        """Handle a processed audio segment.
        
        Args:
            processed_segment: Processed audio segment
            output_adapter: Audio output adapter
            session_id: Session identifier
        """
        try:
            # Log segment processing
            self._logger.debug(
                "Handling processed segment",
                extra={
                    "correlation_id": processed_segment.correlation_id,
                    "session_id": session_id,
                    "status": processed_segment.status.value,
                    "wake_detected": processed_segment.wake_detected,
                    "duration": processed_segment.duration,
                }
            )
            
            # Only process completed segments
            if processed_segment.status.value != "completed":
                return
            
            # Convert processed segment back to audio chunk for output
            audio_chunk = AudioChunk(
                data=processed_segment.audio_data,
                metadata={
                    "sample_rate": processed_segment.sample_rate,
                    "channels": processed_segment.channels,
                    "duration": processed_segment.duration,
                },
                correlation_id=processed_segment.correlation_id,
                sequence_number=0,  # Will be set by output adapter
            )
            
            # Send to output adapter if needed
            # For now, just log the segment
            if processed_segment.wake_detected:
                self._logger.info(
                    "Wake phrase detected, segment ready for agent processing",
                    extra={
                        "correlation_id": processed_segment.correlation_id,
                        "session_id": session_id,
                        "wake_phrase": processed_segment.wake_phrase,
                        "confidence": processed_segment.wake_confidence,
                    }
                )
            
        except Exception as e:
            self._logger.error(
                "Error handling processed segment",
                extra={
                    "correlation_id": processed_segment.correlation_id,
                    "session_id": session_id,
                    "error": str(e),
                }
            )
    
    async def get_status(self) -> dict[str, Any]:
        """Get integration status.
        
        Returns:
            Dictionary containing integration status
        """
        return {
            "is_processing": self._is_processing,
            "active_tasks": len(self._processing_tasks),
            "adapter_manager": await self.adapter_manager.health_check(),
            "audio_pipeline": await self.audio_pipeline.health_check(),
        }
    
    async def health_check(self) -> dict[str, Any]:
        """Perform health check for the integration.
        
        Returns:
            Health check results
        """
        return {
            "status": "healthy",
            "integration_type": "PipelineIntegration",
            "is_processing": self._is_processing,
            "active_tasks": len(self._processing_tasks),
            "adapter_manager": await self.adapter_manager.health_check(),
            "audio_pipeline": await self.audio_pipeline.health_check(),
        }
