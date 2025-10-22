"""Integration tests for audio orchestrator."""

from unittest.mock import AsyncMock

import pytest

from services.orchestrator.adapters.manager import AdapterManager
from services.orchestrator.agents.manager import AgentManager
from services.orchestrator.integration.audio_orchestrator import AudioOrchestrator
from services.orchestrator.pipeline.types import (
    AudioFormat,
    ProcessedSegment,
    ProcessingStatus,
)


pytestmark = pytest.mark.component


class TestAudioOrchestrator:
    """Test AudioOrchestrator integration."""

    def test_audio_orchestrator_creation(self):
        """Test creating an audio orchestrator."""
        orchestrator = AudioOrchestrator()

        assert orchestrator.adapter_manager is not None
        assert orchestrator.agent_manager is not None
        assert orchestrator.audio_pipeline is not None
        assert orchestrator.pipeline_integration is not None
        assert orchestrator.agent_integration is not None

    def test_audio_orchestrator_creation_with_components(self):
        """Test creating an audio orchestrator with custom components."""
        adapter_manager = AdapterManager()
        agent_manager = AgentManager()

        orchestrator = AudioOrchestrator(
            adapter_manager=adapter_manager,
            agent_manager=agent_manager,
        )

        assert orchestrator.adapter_manager == adapter_manager
        assert orchestrator.agent_manager == agent_manager

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test orchestrator initialization."""
        orchestrator = AudioOrchestrator()

        # Mock component health checks
        orchestrator.adapter_manager.health_check = AsyncMock(  # type: ignore[method-assign]
            return_value={"status": "healthy"}
        )
        orchestrator.agent_manager.get_stats = AsyncMock(  # type: ignore[method-assign]
            return_value={"agent_count": 0}
        )
        orchestrator.audio_pipeline.health_check = AsyncMock(  # type: ignore[method-assign]
            return_value={"status": "healthy"}
        )

        await orchestrator.initialize()

        assert orchestrator._is_initialized is True

    @pytest.mark.asyncio
    async def test_start_session(self):
        """Test starting an audio processing session."""
        orchestrator = AudioOrchestrator()

        # Mock initialization
        orchestrator._is_initialized = True
        orchestrator.pipeline_integration.start_processing = AsyncMock()  # type: ignore[method-assign]

        await orchestrator.start_session("session-123")

        assert "session-123" in orchestrator._active_sessions
        orchestrator.pipeline_integration.start_processing.assert_called_once_with(
            "session-123"
        )

    @pytest.mark.asyncio
    async def test_start_session_already_active(self):
        """Test starting a session that's already active."""
        orchestrator = AudioOrchestrator()

        # Mock initialization
        orchestrator._is_initialized = True
        orchestrator._active_sessions.add("session-123")

        # Should not raise an error
        await orchestrator.start_session("session-123")

    @pytest.mark.asyncio
    async def test_stop_session(self):
        """Test stopping an audio processing session."""
        orchestrator = AudioOrchestrator()

        # Mock session state
        orchestrator._active_sessions.add("session-123")
        orchestrator.pipeline_integration.stop_processing = AsyncMock()  # type: ignore[method-assign]
        orchestrator.agent_integration.end_session = AsyncMock()  # type: ignore[method-assign]

        await orchestrator.stop_session("session-123")

        assert "session-123" not in orchestrator._active_sessions
        orchestrator.pipeline_integration.stop_processing.assert_called_once_with(
            "session-123"
        )
        orchestrator.agent_integration.end_session.assert_called_once_with(
            "session-123"
        )

    @pytest.mark.asyncio
    async def test_stop_session_not_active(self):
        """Test stopping a session that's not active."""
        orchestrator = AudioOrchestrator()

        # Should not raise an error
        await orchestrator.stop_session("session-123")

    @pytest.mark.asyncio
    async def test_handle_processed_segment(self):
        """Test handling a processed audio segment."""
        orchestrator = AudioOrchestrator()

        # Mock session state
        orchestrator._active_sessions.add("session-123")
        orchestrator.agent_integration.handle_processed_segment = AsyncMock()  # type: ignore[method-assign]

        # Create processed segment
        processed_segment = ProcessedSegment(
            audio_data=b"\x00" * 1024,
            correlation_id="test-123",
            session_id="session-123",
            original_format=AudioFormat.PCM,
            processed_format=AudioFormat.PCM,
            sample_rate=16000,
            channels=1,
            duration=0.1,
            status=ProcessingStatus.COMPLETED,
            processing_time=0.01,
        )

        await orchestrator.handle_processed_segment(processed_segment, "session-123")

        orchestrator.agent_integration.handle_processed_segment.assert_called_once_with(
            processed_segment, "session-123"
        )

    @pytest.mark.asyncio
    async def test_handle_processed_segment_inactive_session(self):
        """Test handling a processed segment for inactive session."""
        orchestrator = AudioOrchestrator()

        # Create processed segment
        processed_segment = ProcessedSegment(
            audio_data=b"\x00" * 1024,
            correlation_id="test-123",
            session_id="session-123",
            original_format=AudioFormat.PCM,
            processed_format=AudioFormat.PCM,
            sample_rate=16000,
            channels=1,
            duration=0.1,
            status=ProcessingStatus.COMPLETED,
            processing_time=0.01,
        )

        # Should not raise an error
        await orchestrator.handle_processed_segment(processed_segment, "session-123")

    @pytest.mark.asyncio
    async def test_get_session_status(self):
        """Test getting session status."""
        orchestrator = AudioOrchestrator()

        # Mock session state
        orchestrator._active_sessions.add("session-123")
        orchestrator.pipeline_integration.get_status = AsyncMock(  # type: ignore[method-assign]
            return_value={"is_processing": True}
        )
        orchestrator.agent_integration.get_status = AsyncMock(  # type: ignore[method-assign]
            return_value={"active_sessions": 1}
        )

        status = await orchestrator.get_session_status("session-123")

        assert status["session_id"] == "session-123"
        assert status["is_active"] is True
        assert "pipeline_status" in status
        assert "agent_status" in status

    @pytest.mark.asyncio
    async def test_get_orchestrator_status(self):
        """Test getting orchestrator status."""
        orchestrator = AudioOrchestrator()

        # Mock component status
        orchestrator._is_initialized = True
        orchestrator._active_sessions.add("session-123")
        orchestrator.adapter_manager.health_check = AsyncMock(  # type: ignore[method-assign]
            return_value={"status": "healthy"}
        )
        orchestrator.agent_manager.get_stats = AsyncMock(  # type: ignore[method-assign]
            return_value={"agent_count": 0}
        )
        orchestrator.audio_pipeline.health_check = AsyncMock(  # type: ignore[method-assign]
            return_value={"status": "healthy"}
        )
        orchestrator.pipeline_integration.get_status = AsyncMock(  # type: ignore[method-assign]
            return_value={"is_processing": True}
        )
        orchestrator.agent_integration.get_status = AsyncMock(  # type: ignore[method-assign]
            return_value={"active_sessions": 1}
        )

        status = await orchestrator.get_orchestrator_status()

        assert status["is_initialized"] is True
        assert status["active_sessions"] == 1
        assert "session-123" in status["session_ids"]
        assert "adapter_manager" in status
        assert "agent_manager" in status
        assert "audio_pipeline" in status
        assert "pipeline_integration" in status
        assert "agent_integration" in status

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        orchestrator = AudioOrchestrator()

        # Mock component health checks
        orchestrator._is_initialized = True
        orchestrator._active_sessions.add("session-123")
        orchestrator.adapter_manager.health_check = AsyncMock(  # type: ignore[method-assign]
            return_value={"status": "healthy"}
        )
        orchestrator.agent_manager.get_stats = AsyncMock(  # type: ignore[method-assign]
            return_value={"agent_count": 0}
        )
        orchestrator.audio_pipeline.health_check = AsyncMock(  # type: ignore[method-assign]
            return_value={"status": "healthy"}
        )
        orchestrator.pipeline_integration.get_status = AsyncMock(  # type: ignore[method-assign]
            return_value={"is_processing": True}
        )
        orchestrator.agent_integration.get_status = AsyncMock(  # type: ignore[method-assign]
            return_value={"active_sessions": 1}
        )

        health = await orchestrator.health_check()

        assert health["status"] == "healthy"
        assert health["orchestrator_type"] == "AudioOrchestrator"
        assert health["is_initialized"] is True
        assert health["active_sessions"] == 1
        assert "components" in health
