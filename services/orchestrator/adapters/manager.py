"""Adapter manager for registration and selection.

This module provides the main interface for adapter management, including
adapter registration, selection, and coordination within the orchestrator service.
"""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

from .base import AudioInputAdapter, AudioOutputAdapter


logger = get_logger(__name__)


class AdapterManager:
    """Manages audio input and output adapters.

    This is the main interface for adapter management within the orchestrator.
    It handles adapter registration, selection, and coordination.
    """

    def __init__(self) -> None:
        """Initialize the adapter manager."""
        self._input_adapters: dict[str, AudioInputAdapter] = {}
        self._output_adapters: dict[str, AudioOutputAdapter] = {}
        self._logger = get_logger(__name__)

        self._logger.info("Adapter manager initialized")

    def register_input_adapter(self, adapter: AudioInputAdapter) -> None:
        """Register an audio input adapter.

        Args:
            adapter: Input adapter instance to register

        Raises:
            ValueError: If adapter name is already registered
        """
        if not isinstance(adapter, AudioInputAdapter):
            raise ValueError("Adapter must be an AudioInputAdapter instance")

        adapter_name = adapter.name
        if adapter_name in self._input_adapters:
            raise ValueError(f"Input adapter '{adapter_name}' is already registered")

        self._input_adapters[adapter_name] = adapter
        self._logger.info(
            "Input adapter registered",
            extra={
                "adapter_name": adapter_name,
                "adapter_type": adapter.config.adapter_type,
                "total_input_adapters": len(self._input_adapters),
            },
        )

    def register_output_adapter(self, adapter: AudioOutputAdapter) -> None:
        """Register an audio output adapter.

        Args:
            adapter: Output adapter instance to register

        Raises:
            ValueError: If adapter name is already registered
        """
        if not isinstance(adapter, AudioOutputAdapter):
            raise ValueError("Adapter must be an AudioOutputAdapter instance")

        adapter_name = adapter.name
        if adapter_name in self._output_adapters:
            raise ValueError(f"Output adapter '{adapter_name}' is already registered")

        self._output_adapters[adapter_name] = adapter
        self._logger.info(
            "Output adapter registered",
            extra={
                "adapter_name": adapter_name,
                "adapter_type": adapter.config.adapter_type,
                "total_output_adapters": len(self._output_adapters),
            },
        )

    def get_input_adapter(self, name: str) -> AudioInputAdapter | None:
        """Get an input adapter by name.

        Args:
            name: Adapter name to retrieve

        Returns:
            Input adapter instance if found, None otherwise
        """
        return self._input_adapters.get(name)

    def get_output_adapter(self, name: str) -> AudioOutputAdapter | None:
        """Get an output adapter by name.

        Args:
            name: Adapter name to retrieve

        Returns:
            Output adapter instance if found, None otherwise
        """
        return self._output_adapters.get(name)

    def list_input_adapters(self) -> list[str]:
        """List all registered input adapter names.

        Returns:
            List of input adapter names
        """
        return list(self._input_adapters.keys())

    def list_output_adapters(self) -> list[str]:
        """List all registered output adapter names.

        Returns:
            List of output adapter names
        """
        return list(self._output_adapters.keys())

    def unregister_input_adapter(self, name: str) -> bool:
        """Unregister an input adapter by name.

        Args:
            name: Adapter name to unregister

        Returns:
            True if adapter was unregistered, False if not found
        """
        if name not in self._input_adapters:
            return False

        del self._input_adapters[name]
        self._logger.info(
            "Input adapter unregistered",
            extra={
                "adapter_name": name,
                "total_input_adapters": len(self._input_adapters),
            },
        )
        return True

    def unregister_output_adapter(self, name: str) -> bool:
        """Unregister an output adapter by name.

        Args:
            name: Adapter name to unregister

        Returns:
            True if adapter was unregistered, False if not found
        """
        if name not in self._output_adapters:
            return False

        del self._output_adapters[name]
        self._logger.info(
            "Output adapter unregistered",
            extra={
                "adapter_name": name,
                "total_output_adapters": len(self._output_adapters),
            },
        )
        return True

    async def get_input_adapter_capabilities(self) -> dict[str, dict[str, Any]]:
        """Get capabilities of all registered input adapters.

        Returns:
            Dictionary mapping adapter names to their capabilities
        """
        capabilities = {}
        for adapter in self._input_adapters.values():
            try:
                adapter_capabilities = await adapter.get_capabilities()
                capabilities[adapter.name] = adapter_capabilities
            except Exception as e:
                self._logger.warning(
                    "Error getting input adapter capabilities",
                    extra={"adapter_name": adapter.name, "error": str(e)},
                )
                capabilities[adapter.name] = {"error": str(e)}

        return capabilities

    async def get_output_adapter_capabilities(self) -> dict[str, dict[str, Any]]:
        """Get capabilities of all registered output adapters.

        Returns:
            Dictionary mapping adapter names to their capabilities
        """
        capabilities = {}
        for adapter in self._output_adapters.values():
            try:
                adapter_capabilities = await adapter.get_capabilities()
                capabilities[adapter.name] = adapter_capabilities
            except Exception as e:
                self._logger.warning(
                    "Error getting output adapter capabilities",
                    extra={"adapter_name": adapter.name, "error": str(e)},
                )
                capabilities[adapter.name] = {"error": str(e)}

        return capabilities

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on all adapters.

        Returns:
            Health check results for all adapters
        """
        input_health = {}
        output_health = {}

        # Check input adapters
        for adapter in self._input_adapters.values():
            try:
                adapter_health = await adapter.health_check()
                input_health[adapter.name] = adapter_health
            except Exception as e:
                self._logger.warning(
                    "Error during input adapter health check",
                    extra={"adapter_name": adapter.name, "error": str(e)},
                )
                input_health[adapter.name] = {"status": "unhealthy", "error": str(e)}

        # Check output adapters
        for output_adapter in self._output_adapters.values():
            try:
                adapter_health = await output_adapter.health_check()
                output_health[output_adapter.name] = adapter_health
            except Exception as e:
                self._logger.warning(
                    "Error during output adapter health check",
                    extra={"adapter_name": output_adapter.name, "error": str(e)},
                )
                output_health[output_adapter.name] = {
                    "status": "unhealthy",
                    "error": str(e),
                }

        return {
            "manager_status": "healthy",
            "total_input_adapters": len(self._input_adapters),
            "total_output_adapters": len(self._output_adapters),
            "input_adapters": input_health,
            "output_adapters": output_health,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get manager statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_input_adapters": len(self._input_adapters),
            "total_output_adapters": len(self._output_adapters),
            "input_adapter_names": list(self._input_adapters.keys()),
            "output_adapter_names": list(self._output_adapters.keys()),
        }
