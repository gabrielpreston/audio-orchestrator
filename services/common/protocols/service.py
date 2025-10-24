"""Service communication protocols."""

from typing import Protocol, Any
from collections.abc import AsyncIterator


class ServiceDiscoveryProtocol(Protocol):
    """Protocol for service discovery."""

    async def discover_services(self) -> list[dict[str, Any]]: ...
    async def register_service(self, info: dict[str, Any]) -> None: ...


class ServiceCommunicationProtocol(Protocol):
    """Protocol for inter-service communication."""

    async def send_request(
        self, endpoint: str, data: dict[str, Any]
    ) -> dict[str, Any]: ...
    async def stream_data(self, endpoint: str) -> AsyncIterator[dict[str, Any]]: ...
