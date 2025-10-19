"""
Surface registry for adapter discovery and configuration.

This module implements the surface registry that manages available
surface adapters and their configurations.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from services.common.logging import get_logger

from .config import SurfaceConfig, SurfaceStatus, SurfaceType
from .interfaces import SurfaceAdapter


logger = get_logger(__name__)


@dataclass
class RegistryStats:
    """Registry statistics."""

    total_surfaces: int = 0
    available_surfaces: int = 0
    busy_surfaces: int = 0
    unavailable_surfaces: int = 0
    error_surfaces: int = 0

    # Performance metrics
    avg_discovery_time_ms: float = 0.0
    total_discoveries: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_surfaces": self.total_surfaces,
            "available_surfaces": self.available_surfaces,
            "busy_surfaces": self.busy_surfaces,
            "unavailable_surfaces": self.unavailable_surfaces,
            "error_surfaces": self.error_surfaces,
            "avg_discovery_time_ms": self.avg_discovery_time_ms,
            "total_discoveries": self.total_discoveries,
        }


class SurfaceRegistry:
    """Registry for managing surface adapters."""

    def __init__(self) -> None:
        self._logger = get_logger(__name__)

        # Surface storage
        self._surfaces: dict[str, SurfaceConfig] = {}
        self._adapters: dict[str, SurfaceAdapter] = {}

        # Statistics
        self._stats = RegistryStats()

        # Discovery tracking
        self._last_discovery = 0.0
        self._discovery_interval = 30.0  # 30 seconds

    def register_surface(self, surface_config: SurfaceConfig) -> bool:
        """Register a surface configuration."""
        try:
            # Validate configuration
            errors = surface_config.validate()
            if errors:
                self._logger.warning(
                    "surface_registry.invalid_config",
                    surface_id=surface_config.surface_id,
                    errors=errors,
                )
                return False

            # Check for duplicate
            if surface_config.surface_id in self._surfaces:
                self._logger.warning(
                    "surface_registry.duplicate_surface",
                    surface_id=surface_config.surface_id,
                )
                return False

            # Register surface
            self._surfaces[surface_config.surface_id] = surface_config
            self._stats.total_surfaces += 1

            # Update availability stats
            self._update_availability_stats()

            self._logger.info(
                "surface_registry.surface_registered",
                surface_id=surface_config.surface_id,
                surface_type=surface_config.surface_type.value,
                display_name=surface_config.display_name,
            )

            return True

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error(
                "surface_registry.registration_failed",
                surface_id=surface_config.surface_id,
                error=str(e),
            )
            return False

    def unregister_surface(self, surface_id: str) -> bool:
        """Unregister a surface."""
        try:
            if surface_id not in self._surfaces:
                self._logger.warning(
                    "surface_registry.surface_not_found",
                    surface_id=surface_id,
                )
                return False

            # Remove surface
            surface_config = self._surfaces.pop(surface_id)
            self._stats.total_surfaces -= 1

            # Remove adapter if exists
            if surface_id in self._adapters:
                del self._adapters[surface_id]

            # Update availability stats
            self._update_availability_stats()

            self._logger.info(
                "surface_registry.surface_unregistered",
                surface_id=surface_id,
                surface_type=surface_config.surface_type.value,
            )

            return True

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error(
                "surface_registry.unregistration_failed",
                surface_id=surface_id,
                error=str(e),
            )
            return False

    def get_surface(self, surface_id: str) -> SurfaceConfig | None:
        """Get surface configuration by ID."""
        return self._surfaces.get(surface_id)

    def get_surfaces_by_type(self, surface_type: SurfaceType) -> list[SurfaceConfig]:
        """Get surfaces by type."""
        return [
            surface
            for surface in self._surfaces.values()
            if surface.surface_type == surface_type
        ]

    def get_available_surfaces(self) -> list[SurfaceConfig]:
        """Get all available surfaces."""
        return [
            surface for surface in self._surfaces.values() if surface.is_available()
        ]

    def get_healthy_surfaces(self) -> list[SurfaceConfig]:
        """Get all healthy surfaces."""
        return [surface for surface in self._surfaces.values() if surface.is_healthy()]

    def get_surfaces_by_capability(self, capability: str) -> list[SurfaceConfig]:
        """Get surfaces that support a specific capability."""
        return [
            surface
            for surface in self._surfaces.values()
            if surface.supports_feature(capability)
        ]

    def get_surfaces_by_priority(self, min_priority: int = 0) -> list[SurfaceConfig]:
        """Get surfaces with minimum priority."""
        return [
            surface
            for surface in self._surfaces.values()
            if surface.priority >= min_priority
        ]

    def update_surface_status(self, surface_id: str, status: SurfaceStatus) -> bool:
        """Update surface status."""
        surface = self._surfaces.get(surface_id)
        if not surface:
            self._logger.warning(
                "surface_registry.surface_not_found",
                surface_id=surface_id,
            )
            return False

        try:
            old_status = surface.status
            surface.status = status

            # Update availability stats
            self._update_availability_stats()

            self._logger.debug(
                "surface_registry.status_updated",
                surface_id=surface_id,
                old_status=old_status.value,
                new_status=status.value,
            )

            return True

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error(
                "surface_registry.status_update_failed",
                surface_id=surface_id,
                error=str(e),
            )
            return False

    def update_surface_config(self, surface_id: str, config: dict[str, Any]) -> bool:
        """Update surface configuration."""
        surface = self._surfaces.get(surface_id)
        if not surface:
            self._logger.warning(
                "surface_registry.surface_not_found",
                surface_id=surface_id,
            )
            return False

        try:
            # Update configuration
            surface.config.update(config)

            self._logger.debug(
                "surface_registry.config_updated",
                surface_id=surface_id,
                config_keys=list(config.keys()),
            )

            return True

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error(
                "surface_registry.config_update_failed",
                surface_id=surface_id,
                error=str(e),
            )
            return False

    def register_adapter(self, surface_id: str, adapter: SurfaceAdapter) -> bool:
        """Register a surface adapter."""
        if surface_id not in self._surfaces:
            self._logger.warning(
                "surface_registry.surface_not_found",
                surface_id=surface_id,
            )
            return False

        try:
            self._adapters[surface_id] = adapter

            self._logger.info(
                "surface_registry.adapter_registered",
                surface_id=surface_id,
            )

            return True

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error(
                "surface_registry.adapter_registration_failed",
                surface_id=surface_id,
                error=str(e),
            )
            return False

    def get_adapter(self, surface_id: str) -> SurfaceAdapter | None:
        """Get surface adapter by ID."""
        return self._adapters.get(surface_id)

    def unregister_adapter(self, surface_id: str) -> bool:
        """Unregister a surface adapter."""
        if surface_id not in self._adapters:
            return False

        try:
            del self._adapters[surface_id]

            self._logger.info(
                "surface_registry.adapter_unregistered",
                surface_id=surface_id,
            )

            return True

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error(
                "surface_registry.adapter_unregistration_failed",
                surface_id=surface_id,
                error=str(e),
            )
            return False

    def discover_surfaces(self) -> list[SurfaceConfig]:
        """Discover available surfaces."""
        start_time = time.time()

        try:
            # This is a stub implementation
            # In a real implementation, this would scan for available surfaces
            discovered_surfaces: list[SurfaceConfig] = []

            # Update discovery stats
            discovery_time = time.time() - start_time
            self._stats.total_discoveries += 1
            self._stats.avg_discovery_time_ms = (
                self._stats.avg_discovery_time_ms * (self._stats.total_discoveries - 1)
                + discovery_time * 1000
            ) / self._stats.total_discoveries

            self._last_discovery = time.time()

            self._logger.debug(
                "surface_registry.discovery_completed",
                discovered_count=len(discovered_surfaces),
                discovery_time_ms=discovery_time * 1000,
            )

            return discovered_surfaces

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("surface_registry.discovery_failed", error=str(e))
            return []

    def should_discover(self) -> bool:
        """Check if discovery should be performed."""
        current_time = time.time()
        return (current_time - self._last_discovery) > self._discovery_interval

    def get_registry_stats(self) -> RegistryStats:
        """Get registry statistics."""
        return self._stats

    def get_all_surfaces(self) -> list[SurfaceConfig]:
        """Get all registered surfaces."""
        return list(self._surfaces.values())

    def get_surface_count(self) -> int:
        """Get total number of registered surfaces."""
        return len(self._surfaces)

    def get_adapter_count(self) -> int:
        """Get total number of registered adapters."""
        return len(self._adapters)

    def is_surface_registered(self, surface_id: str) -> bool:
        """Check if surface is registered."""
        return surface_id in self._surfaces

    def is_adapter_registered(self, surface_id: str) -> bool:
        """Check if adapter is registered for surface."""
        return surface_id in self._adapters

    def clear_registry(self) -> None:
        """Clear all registered surfaces and adapters."""
        self._surfaces.clear()
        self._adapters.clear()
        self._stats = RegistryStats()

        self._logger.info("surface_registry.registry_cleared")

    def export_config(self) -> dict[str, Any]:
        """Export registry configuration."""
        return {
            "surfaces": [surface.to_dict() for surface in self._surfaces.values()],
            "stats": self._stats.to_dict(),
            "last_discovery": self._last_discovery,
            "discovery_interval": self._discovery_interval,
        }

    def import_config(self, config: dict[str, Any]) -> bool:
        """Import registry configuration."""
        try:
            # Clear existing registry
            self.clear_registry()

            # Import surfaces
            if "surfaces" in config:
                for surface_data in config["surfaces"]:
                    surface_config = SurfaceConfig.from_dict(surface_data)
                    self.register_surface(surface_config)

            # Import stats
            if "stats" in config:
                stats_data = config["stats"]
                self._stats = RegistryStats(
                    total_surfaces=stats_data.get("total_surfaces", 0),
                    available_surfaces=stats_data.get("available_surfaces", 0),
                    busy_surfaces=stats_data.get("busy_surfaces", 0),
                    unavailable_surfaces=stats_data.get("unavailable_surfaces", 0),
                    error_surfaces=stats_data.get("error_surfaces", 0),
                    avg_discovery_time_ms=stats_data.get("avg_discovery_time_ms", 0.0),
                    total_discoveries=stats_data.get("total_discoveries", 0),
                )

            # Import discovery settings
            if "discovery_interval" in config:
                self._discovery_interval = config["discovery_interval"]

            self._logger.info("surface_registry.config_imported")
            return True

        except (ValueError, TypeError, KeyError) as e:
            self._logger.error("surface_registry.config_import_failed", error=str(e))
            return False

    def _update_availability_stats(self) -> None:
        """Update availability statistics."""
        self._stats.available_surfaces = len(
            [
                surface
                for surface in self._surfaces.values()
                if surface.status == SurfaceStatus.AVAILABLE
            ]
        )

        self._stats.busy_surfaces = len(
            [
                surface
                for surface in self._surfaces.values()
                if surface.status == SurfaceStatus.BUSY
            ]
        )

        self._stats.unavailable_surfaces = len(
            [
                surface
                for surface in self._surfaces.values()
                if surface.status == SurfaceStatus.UNAVAILABLE
            ]
        )

        self._stats.error_surfaces = len(
            [
                surface
                for surface in self._surfaces.values()
                if surface.status == SurfaceStatus.ERROR
            ]
        )
