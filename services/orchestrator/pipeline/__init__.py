"""Audio Pipeline framework for audio-orchestrator services.

This module provides the core audio processing pipeline components,
enabling end-to-end audio processing from input to output.

Key Components:
- AudioProcessor: Audio format conversion and processing
- WakeDetector: Wake phrase detection and filtering
- AudioPipeline: End-to-end audio processing pipeline
- ProcessedSegment: Processed audio segment with metadata

Usage:
    from services.orchestrator.pipeline import AudioPipeline, AudioProcessor
    
    # Create audio processor
    processor = AudioProcessor()
    
    # Create pipeline
    pipeline = AudioPipeline(processor)
    
    # Process audio chunks
    async for processed_segment in pipeline.process_audio_stream(audio_stream):
        # Handle processed audio
        pass
"""

from .audio_processor import AudioProcessor
from .pipeline import AudioPipeline
from .types import ProcessedSegment, ProcessingConfig
from .wake_detector import WakeDetector


__all__ = [
    "AudioProcessor",
    "AudioPipeline",
    "WakeDetector",
    "ProcessedSegment",
    "ProcessingConfig",
]
