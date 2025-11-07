"""
Orchestrator client for Discord service to communicate with the LLM orchestrator.
"""

from types import TracebackType
from typing import Any

from services.common.http_client_factory import create_resilient_client
from services.common.resilient_http import ResilientHTTPClient, ServiceUnavailableError
from services.common.structured_logging import get_logger

logger = get_logger(__name__, service_name="discord")


class OrchestratorClient:
    """Client for communicating with the LLM orchestrator service."""

    def __init__(self, orchestrator_url: str = "http://orchestrator:8200"):
        self.orchestrator_url = orchestrator_url
        self._http_client: ResilientHTTPClient | None = None

    async def _get_http_client(self) -> ResilientHTTPClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = create_resilient_client(
                service_name="orchestrator",
                base_url=self.orchestrator_url,
                env_prefix="ORCHESTRATOR",
            )
        return self._http_client

    async def __aenter__(self) -> "OrchestratorClient":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        if self._http_client:
            await self._http_client.close()
            self._http_client = None

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

            # Pass correlation ID in headers (resilient client auto-injects from context too)
            headers = {}
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            response = await client.post_with_retry(
                "/api/v1/transcripts",
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

        except ServiceUnavailableError as exc:
            logger.exception(
                "discord.orchestrator_unavailable",
                error=str(exc),
                guild_id=guild_id,
                channel_id=channel_id,
                user_id=user_id,
                correlation_id=correlation_id,
            )
            return {"error": "Orchestrator service is currently unavailable"}
        except Exception as exc:
            logger.exception(
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

            response = await client.post_with_retry(
                "/api/v1/messages", json=payload, timeout=30.0
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

        except ServiceUnavailableError as exc:
            logger.exception(
                "discord.orchestrator_unavailable",
                error=str(exc),
                guild_id=guild_id,
                channel_id=channel_id,
            )
            return {"error": "Orchestrator service is currently unavailable"}
        except Exception as exc:
            logger.exception(
                "discord.message_send_failed",
                error=str(exc),
                guild_id=guild_id,
                channel_id=channel_id,
            )
            return {"error": str(exc)}

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.close()
            self._http_client = None
