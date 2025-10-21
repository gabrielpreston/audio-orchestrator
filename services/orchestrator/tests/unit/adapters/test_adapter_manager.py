"""Unit tests for adapter manager."""

import pytest

from services.orchestrator.adapters.discord_input import DiscordAudioInputAdapter
from services.orchestrator.adapters.discord_output import DiscordAudioOutputAdapter
from services.orchestrator.adapters.manager import AdapterManager
from services.orchestrator.adapters.types import AdapterConfig


class TestAdapterManager:
    """Test AdapterManager class."""

    def test_adapter_manager_creation(self):
        """Test creating an adapter manager."""
        manager = AdapterManager()

        assert len(manager.list_input_adapters()) == 0
        assert len(manager.list_output_adapters()) == 0

    def test_register_input_adapter(self):
        """Test registering an input adapter."""
        manager = AdapterManager()
        config = AdapterConfig(adapter_type="discord", name="discord_input")
        adapter = DiscordAudioInputAdapter(config)

        manager.register_input_adapter(adapter)

        assert len(manager.list_input_adapters()) == 1
        assert "discord_audio_input" in manager.list_input_adapters()
        assert manager.get_input_adapter("discord_audio_input") == adapter

    def test_register_output_adapter(self):
        """Test registering an output adapter."""
        manager = AdapterManager()
        config = AdapterConfig(adapter_type="discord", name="discord_output")
        adapter = DiscordAudioOutputAdapter(config)

        manager.register_output_adapter(adapter)

        assert len(manager.list_output_adapters()) == 1
        assert "discord_audio_output" in manager.list_output_adapters()
        assert manager.get_output_adapter("discord_audio_output") == adapter

    def test_register_duplicate_input_adapter(self):
        """Test registering a duplicate input adapter."""
        manager = AdapterManager()
        config = AdapterConfig(adapter_type="discord", name="discord_input")
        adapter1 = DiscordAudioInputAdapter(config)
        adapter2 = DiscordAudioInputAdapter(config)

        manager.register_input_adapter(adapter1)

        with pytest.raises(
            ValueError,
            match="Input adapter 'discord_audio_input' is already registered",
        ):
            manager.register_input_adapter(adapter2)

    def test_register_duplicate_output_adapter(self):
        """Test registering a duplicate output adapter."""
        manager = AdapterManager()
        config = AdapterConfig(adapter_type="discord", name="discord_output")
        adapter1 = DiscordAudioOutputAdapter(config)
        adapter2 = DiscordAudioOutputAdapter(config)

        manager.register_output_adapter(adapter1)

        with pytest.raises(
            ValueError,
            match="Output adapter 'discord_audio_output' is already registered",
        ):
            manager.register_output_adapter(adapter2)

    def test_register_invalid_input_adapter(self):
        """Test registering an invalid input adapter."""
        manager = AdapterManager()

        with pytest.raises(
            ValueError, match="Adapter must be an AudioInputAdapter instance"
        ):
            manager.register_input_adapter("not_an_adapter")  # type: ignore

    def test_register_invalid_output_adapter(self):
        """Test registering an invalid output adapter."""
        manager = AdapterManager()

        with pytest.raises(
            ValueError, match="Adapter must be an AudioOutputAdapter instance"
        ):
            manager.register_output_adapter("not_an_adapter")  # type: ignore

    def test_get_nonexistent_input_adapter(self):
        """Test getting a nonexistent input adapter."""
        manager = AdapterManager()

        assert manager.get_input_adapter("nonexistent") is None

    def test_get_nonexistent_output_adapter(self):
        """Test getting a nonexistent output adapter."""
        manager = AdapterManager()

        assert manager.get_output_adapter("nonexistent") is None

    def test_unregister_input_adapter(self):
        """Test unregistering an input adapter."""
        manager = AdapterManager()
        config = AdapterConfig(adapter_type="discord", name="discord_input")
        adapter = DiscordAudioInputAdapter(config)

        manager.register_input_adapter(adapter)
        assert len(manager.list_input_adapters()) == 1

        result = manager.unregister_input_adapter("discord_audio_input")
        assert result is True
        assert len(manager.list_input_adapters()) == 0

        # Test unregistering nonexistent adapter
        result = manager.unregister_input_adapter("nonexistent")
        assert result is False

    def test_unregister_output_adapter(self):
        """Test unregistering an output adapter."""
        manager = AdapterManager()
        config = AdapterConfig(adapter_type="discord", name="discord_output")
        adapter = DiscordAudioOutputAdapter(config)

        manager.register_output_adapter(adapter)
        assert len(manager.list_output_adapters()) == 1

        result = manager.unregister_output_adapter("discord_audio_output")
        assert result is True
        assert len(manager.list_output_adapters()) == 0

        # Test unregistering nonexistent adapter
        result = manager.unregister_output_adapter("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_input_adapter_capabilities(self):
        """Test getting input adapter capabilities."""
        manager = AdapterManager()
        config = AdapterConfig(adapter_type="discord", name="discord_input")
        adapter = DiscordAudioInputAdapter(config)

        manager.register_input_adapter(adapter)

        capabilities = await manager.get_input_adapter_capabilities()

        assert "discord_audio_input" in capabilities
        assert capabilities["discord_audio_input"]["adapter_type"] == "discord"
        assert capabilities["discord_audio_input"]["name"] == "discord_audio_input"

    @pytest.mark.asyncio
    async def test_get_output_adapter_capabilities(self):
        """Test getting output adapter capabilities."""
        manager = AdapterManager()
        config = AdapterConfig(adapter_type="discord", name="discord_output")
        adapter = DiscordAudioOutputAdapter(config)

        manager.register_output_adapter(adapter)

        capabilities = await manager.get_output_adapter_capabilities()

        assert "discord_audio_output" in capabilities
        assert capabilities["discord_audio_output"]["adapter_type"] == "discord"
        assert capabilities["discord_audio_output"]["name"] == "discord_audio_output"

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        manager = AdapterManager()
        config = AdapterConfig(adapter_type="discord", name="discord_input")
        input_adapter = DiscordAudioInputAdapter(config)

        config_output = AdapterConfig(adapter_type="discord", name="discord_output")
        output_adapter = DiscordAudioOutputAdapter(config_output)

        manager.register_input_adapter(input_adapter)
        manager.register_output_adapter(output_adapter)

        health = await manager.health_check()

        assert health["manager_status"] == "healthy"
        assert health["total_input_adapters"] == 1
        assert health["total_output_adapters"] == 1
        assert "discord_audio_input" in health["input_adapters"]
        assert "discord_audio_output" in health["output_adapters"]

    def test_get_stats(self):
        """Test getting manager statistics."""
        manager = AdapterManager()
        config = AdapterConfig(adapter_type="discord", name="discord_input")
        input_adapter = DiscordAudioInputAdapter(config)

        config_output = AdapterConfig(adapter_type="discord", name="discord_output")
        output_adapter = DiscordAudioOutputAdapter(config_output)

        manager.register_input_adapter(input_adapter)
        manager.register_output_adapter(output_adapter)

        stats = manager.get_stats()

        assert stats["total_input_adapters"] == 1
        assert stats["total_output_adapters"] == 1
        assert "discord_audio_input" in stats["input_adapter_names"]
        assert "discord_audio_output" in stats["output_adapter_names"]
