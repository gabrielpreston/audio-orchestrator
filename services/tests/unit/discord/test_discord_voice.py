"""Unit tests for VoiceBot._resolve_voice_state()."""

from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import discord
import pytest

from services.discord.discord_voice import VoiceBot


@pytest.mark.unit
@pytest.mark.asyncio
class TestResolveVoiceState:
    """Unit tests for _resolve_voice_state() method."""

    @pytest.fixture
    def mock_bot_config(self):
        """Create mock bot configuration."""
        config = Mock()
        config.discord = Mock()
        config.discord.intents = ["guilds", "guild_voice_states"]
        config.audio = Mock()
        config.telemetry = Mock()
        config.wake = Mock()
        config.stt = Mock()
        return config

    @pytest.fixture
    def mock_audio_processor_wrapper(self):
        """Create mock audio processor wrapper."""
        return Mock()

    @pytest.fixture
    def mock_wake_detector(self):
        """Create mock wake detector."""
        return Mock()

    @pytest.fixture
    def mock_transcript_publisher(self):
        """Create mock transcript publisher."""
        return AsyncMock()

    @pytest.fixture
    def voice_bot(
        self,
        mock_bot_config,
        mock_audio_processor_wrapper,
        mock_wake_detector,
        mock_transcript_publisher,
    ):
        """Create VoiceBot instance with mocked dependencies."""
        bot = VoiceBot(
            config=mock_bot_config,
            audio_processor_wrapper=mock_audio_processor_wrapper,
            wake_detector=mock_wake_detector,
            transcript_publisher=mock_transcript_publisher,
        )
        return bot

    async def test_resolve_voice_state_with_cached_member(self, voice_bot):
        """Test _resolve_voice_state() with member already cached."""
        # Setup: Create mock guild with cached member
        user_id = 12345
        guild = Mock(spec=discord.Guild)
        guild.id = 1001

        voice_state = Mock(spec=discord.VoiceState)
        voice_state.channel = Mock(spec=discord.VoiceChannel)
        voice_state.channel.id = 2001

        member = Mock(spec=discord.Member)
        member.id = user_id
        member.voice = voice_state

        guild.get_member = Mock(return_value=member)
        with patch.object(
            type(voice_bot), "guilds", new_callable=PropertyMock, return_value=[guild]
        ):
            # Execute
            result = await voice_bot._resolve_voice_state(user_id)

        # Verify
        assert result == voice_state
        guild.get_member.assert_called_once_with(user_id)

    async def test_resolve_voice_state_with_uncached_member_fetch_success(
        self, voice_bot
    ):
        """Test _resolve_voice_state() with uncached member that is successfully fetched."""
        # Setup: Create mock guild without cached member
        user_id = 12345
        guild = Mock(spec=discord.Guild)
        guild.id = 1001

        voice_state = Mock(spec=discord.VoiceState)
        voice_state.channel = Mock(spec=discord.VoiceChannel)
        voice_state.channel.id = 2001

        member = Mock(spec=discord.Member)
        member.id = user_id
        member.voice = voice_state

        # First call returns None (not cached), second call (after fetch) returns member
        guild.get_member = Mock(return_value=None)
        guild.fetch_member = AsyncMock(return_value=member)
        with patch.object(
            type(voice_bot), "guilds", new_callable=PropertyMock, return_value=[guild]
        ):
            # Execute
            result = await voice_bot._resolve_voice_state(user_id)

        # Verify
        assert result == voice_state
        guild.get_member.assert_called_once_with(user_id)
        guild.fetch_member.assert_called_once_with(user_id)

    async def test_resolve_voice_state_with_member_not_found(self, voice_bot):
        """Test _resolve_voice_state() when member is not found in guild."""
        # Setup: Create mock guild where member fetch fails
        user_id = 12345
        guild = Mock(spec=discord.Guild)
        guild.id = 1001

        guild.get_member = Mock(return_value=None)
        guild.fetch_member = AsyncMock(
            side_effect=discord.NotFound(Mock(), "Member not found")
        )
        with patch.object(
            type(voice_bot), "guilds", new_callable=PropertyMock, return_value=[guild]
        ):
            # Execute
            result = await voice_bot._resolve_voice_state(user_id)

        # Verify
        assert result is None
        guild.get_member.assert_called_once_with(user_id)
        guild.fetch_member.assert_called_once_with(user_id)

    async def test_resolve_voice_state_with_http_exception(self, voice_bot):
        """Test _resolve_voice_state() when fetch_member raises HTTPException."""
        # Setup: Create mock guild where member fetch raises HTTPException
        user_id = 12345
        guild = Mock(spec=discord.Guild)
        guild.id = 1001

        guild.get_member = Mock(return_value=None)
        guild.fetch_member = AsyncMock(
            side_effect=discord.HTTPException(Mock(), "API error")
        )
        with patch.object(
            type(voice_bot), "guilds", new_callable=PropertyMock, return_value=[guild]
        ):
            # Execute
            result = await voice_bot._resolve_voice_state(user_id)

        # Verify
        assert result is None
        guild.get_member.assert_called_once_with(user_id)
        guild.fetch_member.assert_called_once_with(user_id)

    async def test_resolve_voice_state_with_multiple_guilds(self, voice_bot):
        """Test _resolve_voice_state() with multiple guilds, member in second guild."""
        # Setup: Create two guilds, member in second
        user_id = 12345

        # First guild - no member
        guild1 = Mock(spec=discord.Guild)
        guild1.id = 1001
        guild1.get_member = Mock(return_value=None)
        guild1.fetch_member = AsyncMock(
            side_effect=discord.NotFound(Mock(), "Not found")
        )

        # Second guild - member found
        guild2 = Mock(spec=discord.Guild)
        guild2.id = 1002

        voice_state = Mock(spec=discord.VoiceState)
        voice_state.channel = Mock(spec=discord.VoiceChannel)
        voice_state.channel.id = 2002

        member = Mock(spec=discord.Member)
        member.id = user_id
        member.voice = voice_state

        guild2.get_member = Mock(return_value=member)

        with patch.object(
            type(voice_bot),
            "guilds",
            new_callable=PropertyMock,
            return_value=[guild1, guild2],
        ):
            # Execute
            result = await voice_bot._resolve_voice_state(user_id)

        # Verify
        assert result == voice_state
        guild1.get_member.assert_called_once_with(user_id)
        guild1.fetch_member.assert_called_once_with(user_id)
        guild2.get_member.assert_called_once_with(user_id)
        # Second guild shouldn't need to fetch since member is cached
        assert not hasattr(guild2, "fetch_member") or not guild2.fetch_member.called

    async def test_resolve_voice_state_no_voice_channel(self, voice_bot):
        """Test _resolve_voice_state() when member has no voice channel."""
        # Setup: Member exists but has no voice channel
        user_id = 12345
        guild = Mock(spec=discord.Guild)
        guild.id = 1001

        member = Mock(spec=discord.Member)
        member.id = user_id
        member.voice = None  # No voice state

        guild.get_member = Mock(return_value=member)
        with patch.object(
            type(voice_bot), "guilds", new_callable=PropertyMock, return_value=[guild]
        ):
            # Execute
            result = await voice_bot._resolve_voice_state(user_id)

        # Verify
        assert result is None
        guild.get_member.assert_called_once_with(user_id)
