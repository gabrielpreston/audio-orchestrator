"""Integration layer for audio-orchestrator services.

This module provides integration between the audio pipeline, I/O adapters,
and agent framework to create a complete audio processing workflow.

Key Components:
- AudioOrchestrator: Main orchestrator that coordinates all components
- PipelineIntegration: Integration between audio pipeline and I/O adapters
- AgentIntegration: Integration between audio pipeline and agent framework

Usage:
    from services.orchestrator.integration import AudioOrchestrator
    
    # Create orchestrator with all components
    orchestrator = AudioOrchestrator()
    
    # Start processing audio
    await orchestrator.start_processing(session_id="session-123")
"""

from .audio_orchestrator import AudioOrchestrator
from .pipeline_integration import PipelineIntegration
from .agent_integration import AgentIntegration

__all__ = [
    "AudioOrchestrator",
    "PipelineIntegration", 
    "AgentIntegration",
]
