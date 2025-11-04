"""Tests for Orchestrator service FastAPI route handlers."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch
import sys

import pytest
from fastapi.testclient import TestClient

from services.common.health import HealthCheck, HealthManager, HealthStatus

# Mock langchain imports before importing orchestrator app
# This prevents ImportError when langchain is not installed in test environment
mock_langchain = MagicMock()
mock_langchain.agents.AgentExecutor = MagicMock
mock_langchain.agents.create_openai_functions_agent = MagicMock
mock_langchain.memory.ConversationBufferMemory = MagicMock
mock_langchain.prompts.ChatPromptTemplate = MagicMock
mock_langchain.prompts.MessagesPlaceholder = MagicMock
mock_langchain.tools.Tool = MagicMock
mock_langchain_openai = MagicMock()
mock_langchain_openai.ChatOpenAI = MagicMock

sys.modules["langchain"] = mock_langchain
sys.modules["langchain.agents"] = mock_langchain.agents
sys.modules["langchain.memory"] = mock_langchain.memory
sys.modules["langchain.prompts"] = mock_langchain.prompts
sys.modules["langchain.tools"] = mock_langchain.tools
sys.modules["langchain_openai"] = mock_langchain_openai

# Now import the app after mocking langchain
from services.orchestrator.app import app  # noqa: E402


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_health_manager():
    """Mock health manager."""
    manager = MagicMock(spec=HealthManager)
    manager._startup_complete = True
    manager.get_health_status = AsyncMock(
        return_value=HealthCheck(
            status=HealthStatus.HEALTHY,
            ready=True,
            details={"startup_complete": True, "dependencies": {}},
        )
    )
    return manager


@pytest.fixture
def mock_app_state():
    """Mock app.state with required components."""
    state = Mock()
    state.cfg = Mock()
    state.langchain_executor = Mock()
    state.tts_client = Mock()
    return state


class TestOrchestratorHealthEndpoints:
    """Test Orchestrator service health endpoints."""

    @pytest.mark.unit
    def test_health_live_endpoint(self, client):
        """Test /health/live endpoint returns alive status."""
        # Health live endpoint doesn't use health_manager, just returns simple dict
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert data["service"] == "orchestrator"

    @pytest.mark.unit
    def test_health_ready_endpoint_ready(self, client, mock_app_state):
        """Test /health/ready endpoint when service is ready."""
        mock_health_status = HealthCheck(
            status=HealthStatus.HEALTHY,
            ready=True,
            details={
                "startup_complete": True,
                "config_loaded": True,
                "executor_ready": True,
                "tts_client_ready": True,
                "dependencies": {},
            },
        )

        # Mock health manager with startup complete and ready status
        mock_health_manager = MagicMock(spec=HealthManager)
        mock_health_manager._startup_complete = True
        mock_health_manager.get_startup_failure.return_value = None
        mock_health_manager.get_health_status = AsyncMock(
            return_value=mock_health_status
        )

        # Import health_endpoints to patch it
        from services.orchestrator.app import health_endpoints

        with (
            patch.object(app, "state", mock_app_state),
            patch("services.orchestrator.app._health_manager", mock_health_manager),
            patch.object(health_endpoints, "health_manager", mock_health_manager),
        ):
            response = client.get("/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert data["service"] == "orchestrator"

    @pytest.mark.unit
    def test_health_ready_endpoint_not_ready(self, client):
        """Test /health/ready endpoint when service is not ready."""
        mock_health_status = HealthCheck(
            status=HealthStatus.UNHEALTHY,
            ready=False,
            details={"startup_complete": False},
        )

        with (
            patch.object(app, "state", Mock(cfg=None)),
            patch(
                "services.orchestrator.app._health_manager.get_health_status",
                new_callable=AsyncMock,
            ) as mock_get_health,
        ):
            mock_get_health.return_value = mock_health_status

            response = client.get("/health/ready")
            assert response.status_code == 503


class TestOrchestratorCapabilitiesEndpoint:
    """Test Orchestrator service capabilities endpoint."""

    @pytest.mark.unit
    def test_capabilities_endpoint(self, client):
        """Test /api/v1/capabilities endpoint returns capabilities."""
        response = client.get("/api/v1/capabilities")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "orchestrator"
        assert data["version"] == "1.0.0"
        assert "capabilities" in data
        assert isinstance(data["capabilities"], list)
        assert len(data["capabilities"]) > 0

        # Check first capability structure
        capability = data["capabilities"][0]
        assert "name" in capability
        assert "description" in capability
        assert "parameters" in capability


class TestOrchestratorStatusEndpoint:
    """Test Orchestrator service status endpoint."""

    @pytest.mark.unit
    def test_status_endpoint(self, client):
        """Test /api/v1/status endpoint returns status."""
        response = client.get("/api/v1/status")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "orchestrator"
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert "connections" in data
        assert isinstance(data["connections"], list)

        # Check connection structure
        if data["connections"]:
            connection = data["connections"][0]
            assert "service" in connection
            assert "status" in connection
            assert "url" in connection


class TestOrchestratorProcessTranscriptEndpoint:
    """Test Orchestrator service process transcript endpoint."""

    @pytest.mark.unit
    @patch("services.orchestrator.app.process_with_langchain")
    @patch("services.orchestrator.app.create_resilient_client")
    def test_process_transcript_success(
        self, mock_create_client, mock_process_langchain, client, mock_app_state
    ):
        """Test /api/v1/transcripts endpoint with successful processing."""
        # Mock guardrails client for input validation
        mock_guardrails_input_client = AsyncMock()
        mock_guardrails_input_response = Mock()
        mock_guardrails_input_response.json.return_value = {
            "safe": True,
            "sanitized": "Hello",
        }
        mock_guardrails_input_client.post_with_retry = AsyncMock(
            return_value=mock_guardrails_input_response
        )
        mock_guardrails_input_client.close = AsyncMock()

        # Mock guardrails client for output validation
        mock_guardrails_output_client = AsyncMock()
        mock_guardrails_output_response = Mock()
        mock_guardrails_output_response.json.return_value = {
            "safe": True,
            "filtered": "Hello, how can I help you?",
        }
        mock_guardrails_output_client.post_with_retry = AsyncMock(
            return_value=mock_guardrails_output_response
        )
        mock_guardrails_output_client.close = AsyncMock()

        # Make create_resilient_client return different clients for different calls
        mock_create_client.side_effect = [
            mock_guardrails_input_client,
            mock_guardrails_output_client,
        ]

        # Mock LangChain processing (async function)
        mock_process_langchain.return_value = "Hello, how can I help you?"

        # Mock TTS client
        mock_tts_client = AsyncMock()
        mock_tts_client.synthesize = AsyncMock(return_value=b"fake_audio_data")
        mock_app_state.tts_client = mock_tts_client
        mock_app_state.langchain_executor = Mock()
        mock_app_state.llm_metrics = {}

        with patch.object(app, "state", mock_app_state):
            response = client.post(
                "/api/v1/transcripts",
                json={
                    "transcript": "Hello",
                    "user_id": "test_user",
                    "channel_id": "test_channel",
                    "correlation_id": "test_correlation",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "response_text" in data
            assert data["correlation_id"] == "test_correlation"

    @pytest.mark.unit
    @patch("services.orchestrator.app.create_resilient_client")
    def test_process_transcript_guardrails_blocked(
        self, mock_create_client, client, mock_app_state
    ):
        """Test /api/v1/transcripts endpoint with guardrails blocking input."""
        # Mock guardrails client returning blocked response
        mock_guardrails_client = AsyncMock()
        mock_guardrails_response = Mock()
        mock_guardrails_response.json.return_value = {
            "safe": False,
            "reason": "toxicity_detected",
        }
        mock_guardrails_client.post_with_retry = AsyncMock(
            return_value=mock_guardrails_response
        )
        mock_guardrails_client.close = AsyncMock()
        mock_create_client.return_value = mock_guardrails_client

        mock_app_state.langchain_executor = Mock()
        mock_app_state.llm_metrics = {}

        with patch.object(app, "state", mock_app_state):
            response = client.post(
                "/api/v1/transcripts",
                json={
                    "transcript": "test input",
                    "user_id": "test_user",
                    "channel_id": "test_channel",
                    "correlation_id": "test_correlation",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data
            assert data["correlation_id"] == "test_correlation"

    @pytest.mark.unit
    def test_process_transcript_missing_required_fields(self, client):
        """Test /api/v1/transcripts endpoint with missing required fields."""
        response = client.post(
            "/api/v1/transcripts",
            json={
                "transcript": "Hello",
                # Missing user_id and channel_id
            },
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.unit
    def test_process_transcript_empty_transcript(self, client):
        """Test /api/v1/transcripts endpoint with empty transcript."""
        response = client.post(
            "/api/v1/transcripts",
            json={
                "transcript": "",
                "user_id": "test_user",
                "channel_id": "test_channel",
            },
        )

        # Should still process (empty string is valid)
        assert response.status_code in [200, 422]
