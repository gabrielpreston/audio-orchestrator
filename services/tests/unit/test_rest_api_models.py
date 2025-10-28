"""Unit tests for REST API models."""

import pytest
from pydantic import ValidationError

from services.discord.models import (
    MessageSendRequest,
    MessageSendResponse,
    TranscriptNotificationRequest,
    CapabilitiesResponse,
    CapabilityInfo,
)
from services.orchestrator.models import (
    TranscriptProcessRequest,
    TranscriptProcessResponse,
    CapabilitiesResponse as OrchestratorCapabilitiesResponse,
    CapabilityInfo as OrchestratorCapabilityInfo,
    StatusResponse,
    ConnectionInfo,
)


@pytest.mark.unit
class TestDiscordModels:
    """Test Discord REST API models."""

    def test_message_send_request_valid(self):
        """Test valid MessageSendRequest."""
        request = MessageSendRequest(
            channel_id="123456789",
            content="Hello, world!",
            correlation_id="test_correlation_123",
        )

        assert request.channel_id == "123456789"
        assert request.content == "Hello, world!"
        assert request.correlation_id == "test_correlation_123"
        assert request.metadata == {}

    def test_message_send_request_minimal(self):
        """Test minimal MessageSendRequest."""
        request = MessageSendRequest(channel_id="123456789", content="Hello, world!")

        assert request.channel_id == "123456789"
        assert request.content == "Hello, world!"
        assert request.correlation_id is None
        assert request.metadata == {}

    def test_message_send_request_invalid(self):
        """Test invalid MessageSendRequest."""
        with pytest.raises(ValidationError):
            MessageSendRequest(
                channel_id=123,  # Wrong type - should be string
                content="Hello, world!",
            )

    def test_message_send_response_valid(self):
        """Test valid MessageSendResponse."""
        response = MessageSendResponse(
            success=True, message_id="msg_123456", correlation_id="test_correlation_123"
        )

        assert response.success is True
        assert response.message_id == "msg_123456"
        assert response.correlation_id == "test_correlation_123"
        assert response.error is None

    def test_transcript_notification_request_valid(self):
        """Test valid TranscriptNotificationRequest."""
        request = TranscriptNotificationRequest(
            transcript="Hello, this is a test",
            user_id="user_123",
            channel_id="channel_456",
            correlation_id="test_correlation_789",
        )

        assert request.transcript == "Hello, this is a test"
        assert request.user_id == "user_123"
        assert request.channel_id == "channel_456"
        assert request.correlation_id == "test_correlation_789"
        assert request.metadata == {}

    def test_capabilities_response_valid(self):
        """Test valid CapabilitiesResponse."""
        capabilities = [
            CapabilityInfo(
                name="send_message",
                description="Send a message to Discord channel",
                parameters={"type": "object", "properties": {}},
            ),
            CapabilityInfo(
                name="transcript_notification",
                description="Receive transcript notifications",
                parameters={"type": "object", "properties": {}},
            ),
        ]

        response = CapabilitiesResponse(
            service="discord", version="1.0.0", capabilities=capabilities
        )

        assert response.service == "discord"
        assert response.version == "1.0.0"
        assert len(response.capabilities) == 2
        assert response.capabilities[0].name == "send_message"
        assert response.capabilities[1].name == "transcript_notification"


@pytest.mark.unit
class TestOrchestratorModels:
    """Test Orchestrator REST API models."""

    def test_transcript_process_request_valid(self):
        """Test valid TranscriptProcessRequest."""
        request = TranscriptProcessRequest(
            transcript="Hello, how are you?",
            user_id="user_123",
            channel_id="channel_456",
            correlation_id="test_correlation_789",
            metadata={"source": "test"},
        )

        assert request.transcript == "Hello, how are you?"
        assert request.user_id == "user_123"
        assert request.channel_id == "channel_456"
        assert request.correlation_id == "test_correlation_789"
        assert request.metadata == {"source": "test"}

    def test_transcript_process_response_valid(self):
        """Test valid TranscriptProcessResponse."""
        response = TranscriptProcessResponse(
            success=True,
            response_text="I'm doing well, thank you!",
            tool_calls=[{"tool": "weather", "args": {"location": "SF"}}],
            correlation_id="test_correlation_123",
        )

        assert response.success is True
        assert response.response_text == "I'm doing well, thank you!"
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1
        assert response.correlation_id == "test_correlation_123"
        assert response.error is None

    def test_transcript_process_response_error(self):
        """Test TranscriptProcessResponse with error."""
        response = TranscriptProcessResponse(
            success=False,
            response_text=None,
            tool_calls=None,
            correlation_id="test_correlation_123",
            error="Processing failed",
        )

        assert response.success is False
        assert response.response_text is None
        assert response.tool_calls is None
        assert response.error == "Processing failed"

    def test_status_response_valid(self):
        """Test valid StatusResponse."""
        connections = [
            ConnectionInfo(
                service="discord", status="connected", url="http://discord:8001"
            ),
            ConnectionInfo(service="flan", status="connected", url="http://flan:8200"),
        ]

        response = StatusResponse(
            service="orchestrator",
            status="healthy",
            connections=connections,
            uptime="2h 30m",
            version="1.0.0",
        )

        assert response.service == "orchestrator"
        assert response.status == "healthy"
        assert len(response.connections) == 2
        assert response.uptime == "2h 30m"
        assert response.version == "1.0.0"

    def test_connection_info_valid(self):
        """Test valid ConnectionInfo."""
        connection = ConnectionInfo(
            service="discord",
            status="connected",
            url="http://discord:8001",
            last_heartbeat="2024-01-15T10:30:00Z",
        )

        assert connection.service == "discord"
        assert connection.status == "connected"
        assert connection.url == "http://discord:8001"
        assert connection.last_heartbeat == "2024-01-15T10:30:00Z"

    def test_orchestrator_capabilities_response_valid(self):
        """Test valid OrchestratorCapabilitiesResponse."""
        capabilities = [
            OrchestratorCapabilityInfo(
                name="transcript_processing",
                description="Process voice transcripts",
                parameters={"type": "object", "properties": {}},
            ),
            OrchestratorCapabilityInfo(
                name="discord_message_sending",
                description="Send Discord messages",
                parameters={"type": "object", "properties": {}},
            ),
        ]

        response = OrchestratorCapabilitiesResponse(
            service="orchestrator", version="1.0.0", capabilities=capabilities
        )

        assert response.service == "orchestrator"
        assert response.version == "1.0.0"
        assert len(response.capabilities) == 2
        assert response.capabilities[0].name == "transcript_processing"
        assert response.capabilities[1].name == "discord_message_sending"


@pytest.mark.unit
class TestModelSerialization:
    """Test model serialization and deserialization."""

    def test_discord_models_json_serialization(self):
        """Test JSON serialization of Discord models."""
        request = MessageSendRequest(
            channel_id="123456789",
            content="Hello, world!",
            correlation_id="test_correlation_123",
        )

        # Test serialization
        json_data = request.model_dump()
        assert json_data["channel_id"] == "123456789"
        assert json_data["content"] == "Hello, world!"
        assert json_data["correlation_id"] == "test_correlation_123"

        # Test deserialization
        reconstructed = MessageSendRequest(**json_data)
        assert reconstructed.channel_id == request.channel_id
        assert reconstructed.content == request.content
        assert reconstructed.correlation_id == request.correlation_id

    def test_orchestrator_models_json_serialization(self):
        """Test JSON serialization of Orchestrator models."""
        request = TranscriptProcessRequest(
            transcript="Hello, how are you?",
            user_id="user_123",
            channel_id="channel_456",
            correlation_id="test_correlation_789",
        )

        # Test serialization
        json_data = request.model_dump()
        assert json_data["transcript"] == "Hello, how are you?"
        assert json_data["user_id"] == "user_123"
        assert json_data["channel_id"] == "channel_456"
        assert json_data["correlation_id"] == "test_correlation_789"

        # Test deserialization
        reconstructed = TranscriptProcessRequest(**json_data)
        assert reconstructed.transcript == request.transcript
        assert reconstructed.user_id == request.user_id
        assert reconstructed.channel_id == request.channel_id
        assert reconstructed.correlation_id == request.correlation_id
