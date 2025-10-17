"""
Orchestrator client for Discord service to communicate with the LLM orchestrator.
"""

from typing import Any

import httpx

from services.common.logging import get_logger

logger = get_logger(__name__, service_name="discord")


class OrchestratorClient:
    """Client for communicating with the LLM orchestrator service."""

    def __init__(self, orchestrator_url: str = "http://orchestrator:8000"):
        self.orchestrator_url = orchestrator_url
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def process_transcript(
        self,
        guild_id: str,
        channel_id: str,
        user_id: str,
        transcript: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Send transcript to orchestrator for processing."""
        try:
            client = await self._get_http_client()

            payload = {
                "guild_id": guild_id,
                "channel_id": channel_id,
                "user_id": user_id,
                "transcript": transcript,
                "correlation_id": correlation_id,
            }

            # Pass correlation ID in headers
            headers = {}
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            response = await client.post(
                f"{self.orchestrator_url}/mcp/transcript",
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()

            result: dict[str, Any] = response.json()
            logger.info(
                "discord.transcript_sent_to_orchestrator",
                guild_id=guild_id,
                channel_id=channel_id,
                user_id=user_id,
                transcript=transcript,
                correlation_id=correlation_id,
            )

            return result

        except Exception as exc:
            logger.error(
                "discord.orchestrator_communication_failed",
                error=str(exc),
                guild_id=guild_id,
                channel_id=channel_id,
                user_id=user_id,
                correlation_id=correlation_id,
            )
            return {"error": str(exc)}

    async def send_message(
        self, guild_id: str, channel_id: str, message: str
    ) -> dict[str, Any]:
        """Send text message via orchestrator."""
        try:
            client = await self._get_http_client()

            payload = {
                "guild_id": guild_id,
                "channel_id": channel_id,
                "message": message,
            }

            response = await client.post(
                f"{self.orchestrator_url}/mcp/send_message", json=payload, timeout=30.0
            )
            response.raise_for_status()

            result: dict[str, Any] = response.json()
            logger.info(
                "discord.message_sent",
                guild_id=guild_id,
                channel_id=channel_id,
                message=message,
            )

            return result

        except Exception as exc:
            logger.error(
                "discord.message_send_failed",
                error=str(exc),
                guild_id=guild_id,
                channel_id=channel_id,
            )
            return {"error": str(exc)}

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
