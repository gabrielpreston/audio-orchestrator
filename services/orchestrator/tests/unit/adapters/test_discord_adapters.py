"""Unit tests for Discord adapters."""

import pytest
from unittest.mock import Mock, AsyncMock

from services.orchestrator.adapters.discord_input import DiscordAudioInputAdapter
from services.orchestrator.adapters.discord_output import DiscordAudioOutputAdapter
from services.orchestrator.adapters.types import AdapterConfig, AudioChunk, AudioMetadata


class TestDiscordAudioInputAdapter:
    """Test DiscordAudioInputAdapter class."""
    
    def test_discord_input_adapter_creation(self):
        """Test creating a Discord input adapter."""
        config = AdapterConfig(
            adapter_type="discord",
            name="discord_input"
        )
        adapter = DiscordAudioInputAdapter(config)
        
        assert adapter.name == "discord_audio_input"
        assert adapter.config == config
        assert not adapter.is_capturing
    
    @pytest.mark.asyncio
    async def test_discord_input_adapter_start_capture(self):
        """Test starting capture."""
        config = AdapterConfig(
            adapter_type="discord",
            name="discord_input"
        )
        adapter = DiscordAudioInputAdapter(config)
        
        await adapter.start_capture()
        
        assert adapter.is_capturing is True
    
    @pytest.mark.asyncio
    async def test_discord_input_adapter_stop_capture(self):
        """Test stopping capture."""
        config = AdapterConfig(
            adapter_type="discord",
            name="discord_input"
        )
        adapter = DiscordAudioInputAdapter(config)
        
        await adapter.start_capture()
        await adapter.stop_capture()
        
        assert adapter.is_capturing is False
    
    @pytest.mark.asyncio
    async def test_discord_input_adapter_get_audio_stream(self):
        """Test getting audio stream."""
        config = AdapterConfig(
            adapter_type="discord",
            name="discord_input"
        )
        adapter = DiscordAudioInputAdapter(config)
        
        await adapter.start_capture()
        
        # Get a few audio chunks
        chunks = []
        async for chunk in adapter.get_audio_stream():
            chunks.append(chunk)
            if len(chunks) >= 3:  # Limit to 3 chunks for testing
                break
        
        await adapter.stop_capture()
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, AudioChunk) for chunk in chunks)
        assert all(chunk.correlation_id.startswith("discord_") for chunk in chunks)
    
    @pytest.mark.asyncio
    async def test_discord_input_adapter_get_capabilities(self):
        """Test getting capabilities."""
        config = AdapterConfig(
            adapter_type="discord",
            name="discord_input"
        )
        adapter = DiscordAudioInputAdapter(config)
        
        capabilities = await adapter.get_capabilities()
        
        assert capabilities["adapter_type"] == "discord"
        assert capabilities["name"] == "discord_audio_input"
        assert capabilities["can_capture"] is True
        assert capabilities["supports_streaming"] is True
        assert capabilities["platform"] == "discord"
        assert capabilities["supports_voice_channels"] is True
    
    @pytest.mark.asyncio
    async def test_discord_input_adapter_health_check(self):
        """Test health check."""
        config = AdapterConfig(
            adapter_type="discord",
            name="discord_input"
        )
        adapter = DiscordAudioInputAdapter(config)
        
        health = await adapter.health_check()
        
        assert health["adapter_name"] == "discord_audio_input"
        assert health["adapter_type"] == "discord"
        assert health["enabled"] is True
        assert "discord_connected" in health
        assert "voice_channel_connected" in health
        assert "audio_queue_size" in health


class TestDiscordAudioOutputAdapter:
    """Test DiscordAudioOutputAdapter class."""
    
    def test_discord_output_adapter_creation(self):
        """Test creating a Discord output adapter."""
        config = AdapterConfig(
            adapter_type="discord",
            name="discord_output"
        )
        adapter = DiscordAudioOutputAdapter(config)
        
        assert adapter.name == "discord_audio_output"
        assert adapter.config == config
        assert not adapter.is_playing
    
    @pytest.mark.asyncio
    async def test_discord_output_adapter_start_playback(self):
        """Test starting playback."""
        config = AdapterConfig(
            adapter_type="discord",
            name="discord_output"
        )
        adapter = DiscordAudioOutputAdapter(config)
        
        await adapter.start_playback()
        
        assert adapter.is_playing is True
    
    @pytest.mark.asyncio
    async def test_discord_output_adapter_stop_playback(self):
        """Test stopping playback."""
        config = AdapterConfig(
            adapter_type="discord",
            name="discord_output"
        )
        adapter = DiscordAudioOutputAdapter(config)
        
        await adapter.start_playback()
        await adapter.stop_playback()
        
        assert adapter.is_playing is False
    
    @pytest.mark.asyncio
    async def test_discord_output_adapter_play_audio(self):
        """Test playing audio chunk."""
        config = AdapterConfig(
            adapter_type="discord",
            name="discord_output"
        )
        adapter = DiscordAudioOutputAdapter(config)
        
        await adapter.start_playback()
        
        # Create a mock audio chunk
        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.1,
            frames=4800,
            format="pcm",
            bit_depth=16
        )
        
        audio_chunk = AudioChunk(
            data=b'\x00' * 1024,
            metadata=metadata,
            correlation_id="test-123",
            sequence_number=1
        )
        
        # This should not raise an exception
        await adapter.play_audio(audio_chunk)
        
        await adapter.stop_playback()
    
    @pytest.mark.asyncio
    async def test_discord_output_adapter_play_audio_stream(self):
        """Test playing audio stream."""
        config = AdapterConfig(
            adapter_type="discord",
            name="discord_output"
        )
        adapter = DiscordAudioOutputAdapter(config)
        
        await adapter.start_playback()
        
        # Create mock audio chunks
        metadata = AudioMetadata(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            duration=0.1,
            frames=4800,
            format="pcm",
            bit_depth=16
        )
        
        async def mock_audio_stream():
            for i in range(3):
                yield AudioChunk(
                    data=b'\x00' * 1024,
                    metadata=metadata,
                    correlation_id=f"test-{i}",
                    sequence_number=i
                )
        
        # This should not raise an exception
        await adapter.play_audio_stream(mock_audio_stream())
        
        await adapter.stop_playback()
    
    @pytest.mark.asyncio
    async def test_discord_output_adapter_get_capabilities(self):
        """Test getting capabilities."""
        config = AdapterConfig(
            adapter_type="discord",
            name="discord_output"
        )
        adapter = DiscordAudioOutputAdapter(config)
        
        capabilities = await adapter.get_capabilities()
        
        assert capabilities["adapter_type"] == "discord"
        assert capabilities["name"] == "discord_audio_output"
        assert capabilities["can_play"] is True
        assert capabilities["supports_streaming"] is True
        assert capabilities["platform"] == "discord"
        assert capabilities["supports_voice_channels"] is True
    
    @pytest.mark.asyncio
    async def test_discord_output_adapter_health_check(self):
        """Test health check."""
        config = AdapterConfig(
            adapter_type="discord",
            name="discord_output"
        )
        adapter = DiscordAudioOutputAdapter(config)
        
        health = await adapter.health_check()
        
        assert health["adapter_name"] == "discord_audio_output"
        assert health["adapter_type"] == "discord"
        assert health["enabled"] is True
        assert "discord_connected" in health
        assert "voice_channel_connected" in health
        assert "playback_queue_size" in health
