"""Protocol-based configuration manager for audio-orchestrator.

This module provides a concrete implementation of configuration protocols,
enabling composition over inheritance for configuration management.
"""

from typing import Any

from services.common.structured_logging import get_logger

from .protocols import (
    ConfigurationSourceProtocol,
)


logger = get_logger(__name__)


class DefaultConfigurationManager:
    """Default implementation of configuration manager protocols.

    This provides a concrete implementation that can be used as a base
    for configuration management or as a standalone manager.
    """

    def __init__(self, source: ConfigurationSourceProtocol | None = None) -> None:
        """Initialize the configuration manager.

        Args:
            source: Configuration source protocol implementation
        """
        self._source = source
        self._config_cache: dict[str, Any] = {}
        self._logger = get_logger(self.__class__.__name__)

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        if key in self._config_cache:
            return self._config_cache[key]

        if self._source:
            try:
                config_data = self._source.load()
                value = config_data.get(key, default)
                self._config_cache[key] = value
                return value
            except Exception as e:
                self._logger.warning(
                    "Failed to load config from source",
                    extra={"key": key, "error": str(e)},
                )

        return default

    def set_config(self, key: str, value: Any) -> None:
        """Set a configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        self._config_cache[key] = value
        self._logger.debug("Configuration updated", extra={"key": key, "value": value})

    def reload_config(self) -> None:
        """Reload configuration from source."""
        if self._source:
            try:
                config_data = self._source.load()
                self._config_cache.update(config_data)
                self._logger.info("Configuration reloaded from source")
            except Exception as e:
                self._logger.error(
                    "Failed to reload configuration", extra={"error": str(e)}
                )

    def get_all_configs(self) -> dict[str, Any]:
        """Get all configuration values.

        Returns:
            Dictionary of all configuration values
        """
        if self._source:
            try:
                return self._source.load()
            except Exception as e:
                self._logger.warning(
                    "Failed to load all configs from source", extra={"error": str(e)}
                )

        return self._config_cache.copy()

    def get_service_config(self, service: str) -> dict[str, Any]:
        """Get service-specific configuration.

        Args:
            service: Service name

        Returns:
            Service configuration dictionary
        """
        service_key = f"{service}_config"
        return self.get_config(service_key, {}) or {}

    def validate_service_config(self, service: str) -> bool:
        """Validate service-specific configuration.

        Args:
            service: Service name

        Returns:
            True if configuration is valid, False otherwise
        """
        service_config = self.get_service_config(service)
        return bool(service_config)

    def update_service_config(self, service: str, config: dict[str, Any]) -> None:
        """Update service-specific configuration.

        Args:
            service: Service name
            config: Configuration dictionary
        """
        service_key = f"{service}_config"
        self.set_config(service_key, config)
        self._logger.info("Service configuration updated", extra={"service": service})
