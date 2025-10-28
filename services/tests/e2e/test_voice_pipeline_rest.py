"""End-to-end tests for voice pipeline with REST API."""

import time

import pytest
import httpx


@pytest.mark.e2e
class TestVoicePipelineRestAPI:
    """Test complete voice pipeline using REST API endpoints."""

    async def test_complete_voice_pipeline_rest_api(self):
        """Test complete voice pipeline: STT → Orchestrator → Discord → TTS."""
        async with httpx.AsyncClient() as client:
            # Step 1: Check service health
            services = [
                "http://stt:9000/health/ready",
                "http://orchestrator-enhanced:8200/health/ready",
                "http://discord:8001/health/ready",
                "http://tts-bark:7100/health/ready",
            ]

            for service_url in services:
                response = await client.get(service_url, timeout=10.0)
                assert response.status_code == 200

            # Step 2: Test service capabilities
            # Test Discord capabilities
            discord_capabilities = await client.get(
                "http://discord:8001/api/v1/capabilities", timeout=10.0
            )
            assert discord_capabilities.status_code == 200
            discord_data = discord_capabilities.json()
            assert "capabilities" in discord_data

            # Test Orchestrator capabilities
            orchestrator_capabilities = await client.get(
                "http://orchestrator-enhanced:8200/api/v1/capabilities", timeout=10.0
            )
            assert orchestrator_capabilities.status_code == 200
            orchestrator_data = orchestrator_capabilities.json()
            assert "capabilities" in orchestrator_data

            # Step 3: Test complete voice pipeline
            start_time = time.time()

            # Simulate audio transcription (using text input for testing)
            test_transcript = (
                "Hello, this is a test of the voice pipeline with REST API"
            )

            # Process transcript with orchestrator
            orchestrator_request = {
                "transcript": test_transcript,
                "user_id": "test_user_e2e",
                "channel_id": "test_channel_e2e",
                "correlation_id": "e2e_test_correlation",
                "metadata": {"test_type": "e2e_rest_api"},
            }

            orchestrator_response = await client.post(
                "http://orchestrator-enhanced:8200/api/v1/transcripts",
                json=orchestrator_request,
                timeout=30.0,
            )
            assert orchestrator_response.status_code == 200
            orchestrator_data = orchestrator_response.json()
            assert orchestrator_data["success"] is True
            assert "response_text" in orchestrator_data
            assert orchestrator_data["correlation_id"] == "e2e_test_correlation"

            # Send response message to Discord
            discord_message_request = {
                "channel_id": "test_channel_e2e",
                "content": orchestrator_data["response_text"],
                "correlation_id": "e2e_test_correlation",
            }

            discord_response = await client.post(
                "http://discord:8001/api/v1/messages",
                json=discord_message_request,
                timeout=30.0,
            )
            assert discord_response.status_code == 200
            discord_data = discord_response.json()
            assert discord_data["success"] is True
            assert discord_data["correlation_id"] == "e2e_test_correlation"

            # Send transcript notification to Discord
            discord_notification_request = {
                "transcript": test_transcript,
                "user_id": "test_user_e2e",
                "channel_id": "test_channel_e2e",
                "correlation_id": "e2e_test_correlation",
            }

            discord_notification_response = await client.post(
                "http://discord:8001/api/v1/notifications/transcript",
                json=discord_notification_request,
                timeout=30.0,
            )
            assert discord_notification_response.status_code == 200
            notification_data = discord_notification_response.json()
            assert notification_data["success"] is True

            # Step 4: Test TTS synthesis
            if orchestrator_data["response_text"]:
                tts_request = {
                    "text": orchestrator_data["response_text"],
                    "voice": "v2/en_speaker_0",
                }

                tts_response = await client.post(
                    "http://tts-bark:7100/synthesize", json=tts_request, timeout=30.0
                )
                assert tts_response.status_code == 200
                assert len(tts_response.content) > 0

            # Step 5: Verify pipeline timing
            pipeline_time = time.time() - start_time
            assert pipeline_time < 60.0  # Should complete within 60 seconds

    async def test_error_recovery_pipeline(self):
        """Test error recovery in the voice pipeline."""
        async with httpx.AsyncClient() as client:
            # Test with empty transcript
            empty_transcript_request = {
                "transcript": "",
                "user_id": "test_user_error",
                "channel_id": "test_channel_error",
                "correlation_id": "error_test_correlation",
            }

            response = await client.post(
                "http://orchestrator-enhanced:8200/api/v1/transcripts",
                json=empty_transcript_request,
                timeout=30.0,
            )

            # Should handle gracefully
            assert response.status_code in [200, 400, 422]

    async def test_correlation_id_propagation_e2e(self):
        """Test correlation ID propagation through entire pipeline."""
        async with httpx.AsyncClient() as client:
            correlation_id = "e2e_correlation_test_123"
            test_transcript = "Test correlation ID propagation through pipeline"

            # Process transcript
            orchestrator_request = {
                "transcript": test_transcript,
                "user_id": "test_user_correlation",
                "channel_id": "test_channel_correlation",
                "correlation_id": correlation_id,
            }

            orchestrator_response = await client.post(
                "http://orchestrator-enhanced:8200/api/v1/transcripts",
                json=orchestrator_request,
                timeout=30.0,
            )
            assert orchestrator_response.status_code == 200
            orchestrator_data = orchestrator_response.json()
            assert orchestrator_data["correlation_id"] == correlation_id

            # Send message
            discord_request = {
                "channel_id": "test_channel_correlation",
                "content": "Test correlation propagation",
                "correlation_id": correlation_id,
            }

            discord_response = await client.post(
                "http://discord:8001/api/v1/messages",
                json=discord_request,
                timeout=30.0,
            )
            assert discord_response.status_code == 200
            discord_data = discord_response.json()
            assert discord_data["correlation_id"] == correlation_id

            # Send notification
            notification_request = {
                "transcript": test_transcript,
                "user_id": "test_user_correlation",
                "channel_id": "test_channel_correlation",
                "correlation_id": correlation_id,
            }

            notification_response = await client.post(
                "http://discord:8001/api/v1/notifications/transcript",
                json=notification_request,
                timeout=30.0,
            )
            assert notification_response.status_code == 200
            notification_data = notification_response.json()
            assert notification_data["correlation_id"] == correlation_id

    async def test_service_status_monitoring(self):
        """Test service status monitoring endpoints."""
        async with httpx.AsyncClient() as client:
            # Test orchestrator status
            orchestrator_status = await client.get(
                "http://orchestrator-enhanced:8200/api/v1/status", timeout=10.0
            )
            assert orchestrator_status.status_code == 200
            status_data = orchestrator_status.json()
            assert status_data["service"] == "orchestrator_enhanced"
            assert status_data["status"] == "healthy"
            assert "connections" in status_data

            # Test Discord health
            discord_health = await client.get(
                "http://discord:8001/health/ready", timeout=10.0
            )
            assert discord_health.status_code == 200
            health_data = discord_health.json()
            assert health_data["service"] == "discord"
