"""End-to-end tests for voice pipeline with real Discord."""

import asyncio
import os
import time
from io import BytesIO

import httpx
import pytest


@pytest.mark.e2e
@pytest.mark.manual
class TestE2EVoicePipeline:
    """Test E2E voice pipeline with real Discord bot."""

    @pytest.fixture(autouse=True)
    def skip_if_no_discord_token(self):
        """Skip E2E tests if DISCORD_TOKEN is not set."""
        if not os.getenv("DISCORD_TOKEN"):
            pytest.skip("DISCORD_TOKEN not set, skipping E2E tests")

    async def test_real_discord_voice_capture_to_response(
        self,
        realistic_voice_audio,
        test_voice_context,
        test_voice_correlation_id,
        test_auth_token,
    ):
        """Test with real Discord bot: Join voice → Capture → Process → Respond"""
        # This test requires a real Discord bot token and manual setup
        # It should be run manually with: pytest -m e2e

        async with httpx.AsyncClient() as client:
            # Step 1: Verify Discord bot is running and healthy
            discord_response = await client.get(
                "http://discord:8001/health/ready", timeout=10.0
            )
            assert discord_response.status_code == 200
            discord_health = discord_response.json()
            assert discord_health["service"] == "discord"

            # Step 2: Test Discord REST API endpoints are accessible
            capabilities_response = await client.get(
                "http://discord:8001/api/v1/capabilities", timeout=10.0
            )
            assert capabilities_response.status_code == 200
            capabilities_data = capabilities_response.json()
            assert "capabilities" in capabilities_data
            assert len(capabilities_data["capabilities"]) > 0

            # Step 3: Test complete voice pipeline
            start_time = time.time()

            # STT transcription
            stt_files = {
                "file": ("test_voice.wav", BytesIO(realistic_voice_audio), "audio/wav")
            }
            stt_response = await client.post(
                "http://stt:9000/transcribe",
                files=stt_files,
                timeout=30.0,
            )
            assert stt_response.status_code == 200
            stt_data = stt_response.json()
            transcript = stt_data["text"]
            assert len(transcript) > 0

            # Orchestrator processing
            orch_response = await client.post(
                "http://orchestrator-enhanced:8200/api/v1/transcripts",
                json={
                    "guild_id": test_voice_context["guild_id"],
                    "channel_id": test_voice_context["channel_id"],
                    "user_id": test_voice_context["user_id"],
                    "transcript": transcript,
                    "correlation_id": test_voice_correlation_id,
                },
                timeout=60.0,
            )
            assert orch_response.status_code == 200
            orch_data = orch_response.json()
            assert "status" in orch_data

            # TTS synthesis
            tts_response = await client.post(
                "http://tts-bark:7100/synthesize",
                json={
                    "text": f"E2E test response to: {transcript}",
                    "voice": "en_US-lessac-medium",
                    "correlation_id": test_voice_correlation_id,
                },
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=30.0,
            )
            assert tts_response.status_code == 200
            assert tts_response.headers["content-type"] == "audio/wav"

            # Step 4: Test Discord message sending
            send_message_response = await client.post(
                "http://discord:8001/api/v1/messages",
                json={
                    "guild_id": test_voice_context["guild_id"],
                    "channel_id": test_voice_context["channel_id"],
                    "message": f"E2E test completed: {transcript}",
                },
                timeout=30.0,
            )
            assert send_message_response.status_code == 200
            message_data = send_message_response.json()
            assert message_data["status"] == "success"

            # Step 5: Validate end-to-end performance
            total_latency = time.time() - start_time
            assert (
                total_latency < 5.0
            ), f"E2E latency {total_latency:.3f}s exceeds 5s threshold"

            print("E2E Voice Pipeline Test Results:")
            print(f"  Transcript: {transcript}")
            print(f"  Total Latency: {total_latency:.3f}s")
            print(f"  Audio Output Size: {len(tts_response.content)} bytes")

    async def test_discord_bot_voice_channel_integration(
        self,
        test_voice_context,
        test_auth_token,
    ):
        """Test Discord bot voice channel integration (requires real bot)."""
        # This test simulates voice channel interaction
        # In a real scenario, the Discord bot would:
        # 1. Join a voice channel
        # 2. Capture audio from users
        # 3. Process through the pipeline
        # 4. Play back responses

        async with httpx.AsyncClient() as client:
            # Test voice channel simulation
            voice_simulation_data = {
                "guild_id": test_voice_context["guild_id"],
                "channel_id": test_voice_context["channel_id"],
                "user_id": test_voice_context["user_id"],
                "action": "join_voice_channel",
                "correlation_id": "voice-channel-test",
            }

            # Simulate voice channel join
            voice_response = await client.post(
                "http://discord:8001/api/v1/notifications/transcript",
                json={
                    **voice_simulation_data,
                    "transcript": "Voice channel integration test",
                },
                timeout=30.0,
            )
            assert voice_response.status_code == 200

            # Test voice channel message
            channel_message_response = await client.post(
                "http://discord:8001/api/v1/messages",
                json={
                    "guild_id": test_voice_context["guild_id"],
                    "channel_id": test_voice_context["channel_id"],
                    "message": "Voice channel integration test message",
                },
                timeout=30.0,
            )
            assert channel_message_response.status_code == 200

    async def test_discord_bot_error_recovery(
        self,
        test_voice_context,
        test_auth_token,
    ):
        """Test Discord bot error recovery scenarios."""
        async with httpx.AsyncClient() as client:
            # Test with invalid guild/channel IDs
            invalid_context_response = await client.post(
                "http://discord:8001/api/v1/messages",
                json={
                    "guild_id": "invalid_guild",
                    "channel_id": "invalid_channel",
                    "message": "Test message with invalid context",
                },
                timeout=10.0,
            )
            # Should handle gracefully
            assert invalid_context_response.status_code in [200, 400, 422]

            # Test with malformed transcript
            malformed_transcript_response = await client.post(
                "http://discord:8001/api/v1/notifications/transcript",
                json={
                    "guild_id": test_voice_context["guild_id"],
                    "channel_id": test_voice_context["channel_id"],
                    "user_id": test_voice_context["user_id"],
                    "transcript": "",  # Empty transcript
                    "correlation_id": "error-recovery-test",
                },
                timeout=30.0,
            )
            # Should handle empty transcript gracefully
            assert malformed_transcript_response.status_code in [200, 400, 422]

    async def test_discord_bot_concurrent_voice_requests(
        self,
        realistic_voice_audio,
        test_voice_context,
        test_auth_token,
    ):
        """Test Discord bot handling of concurrent voice requests."""
        import asyncio

        async def process_voice_request(request_id: int):
            async with httpx.AsyncClient() as client:
                # Simulate concurrent voice processing
                stt_files = {
                    "file": (
                        "test_voice.wav",
                        BytesIO(realistic_voice_audio),
                        "audio/wav",
                    )
                }

                # STT
                stt_response = await client.post(
                    "http://stt:9000/transcribe",
                    files=stt_files,
                    timeout=30.0,
                )
                if stt_response.status_code != 200:
                    return {"success": False, "request_id": request_id}

                transcript = stt_response.json()["text"]

                # Orchestrator
                orch_response = await client.post(
                    "http://orchestrator-enhanced:8200/api/v1/transcripts",
                    json={
                        "guild_id": test_voice_context["guild_id"],
                        "channel_id": test_voice_context["channel_id"],
                        "user_id": test_voice_context["user_id"],
                        "transcript": transcript,
                        "correlation_id": f"concurrent-e2e-{request_id}",
                    },
                    timeout=60.0,
                )
                if orch_response.status_code != 200:
                    return {"success": False, "request_id": request_id}

                # TTS
                tts_response = await client.post(
                    "http://tts-bark:7100/synthesize",
                    json={
                        "text": f"Concurrent E2E test {request_id}",
                        "voice": "en_US-lessac-medium",
                        "correlation_id": f"concurrent-e2e-{request_id}",
                    },
                    headers={"Authorization": f"Bearer {test_auth_token}"},
                    timeout=30.0,
                )
                if tts_response.status_code != 200:
                    return {"success": False, "request_id": request_id}

                # Discord message
                message_response = await client.post(
                    "http://discord:8001/api/v1/messages",
                    json={
                        "guild_id": test_voice_context["guild_id"],
                        "channel_id": test_voice_context["channel_id"],
                        "message": f"Concurrent E2E test {request_id} completed",
                    },
                    timeout=30.0,
                )

                return {
                    "success": message_response.status_code == 200,
                    "request_id": request_id,
                }

        # Process 3 concurrent E2E requests
        tasks = [process_voice_request(i) for i in range(3)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # At least 2 should succeed
        successful_results = [
            r for r in results if isinstance(r, dict) and r.get("success")
        ]
        assert (
            len(successful_results) >= 2
        ), f"Only {len(successful_results)} concurrent E2E requests succeeded"

    async def test_discord_bot_health_monitoring(self):
        """Test Discord bot health monitoring during E2E operations."""
        async with httpx.AsyncClient() as client:
            # Monitor health during operations
            health_checks = []

            for i in range(5):
                health_response = await client.get(
                    "http://discord:8001/health/ready", timeout=5.0
                )
                health_checks.append(
                    {
                        "check": i,
                        "status_code": health_response.status_code,
                        "healthy": health_response.status_code == 200,
                    }
                )
                await asyncio.sleep(1)  # Wait 1 second between checks

            # All health checks should pass
            healthy_checks = [h for h in health_checks if h["healthy"]]
            assert (
                len(healthy_checks) >= 4
            ), f"Only {len(healthy_checks)}/5 health checks passed"

            print("Discord Bot Health Monitoring:")
            for check in health_checks:
                print(f"  Check {check['check']}: {'✓' if check['healthy'] else '✗'}")

    async def test_discord_bot_correlation_tracking(
        self,
        realistic_voice_audio,
        test_voice_context,
        test_voice_correlation_id,
        test_auth_token,
    ):
        """Test correlation ID tracking through E2E Discord bot operations."""
        async with httpx.AsyncClient() as client:
            # Process voice request with specific correlation ID
            stt_files = {
                "file": ("test_voice.wav", BytesIO(realistic_voice_audio), "audio/wav")
            }

            # STT with correlation ID
            stt_response = await client.post(
                "http://stt:9000/transcribe",
                files=stt_files,
                timeout=30.0,
            )
            assert stt_response.status_code == 200
            stt_data = stt_response.json()
            assert "correlation_id" in stt_data

            # Use STT correlation ID for orchestrator
            orch_response = await client.post(
                "http://orchestrator-enhanced:8200/api/v1/transcripts",
                json={
                    "guild_id": test_voice_context["guild_id"],
                    "channel_id": test_voice_context["channel_id"],
                    "user_id": test_voice_context["user_id"],
                    "transcript": stt_data["text"],
                    "correlation_id": stt_data["correlation_id"],
                },
                timeout=60.0,
            )
            assert orch_response.status_code == 200
            orch_data = orch_response.json()
            assert orch_data.get("correlation_id") == stt_data["correlation_id"]

            # Use same correlation ID for TTS
            tts_response = await client.post(
                "http://tts-bark:7100/synthesize",
                json={
                    "text": "E2E correlation tracking test",
                    "voice": "en_US-lessac-medium",
                    "correlation_id": stt_data["correlation_id"],
                },
                headers={"Authorization": f"Bearer {test_auth_token}"},
                timeout=30.0,
            )
            assert tts_response.status_code == 200

            # Send Discord message with correlation ID
            message_response = await client.post(
                "http://discord:8001/api/v1/messages",
                json={
                    "guild_id": test_voice_context["guild_id"],
                    "channel_id": test_voice_context["channel_id"],
                    "message": f"E2E correlation test: {stt_data['correlation_id']}",
                },
                timeout=30.0,
            )
            assert message_response.status_code == 200

            print("E2E Correlation Tracking:")
            print(f"  STT Correlation ID: {stt_data['correlation_id']}")
            print(f"  Orchestrator Correlation ID: {orch_data.get('correlation_id')}")
            print(f"  Message Sent: {message_response.json()['status']}")
