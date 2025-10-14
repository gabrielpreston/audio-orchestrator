"""Service-specific configuration classes for discord-voice-lab services.

This module contains pre-built configuration classes for each service,
demonstrating how to use the common configuration library.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .config import (
    BaseConfig,
    FieldDefinition,
    create_field_definition,
    validate_non_negative,
    validate_port,
    validate_positive,
    validate_url,
)


class DiscordConfig(BaseConfig):
    """Discord bot configuration."""

    def __init__(
        self,
        token: str = "",
        guild_id: int = 0,
        voice_channel_id: int = 0,
        intents: List[str] = None,
        auto_join: bool = False,
        voice_connect_timeout_seconds: float = 15.0,
        voice_connect_max_attempts: int = 3,
        voice_reconnect_initial_backoff_seconds: float = 5.0,
        voice_reconnect_max_backoff_seconds: float = 60.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.token = token
        self.guild_id = guild_id
        self.voice_channel_id = voice_channel_id
        self.intents = intents or ["guilds", "voice_states", "guild_messages"]
        self.auto_join = auto_join
        self.voice_connect_timeout_seconds = voice_connect_timeout_seconds
        self.voice_connect_max_attempts = voice_connect_max_attempts
        self.voice_reconnect_initial_backoff_seconds = voice_reconnect_initial_backoff_seconds
        self.voice_reconnect_max_backoff_seconds = voice_reconnect_max_backoff_seconds

    @classmethod
    def get_field_definitions(cls) -> List[FieldDefinition]:
        return [
            create_field_definition(
                name="token",
                field_type=str,
                required=True,
                description="Discord bot token",
                env_var="DISCORD_BOT_TOKEN",
            ),
            create_field_definition(
                name="guild_id",
                field_type=int,
                required=True,
                description="Discord guild (server) ID",
                env_var="DISCORD_GUILD_ID",
            ),
            create_field_definition(
                name="voice_channel_id",
                field_type=int,
                required=True,
                description="Discord voice channel ID",
                env_var="DISCORD_VOICE_CHANNEL_ID",
            ),
            create_field_definition(
                name="intents",
                field_type=list,
                default=["guilds", "voice_states", "guild_messages"],
                description="Discord bot intents",
                env_var="DISCORD_INTENTS",
            ),
            create_field_definition(
                name="auto_join",
                field_type=bool,
                default=False,
                description="Whether to automatically join voice channel on startup",
                env_var="DISCORD_AUTO_JOIN",
            ),
            create_field_definition(
                name="voice_connect_timeout_seconds",
                field_type=float,
                default=15.0,
                description="Timeout for voice connection attempts",
                min_value=1.0,
                max_value=300.0,
                env_var="DISCORD_VOICE_CONNECT_TIMEOUT",
            ),
            create_field_definition(
                name="voice_connect_max_attempts",
                field_type=int,
                default=3,
                description="Maximum number of voice connection attempts",
                min_value=1,
                max_value=10,
                env_var="DISCORD_VOICE_CONNECT_ATTEMPTS",
            ),
            create_field_definition(
                name="voice_reconnect_initial_backoff_seconds",
                field_type=float,
                default=5.0,
                description="Initial backoff delay for voice reconnection",
                min_value=0.1,
                max_value=60.0,
                env_var="DISCORD_VOICE_RECONNECT_BASE_DELAY",
            ),
            create_field_definition(
                name="voice_reconnect_max_backoff_seconds",
                field_type=float,
                default=60.0,
                description="Maximum backoff delay for voice reconnection",
                min_value=1.0,
                max_value=300.0,
                env_var="DISCORD_VOICE_RECONNECT_MAX_DELAY",
            ),
        ]


class AudioConfig(BaseConfig):
    """Audio processing configuration."""

    def __init__(
        self,
        silence_timeout_seconds: float = 1.0,
        max_segment_duration_seconds: float = 15.0,
        min_segment_duration_seconds: float = 0.3,
        aggregation_window_seconds: float = 1.5,
        allowlist_user_ids: List[int] = None,
        input_sample_rate_hz: int = 48000,
        vad_sample_rate_hz: int = 16000,
        vad_frame_duration_ms: int = 30,
        vad_aggressiveness: int = 1,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.silence_timeout_seconds = silence_timeout_seconds
        self.max_segment_duration_seconds = max_segment_duration_seconds
        self.min_segment_duration_seconds = min_segment_duration_seconds
        self.aggregation_window_seconds = aggregation_window_seconds
        self.allowlist_user_ids = allowlist_user_ids or []
        self.input_sample_rate_hz = input_sample_rate_hz
        self.vad_sample_rate_hz = vad_sample_rate_hz
        self.vad_frame_duration_ms = vad_frame_duration_ms
        self.vad_aggressiveness = vad_aggressiveness

    @classmethod
    def get_field_definitions(cls) -> List[FieldDefinition]:
        return [
            create_field_definition(
                name="silence_timeout_seconds",
                field_type=float,
                default=1.0,
                description="Timeout for silence detection",
                min_value=0.1,
                max_value=10.0,
                env_var="AUDIO_SILENCE_TIMEOUT",
            ),
            create_field_definition(
                name="max_segment_duration_seconds",
                field_type=float,
                default=15.0,
                description="Maximum duration for audio segments",
                min_value=1.0,
                max_value=60.0,
                env_var="AUDIO_MAX_SEGMENT_DURATION",
            ),
            create_field_definition(
                name="min_segment_duration_seconds",
                field_type=float,
                default=0.3,
                description="Minimum duration for audio segments",
                min_value=0.1,
                max_value=5.0,
                env_var="AUDIO_MIN_SEGMENT_DURATION",
            ),
            create_field_definition(
                name="aggregation_window_seconds",
                field_type=float,
                default=1.5,
                description="Window for audio aggregation",
                min_value=0.1,
                max_value=10.0,
                env_var="AUDIO_AGGREGATION_WINDOW",
            ),
            create_field_definition(
                name="allowlist_user_ids",
                field_type=list,
                default=[],
                description="List of allowed user IDs for audio processing",
                env_var="AUDIO_ALLOWLIST",
            ),
            create_field_definition(
                name="input_sample_rate_hz",
                field_type=int,
                default=48000,
                description="Input audio sample rate in Hz",
                choices=[8000, 16000, 22050, 44100, 48000],
                env_var="AUDIO_SAMPLE_RATE",
            ),
            create_field_definition(
                name="vad_sample_rate_hz",
                field_type=int,
                default=16000,
                description="Voice activity detection sample rate in Hz",
                choices=[8000, 16000, 22050, 44100, 48000],
                env_var="AUDIO_VAD_SAMPLE_RATE",
            ),
            create_field_definition(
                name="vad_frame_duration_ms",
                field_type=int,
                default=30,
                description="VAD frame duration in milliseconds",
                min_value=10,
                max_value=100,
                env_var="AUDIO_VAD_FRAME_MS",
            ),
            create_field_definition(
                name="vad_aggressiveness",
                field_type=int,
                default=1,
                description="VAD aggressiveness level",
                min_value=0,
                max_value=3,
                env_var="AUDIO_VAD_AGGRESSIVENESS",
            ),
        ]


class STTConfig(BaseConfig):
    """Speech-to-text service configuration."""

    def __init__(
        self,
        base_url: str = "",
        request_timeout_seconds: float = 45.0,
        max_retries: int = 3,
        forced_language: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.base_url = base_url
        self.request_timeout_seconds = request_timeout_seconds
        self.max_retries = max_retries
        self.forced_language = forced_language

    @classmethod
    def get_field_definitions(cls) -> List[FieldDefinition]:
        return [
            create_field_definition(
                name="base_url",
                field_type=str,
                required=True,
                description="Base URL for STT service",
                validator=validate_url,
                env_var="STT_BASE_URL",
            ),
            create_field_definition(
                name="request_timeout_seconds",
                field_type=float,
                default=45.0,
                description="Request timeout for STT service",
                min_value=1.0,
                max_value=300.0,
                env_var="STT_TIMEOUT",
            ),
            create_field_definition(
                name="max_retries",
                field_type=int,
                default=3,
                description="Maximum retries for STT requests",
                min_value=0,
                max_value=10,
                env_var="STT_MAX_RETRIES",
            ),
            create_field_definition(
                name="forced_language",
                field_type=str,
                description="Forced language for STT processing",
                env_var="STT_FORCED_LANGUAGE",
            ),
        ]


class WakeConfig(BaseConfig):
    """Wake phrase detection configuration."""

    def __init__(
        self,
        wake_phrases: List[str] = None,
        model_paths: List[Path] = None,
        activation_threshold: float = 0.5,
        target_sample_rate_hz: int = 16000,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.wake_phrases = wake_phrases or ["hey atlas", "ok atlas"]
        self.model_paths = model_paths or []
        self.activation_threshold = activation_threshold
        self.target_sample_rate_hz = target_sample_rate_hz

    @classmethod
    def get_field_definitions(cls) -> List[FieldDefinition]:
        return [
            create_field_definition(
                name="wake_phrases",
                field_type=list,
                default=["hey atlas", "ok atlas"],
                description="List of wake phrases to detect",
                env_var="WAKE_PHRASES",
            ),
            create_field_definition(
                name="model_paths",
                field_type=list,
                default=[],
                description="Paths to wake phrase detection models",
                env_var="WAKE_MODEL_PATHS",
            ),
            create_field_definition(
                name="activation_threshold",
                field_type=float,
                default=0.5,
                description="Activation threshold for wake phrase detection",
                min_value=0.0,
                max_value=1.0,
                env_var="WAKE_THRESHOLD",
            ),
            create_field_definition(
                name="target_sample_rate_hz",
                field_type=int,
                default=16000,
                description="Target sample rate for wake phrase detection",
                choices=[8000, 16000, 22050, 44100, 48000],
                env_var="WAKE_SAMPLE_RATE",
            ),
        ]


class MCPConfig(BaseConfig):
    """MCP (Model Context Protocol) configuration."""

    def __init__(
        self,
        manifest_paths: List[Path] = None,
        websocket_url: Optional[str] = None,
        command_path: Optional[Path] = None,
        registration_url: Optional[str] = None,
        heartbeat_interval_seconds: float = 30.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.manifest_paths = manifest_paths or []
        self.websocket_url = websocket_url
        self.command_path = command_path
        self.registration_url = registration_url
        self.heartbeat_interval_seconds = heartbeat_interval_seconds

    @classmethod
    def get_field_definitions(cls) -> List[FieldDefinition]:
        return [
            create_field_definition(
                name="manifest_paths",
                field_type=list,
                default=[],
                description="Paths to MCP manifest files",
                env_var="MCP_MANIFESTS",
            ),
            create_field_definition(
                name="websocket_url",
                field_type=str,
                description="WebSocket URL for MCP connection",
                validator=validate_url,
                env_var="MCP_WEBSOCKET_URL",
            ),
            create_field_definition(
                name="command_path",
                field_type=str,
                description="Path to MCP command executable",
                env_var="MCP_COMMAND_PATH",
            ),
            create_field_definition(
                name="registration_url",
                field_type=str,
                description="URL for MCP registration",
                validator=validate_url,
                env_var="MCP_REGISTRATION_URL",
            ),
            create_field_definition(
                name="heartbeat_interval_seconds",
                field_type=float,
                default=30.0,
                description="Heartbeat interval for MCP connections",
                min_value=1.0,
                max_value=300.0,
                env_var="MCP_HEARTBEAT_INTERVAL",
            ),
        ]


class TelemetryConfig(BaseConfig):
    """Telemetry and monitoring configuration."""

    def __init__(
        self,
        log_level: str = "INFO",
        log_json: bool = True,
        metrics_port: Optional[int] = None,
        waveform_debug_dir: Optional[Path] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.log_level = log_level
        self.log_json = log_json
        self.metrics_port = metrics_port
        self.waveform_debug_dir = waveform_debug_dir

    @classmethod
    def get_field_definitions(cls) -> List[FieldDefinition]:
        return [
            create_field_definition(
                name="log_level",
                field_type=str,
                default="INFO",
                description="Logging level",
                choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                env_var="LOG_LEVEL",
            ),
            create_field_definition(
                name="log_json",
                field_type=bool,
                default=True,
                description="Whether to use JSON logging format",
                env_var="LOG_JSON",
            ),
            create_field_definition(
                name="metrics_port",
                field_type=int,
                description="Port for metrics endpoint",
                validator=validate_port,
                env_var="METRICS_PORT",
            ),
            create_field_definition(
                name="waveform_debug_dir",
                field_type=str,
                description="Directory for waveform debug files",
                env_var="WAVEFORM_DEBUG_DIR",
            ),
        ]


class FasterWhisperConfig(BaseConfig):
    """Faster-whisper model configuration."""

    def __init__(
        self,
        model: str = "small",
        device: str = "cpu",
        compute_type: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.model = model
        self.device = device
        self.compute_type = compute_type

    @classmethod
    def get_field_definitions(cls) -> List[FieldDefinition]:
        return [
            create_field_definition(
                name="model",
                field_type=str,
                default="small",
                description="Faster-whisper model name",
                choices=["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
                env_var="FW_MODEL",
            ),
            create_field_definition(
                name="device",
                field_type=str,
                default="cpu",
                description="Device to run the model on",
                choices=["cpu", "cuda", "auto"],
                env_var="FW_DEVICE",
            ),
            create_field_definition(
                name="compute_type",
                field_type=str,
                default=None,
                description="Compute type for the model",
                choices=["int8", "int8_float16", "int16", "float16", "float32"],
                env_var="FW_COMPUTE_TYPE",
            ),
        ]


class LlamaConfig(BaseConfig):
    """Llama model configuration."""

    def __init__(
        self,
        model_path: str = "/app/models/llama2-7b.gguf",
        context_length: int = 2048,
        threads: int = 4,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.model_path = model_path
        self.context_length = context_length
        self.threads = threads

    @classmethod
    def get_field_definitions(cls) -> List[FieldDefinition]:
        return [
            create_field_definition(
                name="model_path",
                field_type=str,
                default="/app/models/llama2-7b.gguf",
                description="Path to Llama model file",
                env_var="LLAMA_MODEL_PATH",
            ),
            create_field_definition(
                name="context_length",
                field_type=int,
                default=2048,
                description="Context length for the model",
                min_value=512,
                max_value=8192,
                env_var="LLAMA_CTX",
            ),
            create_field_definition(
                name="threads",
                field_type=int,
                default=4,
                description="Number of threads for model inference",
                min_value=1,
                max_value=32,
                env_var="LLAMA_THREADS",
            ),
        ]


class TTSConfig(BaseConfig):
    """Text-to-speech service configuration."""

    def __init__(
        self,
        port: int = 7000,
        model_path: Optional[str] = None,
        model_config_path: Optional[str] = None,
        default_voice: Optional[str] = None,
        max_text_length: int = 1000,
        max_concurrency: int = 4,
        rate_limit_per_minute: int = 60,
        auth_token: Optional[str] = None,
        length_scale: float = 1.0,
        noise_scale: float = 0.667,
        noise_w: float = 0.8,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.port = port
        self.model_path = model_path
        self.model_config_path = model_config_path
        self.default_voice = default_voice
        self.max_text_length = max_text_length
        self.max_concurrency = max_concurrency
        self.rate_limit_per_minute = rate_limit_per_minute
        self.auth_token = auth_token
        self.length_scale = length_scale
        self.noise_scale = noise_scale
        self.noise_w = noise_w

    @classmethod
    def get_field_definitions(cls) -> List[FieldDefinition]:
        return [
            create_field_definition(
                name="port",
                field_type=int,
                default=7000,
                description="Port for TTS service",
                validator=validate_port,
                env_var="PORT",
            ),
            create_field_definition(
                name="model_path",
                field_type=str,
                description="Path to TTS model file",
                env_var="TTS_MODEL_PATH",
            ),
            create_field_definition(
                name="model_config_path",
                field_type=str,
                description="Path to TTS model configuration file",
                env_var="TTS_MODEL_CONFIG_PATH",
            ),
            create_field_definition(
                name="default_voice",
                field_type=str,
                description="Default voice for TTS",
                env_var="TTS_DEFAULT_VOICE",
            ),
            create_field_definition(
                name="max_text_length",
                field_type=int,
                default=1000,
                description="Maximum text length for TTS",
                min_value=32,
                max_value=10000,
                env_var="TTS_MAX_TEXT_LENGTH",
            ),
            create_field_definition(
                name="max_concurrency",
                field_type=int,
                default=4,
                description="Maximum concurrent TTS requests",
                min_value=1,
                max_value=64,
                env_var="TTS_MAX_CONCURRENCY",
            ),
            create_field_definition(
                name="rate_limit_per_minute",
                field_type=int,
                default=60,
                description="Rate limit for TTS requests per minute",
                min_value=0,
                max_value=100000,
                env_var="TTS_RATE_LIMIT_PER_MINUTE",
            ),
            create_field_definition(
                name="auth_token",
                field_type=str,
                description="Authentication token for TTS service",
                env_var="TTS_AUTH_TOKEN",
            ),
            create_field_definition(
                name="length_scale",
                field_type=float,
                default=1.0,
                description="Length scale for TTS synthesis",
                min_value=0.1,
                max_value=3.0,
                env_var="TTS_LENGTH_SCALE",
            ),
            create_field_definition(
                name="noise_scale",
                field_type=float,
                default=0.667,
                description="Noise scale for TTS synthesis",
                min_value=0.0,
                max_value=2.0,
                env_var="TTS_NOISE_SCALE",
            ),
            create_field_definition(
                name="noise_w",
                field_type=float,
                default=0.8,
                description="Noise W parameter for TTS synthesis",
                min_value=0.0,
                max_value=2.0,
                env_var="TTS_NOISE_W",
            ),
        ]


class OrchestratorConfig(BaseConfig):
    """Orchestrator service configuration."""

    def __init__(
        self,
        port: int = 8000,
        auth_token: Optional[str] = None,
        debug_save: bool = False,
        tts_base_url: Optional[str] = None,
        tts_voice: Optional[str] = None,
        tts_timeout: float = 30.0,
        mcp_config_path: str = "./mcp.json",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.port = port
        self.auth_token = auth_token
        self.debug_save = debug_save
        self.tts_base_url = tts_base_url
        self.tts_voice = tts_voice
        self.tts_timeout = tts_timeout
        self.mcp_config_path = mcp_config_path

    @classmethod
    def get_field_definitions(cls) -> List[FieldDefinition]:
        return [
            create_field_definition(
                name="port",
                field_type=int,
                default=8000,
                description="Port for orchestrator service",
                validator=validate_port,
                env_var="PORT",
            ),
            create_field_definition(
                name="auth_token",
                field_type=str,
                description="Authentication token for orchestrator",
                env_var="ORCH_AUTH_TOKEN",
            ),
            create_field_definition(
                name="debug_save",
                field_type=bool,
                default=False,
                description="Whether to save debug data",
                env_var="ORCHESTRATOR_DEBUG_SAVE",
            ),
            create_field_definition(
                name="tts_base_url",
                field_type=str,
                description="Base URL for TTS service",
                validator=validate_url,
                env_var="TTS_BASE_URL",
            ),
            create_field_definition(
                name="tts_voice",
                field_type=str,
                description="Default voice for TTS",
                env_var="TTS_VOICE",
            ),
            create_field_definition(
                name="tts_timeout",
                field_type=float,
                default=30.0,
                description="Timeout for TTS requests",
                min_value=1.0,
                max_value=300.0,
                env_var="TTS_TIMEOUT",
            ),
            create_field_definition(
                name="mcp_config_path",
                field_type=str,
                default="./mcp.json",
                description="Path to MCP configuration file",
                env_var="MCP_CONFIG_PATH",
            ),
        ]


__all__ = [
    "AudioConfig",
    "DiscordConfig",
    "FasterWhisperConfig",
    "LlamaConfig",
    "MCPConfig",
    "OrchestratorConfig",
    "STTConfig",
    "TelemetryConfig",
    "TTSConfig",
    "WakeConfig",
]
