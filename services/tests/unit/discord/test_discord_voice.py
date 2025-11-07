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


@pytest.mark.unit
@pytest.mark.asyncio
class TestValidateGatewaySession:
    """Unit tests for _validate_gateway_session() method."""

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

    async def test_validate_gateway_session_not_ready(self, voice_bot):
        """Test _validate_gateway_session() returns False when bot is not ready."""
        with patch.object(
            type(voice_bot), "is_ready", new_callable=PropertyMock, return_value=False
        ):
            result = await voice_bot._validate_gateway_session()
            assert result is False

    async def test_validate_gateway_session_success_with_valid_latency(self, voice_bot):
        """Test _validate_gateway_session() succeeds when latency becomes finite."""
        from unittest.mock import MagicMock

        mock_logger = MagicMock()
        mock_logger.info = MagicMock()
        mock_logger.warning = MagicMock()
        mock_logger.debug = MagicMock()
        with (
            patch.object(
                type(voice_bot),
                "is_ready",
                new_callable=PropertyMock,
                return_value=True,
            ),
            patch.object(
                type(voice_bot), "latency", new_callable=PropertyMock, return_value=0.05
            ),
            patch.object(voice_bot, "_logger", mock_logger),
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("asyncio.get_event_loop") as mock_get_loop,
        ):
            # Mock time: start at 0, then 0.1 in while condition, then 0.1 for elapsed
            # get_event_loop() is called 3 times: start_time, while condition, elapsed calculation
            time_values = [0.0, 0.1, 0.1]
            mock_loop_obj = Mock()
            mock_loop_obj.time = Mock(side_effect=time_values)
            # Ensure get_event_loop always returns the same mock object
            mock_get_loop.return_value = mock_loop_obj
            mock_get_loop.side_effect = None
            result = await voice_bot._validate_gateway_session(
                max_wait_seconds=5.0, min_delay_seconds=1.0
            )

            assert result is True
            # Should log validation success at debug level
            mock_logger.debug.assert_called()

    async def test_validate_gateway_session_timeout_fallback_to_min_delay(
        self, voice_bot
    ):
        """Test _validate_gateway_session() falls back to min_delay when latency stays infinite."""
        mock_logger = Mock()
        mock_logger.info = Mock()
        mock_logger.warning = Mock()
        mock_logger.debug = Mock()
        with (
            patch.object(
                type(voice_bot),
                "is_ready",
                new_callable=PropertyMock,
                return_value=True,
            ),
            patch.object(
                type(voice_bot),
                "latency",
                new_callable=PropertyMock,
                return_value=float("inf"),
            ),
            patch.object(voice_bot, "_logger", mock_logger),
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("asyncio.get_event_loop") as mock_loop,
        ):
            # Mock time progression: start at 0, then multiple checks, then after max_wait it's past timeout
            # The loop checks time() twice: once at start, once to calculate elapsed
            time_values = [
                0.0,
                0.0,
                5.1,
                5.1,
            ]  # Start (twice), then after max_wait (twice)
            mock_loop.return_value.time = Mock(side_effect=time_values)

            result = await voice_bot._validate_gateway_session(
                max_wait_seconds=5.0, min_delay_seconds=1.0
            )

            assert result is True
            # Should log warning about timeout
            mock_logger.warning.assert_called()
            # Should have called sleep for min_delay
            assert mock_sleep.called

    async def test_validate_gateway_session_latency_too_high(self, voice_bot):
        """Test _validate_gateway_session() rejects latency > 60.0 seconds."""
        mock_logger = Mock()
        mock_logger.info = Mock()
        mock_logger.warning = Mock()
        mock_logger.debug = Mock()
        with (
            patch.object(
                type(voice_bot),
                "is_ready",
                new_callable=PropertyMock,
                return_value=True,
            ),
            patch.object(
                type(voice_bot),
                "latency",
                new_callable=PropertyMock,
                return_value=100.0,
            ),
            patch.object(voice_bot, "_logger", mock_logger),
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("asyncio.get_event_loop") as mock_loop,
        ):
            # Mock time progression: timeout before acceptable latency
            time_values = [0.0, 0.0, 5.1, 5.1]
            mock_loop.return_value.time = Mock(side_effect=time_values)

            result = await voice_bot._validate_gateway_session(
                max_wait_seconds=5.0, min_delay_seconds=1.0
            )

            # Should fall back to min_delay and return True
            assert result is True
            mock_logger.warning.assert_called()

    async def test_validate_gateway_session_latency_zero(self, voice_bot):
        """Test _validate_gateway_session() rejects latency of 0 (not yet initialized)."""
        mock_logger = Mock()
        mock_logger.info = Mock()
        mock_logger.warning = Mock()
        mock_logger.debug = Mock()
        with (
            patch.object(
                type(voice_bot),
                "is_ready",
                new_callable=PropertyMock,
                return_value=True,
            ),
            patch.object(
                type(voice_bot), "latency", new_callable=PropertyMock, return_value=0.0
            ),
            patch.object(voice_bot, "_logger", mock_logger),
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("asyncio.get_event_loop") as mock_loop,
        ):
            # Mock time progression: timeout before acceptable latency
            time_values = [0.0, 0.0, 5.1, 5.1]
            mock_loop.return_value.time = Mock(side_effect=time_values)

            result = await voice_bot._validate_gateway_session(
                max_wait_seconds=5.0, min_delay_seconds=1.0
            )

            # Should fall back to min_delay and return True
            assert result is True
            mock_logger.warning.assert_called()

    async def test_validate_gateway_session_valid_latency_within_threshold(
        self, voice_bot
    ):
        """Test _validate_gateway_session() succeeds with latency < 60.0."""
        from unittest.mock import MagicMock

        mock_logger = MagicMock()
        mock_logger.info = MagicMock()
        mock_logger.warning = MagicMock()
        mock_logger.debug = MagicMock()
        with (
            patch.object(
                type(voice_bot),
                "is_ready",
                new_callable=PropertyMock,
                return_value=True,
            ),
            patch.object(
                type(voice_bot), "latency", new_callable=PropertyMock, return_value=0.1
            ),
            patch.object(voice_bot, "_logger", mock_logger),
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("asyncio.get_event_loop") as mock_get_loop,
        ):
            # Mock time: start at 0, then 0.1 in while condition, then 0.1 for elapsed
            # get_event_loop() is called 3 times: start_time, while condition, elapsed calculation
            time_values = [0.0, 0.1, 0.1]
            mock_loop_obj = Mock()
            mock_loop_obj.time = Mock(side_effect=time_values)
            # Ensure get_event_loop always returns the same mock object
            mock_get_loop.return_value = mock_loop_obj
            mock_get_loop.side_effect = None
            result = await voice_bot._validate_gateway_session(
                max_wait_seconds=5.0, min_delay_seconds=1.0
            )

            assert result is True
            # Should log success at debug level, not warning
            mock_logger.debug.assert_called()
            assert not mock_logger.warning.called
