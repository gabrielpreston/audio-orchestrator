"""Mock Discord client for testing."""

from typing import Any, Dict, List, Optional
from unittest import mock

import discord
from discord.ext import voice_recv


class MockDiscordClient:
    """Mock Discord client for testing."""
    
    def __init__(self, **kwargs):
        self.user = mock.Mock(spec=discord.User)
        self.user.id = kwargs.get('user_id', 123456789)
        self.user.name = kwargs.get('user_name', 'TestBot')
        self.user.discriminator = kwargs.get('user_discriminator', '0001')
        
        self.guilds = []
        self.voice_clients = []
        self._is_ready = False
        self._is_closed = False
        
        # Mock event handlers
        self._event_handlers = {}
    
    async def start(self, token: str) -> None:
        """Mock start method."""
        self._is_ready = True
        if 'on_ready' in self._event_handlers:
            await self._event_handlers['on_ready']()
    
    async def close(self) -> None:
        """Mock close method."""
        self._is_closed = True
    
    def event(self, func):
        """Mock event decorator."""
        self._event_handlers[func.__name__] = func
        return func
    
    def get_guild(self, guild_id: int) -> Optional[mock.Mock]:
        """Get a guild by ID."""
        for guild in self.guilds:
            if guild.id == guild_id:
                return guild
        return None
    
    def get_channel(self, channel_id: int) -> Optional[mock.Mock]:
        """Get a channel by ID."""
        for guild in self.guilds:
            for channel in guild.channels:
                if channel.id == channel_id:
                    return channel
        return None
    
    def get_user(self, user_id: int) -> Optional[mock.Mock]:
        """Get a user by ID."""
        if user_id == self.user.id:
            return self.user
        return None


class MockGuild:
    """Mock Discord guild for testing."""
    
    def __init__(self, guild_id: int, name: str = "Test Guild"):
        self.id = guild_id
        self.name = name
        self.channels = []
        self.members = []
        self.voice_states = {}


class MockChannel:
    """Mock Discord channel for testing."""
    
    def __init__(self, channel_id: int, channel_type: str = "text", guild_id: Optional[int] = None):
        self.id = channel_id
        self.type = channel_type
        self.guild_id = guild_id
        self.name = f"test-{channel_type}-{channel_id}"


class MockVoiceChannel(MockChannel):
    """Mock Discord voice channel for testing."""
    
    def __init__(self, channel_id: int, guild_id: Optional[int] = None):
        super().__init__(channel_id, "voice", guild_id)
        self.bitrate = 64000
        self.user_limit = 0
        self.connected_members = []


class MockVoiceClient:
    """Mock Discord voice client for testing."""
    
    def __init__(self, channel: MockVoiceChannel, client: MockDiscordClient):
        self.channel = channel
        self.guild = channel.guild_id
        self.client = client
        self.is_connected = True
        self.is_playing = False
        self.is_paused = False
        self.source = None
        self.voice_recv = None
    
    async def connect(self, *, timeout: float = 60.0, reconnect: bool = True) -> None:
        """Mock connect method."""
        self.is_connected = True
    
    async def disconnect(self, *, force: bool = False) -> None:
        """Mock disconnect method."""
        self.is_connected = False
        if self.voice_recv:
            await self.voice_recv.stop()
    
    def play(self, source, *, after=None) -> None:
        """Mock play method."""
        self.source = source
        self.is_playing = True
        self.is_paused = False
    
    def stop(self) -> None:
        """Mock stop method."""
        self.source = None
        self.is_playing = False
        self.is_paused = False
    
    def pause(self) -> None:
        """Mock pause method."""
        self.is_paused = True
    
    def resume(self) -> None:
        """Mock resume method."""
        self.is_paused = False


class MockVoiceRecvClient:
    """Mock voice receiver client for testing."""
    
    def __init__(self, voice_client: MockVoiceClient):
        self.voice_client = voice_client
        self.is_listening = False
        self.listeners = []
    
    async def start(self) -> None:
        """Mock start method."""
        self.is_listening = True
    
    async def stop(self) -> None:
        """Mock stop method."""
        self.is_listening = False
    
    def listen(self, sink) -> None:
        """Mock listen method."""
        self.listeners.append(sink)


class MockAudioSink:
    """Mock audio sink for testing."""
    
    def __init__(self):
        self.audio_data = []
        self.is_cleanup = False
    
    def write(self, data: bytes, user: Any) -> None:
        """Mock write method."""
        self.audio_data.append((data, user))
    
    def cleanup(self) -> None:
        """Mock cleanup method."""
        self.is_cleanup = True


def create_mock_discord_client(**kwargs) -> MockDiscordClient:
    """Create a mock Discord client for testing.
    
    Args:
        **kwargs: Configuration options
        
    Returns:
        Mock Discord client
    """
    return MockDiscordClient(**kwargs)


def create_mock_guild(guild_id: int, name: str = "Test Guild") -> MockGuild:
    """Create a mock guild for testing.
    
    Args:
        guild_id: Guild ID
        name: Guild name
        
    Returns:
        Mock guild
    """
    return MockGuild(guild_id, name)


def create_mock_voice_channel(channel_id: int, guild_id: Optional[int] = None) -> MockVoiceChannel:
    """Create a mock voice channel for testing.
    
    Args:
        channel_id: Channel ID
        guild_id: Guild ID
        
    Returns:
        Mock voice channel
    """
    return MockVoiceChannel(channel_id, guild_id)


def create_mock_voice_client(channel: MockVoiceChannel, client: MockDiscordClient) -> MockVoiceClient:
    """Create a mock voice client for testing.
    
    Args:
        channel: Voice channel
        client: Discord client
        
    Returns:
        Mock voice client
    """
    return MockVoiceClient(channel, client)


def create_mock_voice_recv_client(voice_client: MockVoiceClient) -> MockVoiceRecvClient:
    """Create a mock voice receiver client for testing.
    
    Args:
        voice_client: Voice client
        
    Returns:
        Mock voice receiver client
    """
    return MockVoiceRecvClient(voice_client)


def create_mock_audio_sink() -> MockAudioSink:
    """Create a mock audio sink for testing.
    
    Returns:
        Mock audio sink
    """
    return MockAudioSink()