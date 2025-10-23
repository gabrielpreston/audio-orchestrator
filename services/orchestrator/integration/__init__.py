"""Integration layer for audio-orchestrator services.

This module provides integration between I/O adapters and agent framework
to create a complete audio processing workflow.

Key Components:
- AudioOrchestrator: Main orchestrator that coordinates all components
- AgentIntegration: Integration between I/O adapters and agent framework

Usage:
    from services.orchestrator.integration import AudioOrchestrator

    # Create orchestrator with all components
    orchestrator = AudioOrchestrator()

    # Start processing audio
    await orchestrator.start_processing(session_id="session-123")
"""

from .agent_integration import AgentIntegration
from .audio_orchestrator import AudioOrchestrator


__all__ = [
    "AgentIntegration",
    "AudioOrchestrator",
]
