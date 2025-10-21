"""
Tests for surface registry functionality.

This module validates that the surface registry correctly manages
surface configurations and adapters.
"""

from unittest.mock import Mock

from services.common.surfaces.config import (
    SurfaceCapabilities,
    SurfaceConfig,
    SurfaceStatus,
    SurfaceType,
)
from services.common.surfaces.interfaces import SurfaceAdapter
from services.common.surfaces.registry import RegistryStats, SurfaceRegistry


class TestRegistryStats:
    """Test RegistryStats data structure."""

    def test_registry_stats_creation(self):
        """Test creating RegistryStats with defaults."""
        stats = RegistryStats()

        assert stats.total_surfaces == 0
        assert stats.available_surfaces == 0
        assert stats.busy_surfaces == 0
        assert stats.unavailable_surfaces == 0
        assert stats.error_surfaces == 0
        assert stats.avg_discovery_time_ms == 0.0
        assert stats.total_discoveries == 0

    def test_registry_stats_to_dict(self):
        """Test converting RegistryStats to dictionary."""
        stats = RegistryStats()
        data = stats.to_dict()

        assert "total_surfaces" in data
        assert "available_surfaces" in data
        assert "busy_surfaces" in data
        assert "unavailable_surfaces" in data
        assert "error_surfaces" in data
        assert "avg_discovery_time_ms" in data
        assert "total_discoveries" in data


class TestSurfaceRegistry:
    """Test SurfaceRegistry functionality."""

    def test_surface_registry_creation(self):
        """Test creating SurfaceRegistry."""
        registry = SurfaceRegistry()

        assert len(registry._surfaces) == 0
        assert len(registry._adapters) == 0
        assert registry._stats.total_surfaces == 0

    def test_register_surface(self):
        """Test registering a surface."""
        registry = SurfaceRegistry()

        surface_config = SurfaceConfig(
            surface_id="test_surface",
            surface_type=SurfaceType.DISCORD,
            display_name="Test Surface",
            description="Test surface for testing",
        )

        success = registry.register_surface(surface_config)

        assert success is True
        assert "test_surface" in registry._surfaces
        assert registry._stats.total_surfaces == 1

    def test_register_surface_duplicate(self):
        """Test registering duplicate surface."""
        registry = SurfaceRegistry()

        surface_config = SurfaceConfig(
            surface_id="test_surface",
            surface_type=SurfaceType.DISCORD,
            display_name="Test Surface",
        )

        # Register first time
        success1 = registry.register_surface(surface_config)
        assert success1 is True

        # Try to register again
        success2 = registry.register_surface(surface_config)
        assert success2 is False

    def test_register_surface_invalid_config(self):
        """Test registering surface with invalid config."""
        registry = SurfaceRegistry()

        # Create invalid config (missing required fields)
        surface_config = SurfaceConfig(
            surface_id="",  # Invalid: empty ID
            surface_type=SurfaceType.DISCORD,
            display_name="",  # Invalid: empty display name
        )

        success = registry.register_surface(surface_config)
        assert success is False

    def test_unregister_surface(self):
        """Test unregistering a surface."""
        registry = SurfaceRegistry()

        # Register surface
        surface_config = SurfaceConfig(
            surface_id="test_surface",
            surface_type=SurfaceType.DISCORD,
            display_name="Test Surface",
        )
        registry.register_surface(surface_config)

        # Unregister surface
        success = registry.unregister_surface("test_surface")

        assert success is True
        assert "test_surface" not in registry._surfaces
        assert registry._stats.total_surfaces == 0

    def test_unregister_surface_not_found(self):
        """Test unregistering non-existent surface."""
        registry = SurfaceRegistry()

        success = registry.unregister_surface("non_existent")
        assert success is False

    def test_get_surface(self):
        """Test getting surface by ID."""
        registry = SurfaceRegistry()

        # Register surface
        surface_config = SurfaceConfig(
            surface_id="test_surface",
            surface_type=SurfaceType.DISCORD,
            display_name="Test Surface",
        )
        registry.register_surface(surface_config)

        # Get surface
        retrieved_surface = registry.get_surface("test_surface")

        assert retrieved_surface is not None
        assert retrieved_surface.surface_id == "test_surface"
        assert retrieved_surface.display_name == "Test Surface"

        # Test non-existent surface
        non_existent = registry.get_surface("non_existent")
        assert non_existent is None

    def test_get_surfaces_by_type(self):
        """Test getting surfaces by type."""
        registry = SurfaceRegistry()

        # Register surfaces of different types
        discord_surface = SurfaceConfig(
            surface_id="discord1",
            surface_type=SurfaceType.DISCORD,
            display_name="Discord Surface 1",
        )
        web_surface = SurfaceConfig(
            surface_id="web1",
            surface_type=SurfaceType.WEB,
            display_name="Web Surface 1",
        )
        discord_surface2 = SurfaceConfig(
            surface_id="discord2",
            surface_type=SurfaceType.DISCORD,
            display_name="Discord Surface 2",
        )

        registry.register_surface(discord_surface)
        registry.register_surface(web_surface)
        registry.register_surface(discord_surface2)

        # Get Discord surfaces
        discord_surfaces = registry.get_surfaces_by_type(SurfaceType.DISCORD)
        assert len(discord_surfaces) == 2
        assert discord_surface.surface_id in [s.surface_id for s in discord_surfaces]
        assert discord_surface2.surface_id in [s.surface_id for s in discord_surfaces]

        # Get Web surfaces
        web_surfaces = registry.get_surfaces_by_type(SurfaceType.WEB)
        assert len(web_surfaces) == 1
        assert web_surface.surface_id in [s.surface_id for s in web_surfaces]

    def test_get_available_surfaces(self):
        """Test getting available surfaces."""
        registry = SurfaceRegistry()

        # Register surfaces with different statuses
        available_surface = SurfaceConfig(
            surface_id="available",
            surface_type=SurfaceType.DISCORD,
            display_name="Available Surface",
            status=SurfaceStatus.AVAILABLE,
        )
        busy_surface = SurfaceConfig(
            surface_id="busy",
            surface_type=SurfaceType.DISCORD,
            display_name="Busy Surface",
            status=SurfaceStatus.BUSY,
        )

        registry.register_surface(available_surface)
        registry.register_surface(busy_surface)

        # Get available surfaces
        available_surfaces = registry.get_available_surfaces()
        assert len(available_surfaces) == 1
        assert available_surface.surface_id in [s.surface_id for s in available_surfaces]

    def test_get_healthy_surfaces(self):
        """Test getting healthy surfaces."""
        registry = SurfaceRegistry()

        # Register surfaces with different statuses
        healthy_surface = SurfaceConfig(
            surface_id="healthy",
            surface_type=SurfaceType.DISCORD,
            display_name="Healthy Surface",
            status=SurfaceStatus.AVAILABLE,
        )
        error_surface = SurfaceConfig(
            surface_id="error",
            surface_type=SurfaceType.DISCORD,
            display_name="Error Surface",
            status=SurfaceStatus.ERROR,
        )

        registry.register_surface(healthy_surface)
        registry.register_surface(error_surface)

        # Get healthy surfaces
        healthy_surfaces = registry.get_healthy_surfaces()
        assert len(healthy_surfaces) == 1
        assert healthy_surface.surface_id in [s.surface_id for s in healthy_surfaces]

    def test_get_surfaces_by_capability(self):
        """Test getting surfaces by capability."""
        registry = SurfaceRegistry()

        # Register surfaces with different capabilities
        audio_surface = SurfaceConfig(
            surface_id="audio",
            surface_type=SurfaceType.DISCORD,
            display_name="Audio Surface",
            capabilities=SurfaceCapabilities(supports_audio_input=True),
        )
        no_audio_surface = SurfaceConfig(
            surface_id="no_audio",
            surface_type=SurfaceType.DISCORD,
            display_name="No Audio Surface",
            capabilities=SurfaceCapabilities(supports_audio_input=False),
        )

        registry.register_surface(audio_surface)
        registry.register_surface(no_audio_surface)

        # Get surfaces with audio input capability
        audio_surfaces = registry.get_surfaces_by_capability("audio_input")
        assert len(audio_surfaces) == 1
        assert audio_surface.surface_id in [s.surface_id for s in audio_surfaces]

    def test_get_surfaces_by_priority(self):
        """Test getting surfaces by priority."""
        registry = SurfaceRegistry()

        # Register surfaces with different priorities
        high_priority_surface = SurfaceConfig(
            surface_id="high_priority",
            surface_type=SurfaceType.DISCORD,
            display_name="High Priority Surface",
            priority=10,
        )
        low_priority_surface = SurfaceConfig(
            surface_id="low_priority",
            surface_type=SurfaceType.DISCORD,
            display_name="Low Priority Surface",
            priority=1,
        )

        registry.register_surface(high_priority_surface)
        registry.register_surface(low_priority_surface)

        # Get surfaces with priority >= 5
        high_priority_surfaces = registry.get_surfaces_by_priority(5)
        assert len(high_priority_surfaces) == 1
        assert high_priority_surface.surface_id in [s.surface_id for s in high_priority_surfaces]

    def test_update_surface_status(self):
        """Test updating surface status."""
        registry = SurfaceRegistry()

        # Register surface
        surface_config = SurfaceConfig(
            surface_id="test_surface",
            surface_type=SurfaceType.DISCORD,
            display_name="Test Surface",
            status=SurfaceStatus.AVAILABLE,
        )
        registry.register_surface(surface_config)

        # Update status
        success = registry.update_surface_status("test_surface", SurfaceStatus.BUSY)
        assert success is True

        # Verify status update
        updated_surface = registry.get_surface("test_surface")
        assert updated_surface is not None
        assert updated_surface.status == SurfaceStatus.BUSY

        # Test with non-existent surface
        success = registry.update_surface_status("non_existent", SurfaceStatus.BUSY)
        assert success is False

    def test_update_surface_config(self):
        """Test updating surface configuration."""
        registry = SurfaceRegistry()

        # Register surface
        surface_config = SurfaceConfig(
            surface_id="test_surface",
            surface_type=SurfaceType.DISCORD,
            display_name="Test Surface",
        )
        registry.register_surface(surface_config)

        # Update config
        new_config = {"timeout_ms": 5000.0, "retry_count": 5}
        success = registry.update_surface_config("test_surface", new_config)
        assert success is True

        # Verify config update
        updated_surface = registry.get_surface("test_surface")
        assert updated_surface is not None
        assert updated_surface.config["timeout_ms"] == 5000.0
        assert updated_surface.config["retry_count"] == 5

        # Test with non-existent surface
        success = registry.update_surface_config("non_existent", new_config)
        assert success is False

    def test_register_adapter(self):
        """Test registering a surface adapter."""
        registry = SurfaceRegistry()

        # Register surface first
        surface_config = SurfaceConfig(
            surface_id="test_surface",
            surface_type=SurfaceType.DISCORD,
            display_name="Test Surface",
        )
        registry.register_surface(surface_config)

        # Create mock adapter
        mock_adapter = Mock(spec=SurfaceAdapter)

        # Register adapter
        success = registry.register_adapter("test_surface", mock_adapter)
        assert success is True

        # Verify adapter registration
        retrieved_adapter = registry.get_adapter("test_surface")
        assert retrieved_adapter is mock_adapter

        # Test with non-existent surface
        success = registry.register_adapter("non_existent", mock_adapter)
        assert success is False

    def test_get_adapter(self):
        """Test getting surface adapter."""
        registry = SurfaceRegistry()

        # Register surface and adapter
        surface_config = SurfaceConfig(
            surface_id="test_surface",
            surface_type=SurfaceType.DISCORD,
            display_name="Test Surface",
        )
        registry.register_surface(surface_config)

        mock_adapter = Mock(spec=SurfaceAdapter)
        registry.register_adapter("test_surface", mock_adapter)

        # Get adapter
        retrieved_adapter = registry.get_adapter("test_surface")
        assert retrieved_adapter is mock_adapter

        # Test non-existent adapter
        non_existent = registry.get_adapter("non_existent")
        assert non_existent is None

    def test_unregister_adapter(self):
        """Test unregistering a surface adapter."""
        registry = SurfaceRegistry()

        # Register surface and adapter
        surface_config = SurfaceConfig(
            surface_id="test_surface",
            surface_type=SurfaceType.DISCORD,
            display_name="Test Surface",
        )
        registry.register_surface(surface_config)

        mock_adapter = Mock(spec=SurfaceAdapter)
        registry.register_adapter("test_surface", mock_adapter)

        # Unregister adapter
        success = registry.unregister_adapter("test_surface")
        assert success is True

        # Verify adapter removal
        retrieved_adapter = registry.get_adapter("test_surface")
        assert retrieved_adapter is None

        # Test with non-existent adapter
        success = registry.unregister_adapter("non_existent")
        assert success is False

    def test_discover_surfaces(self):
        """Test discovering surfaces."""
        registry = SurfaceRegistry()

        # This is a stub implementation, so it should return empty list
        discovered_surfaces = registry.discover_surfaces()
        assert isinstance(discovered_surfaces, list)

    def test_should_discover(self):
        """Test discovery timing check."""
        registry = SurfaceRegistry()

        # Initially should not need discovery
        assert registry.should_discover() is False

    def test_get_registry_stats(self):
        """Test getting registry statistics."""
        registry = SurfaceRegistry()

        # Register some surfaces
        surface1 = SurfaceConfig(
            surface_id="surface1",
            surface_type=SurfaceType.DISCORD,
            display_name="Surface 1",
            status=SurfaceStatus.AVAILABLE,
        )
        surface2 = SurfaceConfig(
            surface_id="surface2",
            surface_type=SurfaceType.WEB,
            display_name="Surface 2",
            status=SurfaceStatus.BUSY,
        )

        registry.register_surface(surface1)
        registry.register_surface(surface2)

        # Get stats
        stats = registry.get_registry_stats()

        assert stats.total_surfaces == 2
        assert stats.available_surfaces == 1
        assert stats.busy_surfaces == 1

    def test_get_all_surfaces(self):
        """Test getting all surfaces."""
        registry = SurfaceRegistry()

        # Register surfaces
        surface1 = SurfaceConfig(
            surface_id="surface1",
            surface_type=SurfaceType.DISCORD,
            display_name="Surface 1",
        )
        surface2 = SurfaceConfig(
            surface_id="surface2",
            surface_type=SurfaceType.WEB,
            display_name="Surface 2",
        )

        registry.register_surface(surface1)
        registry.register_surface(surface2)

        # Get all surfaces
        all_surfaces = registry.get_all_surfaces()
        assert len(all_surfaces) == 2
        assert surface1.surface_id in [s.surface_id for s in all_surfaces]
        assert surface2.surface_id in [s.surface_id for s in all_surfaces]

    def test_get_surface_count(self):
        """Test getting surface count."""
        registry = SurfaceRegistry()

        # Initially no surfaces
        assert registry.get_surface_count() == 0

        # Register surface
        surface = SurfaceConfig(
            surface_id="test_surface",
            surface_type=SurfaceType.DISCORD,
            display_name="Test Surface",
        )
        registry.register_surface(surface)

        # Now should have 1 surface
        assert registry.get_surface_count() == 1

    def test_get_adapter_count(self):
        """Test getting adapter count."""
        registry = SurfaceRegistry()

        # Initially no adapters
        assert registry.get_adapter_count() == 0

        # Register surface and adapter
        surface = SurfaceConfig(
            surface_id="test_surface",
            surface_type=SurfaceType.DISCORD,
            display_name="Test Surface",
        )
        registry.register_surface(surface)

        mock_adapter = Mock(spec=SurfaceAdapter)
        registry.register_adapter("test_surface", mock_adapter)

        # Now should have 1 adapter
        assert registry.get_adapter_count() == 1

    def test_is_surface_registered(self):
        """Test checking if surface is registered."""
        registry = SurfaceRegistry()

        # Initially not registered
        assert registry.is_surface_registered("test_surface") is False

        # Register surface
        surface = SurfaceConfig(
            surface_id="test_surface",
            surface_type=SurfaceType.DISCORD,
            display_name="Test Surface",
        )
        registry.register_surface(surface)

        # Now should be registered
        assert registry.is_surface_registered("test_surface") is True

    def test_is_adapter_registered(self):
        """Test checking if adapter is registered."""
        registry = SurfaceRegistry()

        # Initially not registered
        assert registry.is_adapter_registered("test_surface") is False

        # Register surface and adapter
        surface = SurfaceConfig(
            surface_id="test_surface",
            surface_type=SurfaceType.DISCORD,
            display_name="Test Surface",
        )
        registry.register_surface(surface)

        mock_adapter = Mock(spec=SurfaceAdapter)
        registry.register_adapter("test_surface", mock_adapter)

        # Now should be registered
        assert registry.is_adapter_registered("test_surface") is True

    def test_clear_registry(self):
        """Test clearing registry."""
        registry = SurfaceRegistry()

        # Register some surfaces and adapters
        surface = SurfaceConfig(
            surface_id="test_surface",
            surface_type=SurfaceType.DISCORD,
            display_name="Test Surface",
        )
        registry.register_surface(surface)

        mock_adapter = Mock(spec=SurfaceAdapter)
        registry.register_adapter("test_surface", mock_adapter)

        # Clear registry
        registry.clear_registry()

        # Should be empty now
        assert registry.get_surface_count() == 0
        assert registry.get_adapter_count() == 0
        assert registry._stats.total_surfaces == 0

    def test_export_config(self):
        """Test exporting registry configuration."""
        registry = SurfaceRegistry()

        # Register surface
        surface = SurfaceConfig(
            surface_id="test_surface",
            surface_type=SurfaceType.DISCORD,
            display_name="Test Surface",
        )
        registry.register_surface(surface)

        # Export config
        config = registry.export_config()

        assert "surfaces" in config
        assert "stats" in config
        assert "last_discovery" in config
        assert "discovery_interval" in config
        assert len(config["surfaces"]) == 1
        assert config["surfaces"][0]["surface_id"] == "test_surface"

    def test_import_config(self):
        """Test importing registry configuration."""
        registry = SurfaceRegistry()

        # Create config to import
        config = {
            "surfaces": [
                {
                    "surface_id": "imported_surface",
                    "surface_type": "discord",
                    "display_name": "Imported Surface",
                    "description": "Imported surface for testing",
                    "status": "available",
                    "priority": 5,
                    "capabilities": {
                        "supports_audio_input": True,
                        "supports_audio_output": True,
                    },
                    "config": {"timeout_ms": 5000.0},
                    "metadata": {"version": "1.0"},
                }
            ],
            "stats": {
                "total_surfaces": 1,
                "available_surfaces": 1,
                "busy_surfaces": 0,
                "unavailable_surfaces": 0,
                "error_surfaces": 0,
                "avg_discovery_time_ms": 0.0,
                "total_discoveries": 0,
            },
            "discovery_interval": 30.0,
        }

        # Import config
        success = registry.import_config(config)
        assert success is True

        # Verify import
        assert registry.get_surface_count() == 1
        imported_surface = registry.get_surface("imported_surface")
        assert imported_surface is not None
        assert imported_surface.display_name == "Imported Surface"
        assert imported_surface.priority == 5
        assert imported_surface.config["timeout_ms"] == 5000.0
