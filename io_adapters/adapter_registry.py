"""Registry for managing I/O adapters."""

from typing import Dict, Type, Optional
from .audio_input_adapter import AudioInputAdapter
from .audio_output_adapter import AudioOutputAdapter


class AdapterRegistry:
    """Registry for managing audio I/O adapters."""

    def __init__(self):
        """Initialize the adapter registry."""
        self._input_adapters: Dict[str, Type[AudioInputAdapter]] = {}
        self._output_adapters: Dict[str, Type[AudioOutputAdapter]] = {}

    def register_input_adapter(self, name: str, adapter_class: Type[AudioInputAdapter]) -> None:
        """Register an audio input adapter.

        Args:
            name: The name to register the adapter under
            adapter_class: The adapter class to register
        """
        self._input_adapters[name] = adapter_class

    def register_output_adapter(self, name: str, adapter_class: Type[AudioOutputAdapter]) -> None:
        """Register an audio output adapter.

        Args:
            name: The name to register the adapter under
            adapter_class: The adapter class to register
        """
        self._output_adapters[name] = adapter_class

    def get_input_adapter(self, name: str) -> Optional[Type[AudioInputAdapter]]:
        """Get an input adapter by name.

        Args:
            name: The name of the adapter to retrieve

        Returns:
            The adapter class if found, None otherwise
        """
        return self._input_adapters.get(name)

    def get_output_adapter(self, name: str) -> Optional[Type[AudioOutputAdapter]]:
        """Get an output adapter by name.

        Args:
            name: The name of the adapter to retrieve

        Returns:
            The adapter class if found, None otherwise
        """
        return self._output_adapters.get(name)

    def list_input_adapters(self) -> list[str]:
        """List all registered input adapter names."""
        return list(self._input_adapters.keys())

    def list_output_adapters(self) -> list[str]:
        """List all registered output adapter names."""
        return list(self._output_adapters.keys())


# Global registry instance
registry = AdapterRegistry()


def register_input_adapter(name: str, adapter_class: Type[AudioInputAdapter]) -> None:
    """Convenience function to register an input adapter."""
    registry.register_input_adapter(name, adapter_class)


def register_output_adapter(name: str, adapter_class: Type[AudioOutputAdapter]) -> None:
    """Convenience function to register an output adapter."""
    registry.register_output_adapter(name, adapter_class)


def get_input_adapter(name: str) -> Optional[Type[AudioInputAdapter]]:
    """Convenience function to get an input adapter."""
    return registry.get_input_adapter(name)


def get_output_adapter(name: str) -> Optional[Type[AudioOutputAdapter]]:
    """Convenience function to get an output adapter."""
    return registry.get_output_adapter(name)
