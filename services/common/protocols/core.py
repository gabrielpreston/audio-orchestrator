"""Core protocols for service components."""

from typing import Protocol, Any, runtime_checkable


@runtime_checkable
class LifecycleProtocol(Protocol):
    """Protocol for service/component lifecycle management.

    Runtime checkable for isinstance() validation.
    """

    async def initialize(self) -> None: ...
    async def cleanup(self) -> None: ...


@runtime_checkable
class HealthProtocol(Protocol):
    """Protocol for health checking.

    Runtime checkable for health check validation.
    """

    async def check_health(self) -> dict[str, Any]: ...
    async def get_metrics(self) -> dict[str, Any]: ...


class ConfigurableProtocol(Protocol):
    """Protocol for configurable components.

    Compile-time only - no runtime checking needed.
    """

    def get_config(self, key: str, default: Any = None) -> Any: ...
    def validate_config(self) -> bool: ...
