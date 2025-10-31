"""Service-specific configuration presets for audio-orchestrator services."""

from __future__ import annotations

from typing import Any

from .base import AudioConfig, HttpConfig, LoggingConfig, ServiceConfig, TelemetryConfig


class DiscordConfig:
    """Discord service configuration."""

    def __init__(
        self,
        token: str = "",
        guild_id: int = 0,
        voice_channel_id: int = 0,
        auto_join: bool = False,
        intents: Any = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Discord configuration."""
        self.token = token
        self.guild_id = guild_id
        self.voice_channel_id = voice_channel_id
        self.auto_join = auto_join
        self.intents = intents

        # Initialize sub-configurations
        self.logging = LoggingConfig(**kwargs.get("logging", {}))
        self.http = HttpConfig(**kwargs.get("http", {}))
        self.audio = AudioConfig(**kwargs.get("audio", {}))
        self.service = ServiceConfig(**kwargs.get("service", {}))
        self.telemetry = TelemetryConfig(**kwargs.get("telemetry", {}))


class STTConfig:
    """STT service configuration."""

    def __init__(
        self,
        model: str = "medium.en",
        device: str = "cpu",
        model_path: str = "/app/models",
        base_url: str = "http://stt:9000",
        forced_language: str | None = None,
        beam_size: int = 5,
        request_timeout_seconds: int = 30,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        """Initialize STT configuration."""
        self.model = model
        self.device = device
        self.model_path = model_path
        self.base_url = base_url
        self.forced_language = forced_language
        self.beam_size = beam_size
        self.request_timeout_seconds = request_timeout_seconds
        self.max_retries = max_retries

        # Initialize sub-configurations
        self.logging = LoggingConfig(**kwargs.get("logging", {}))
        self.http = HttpConfig(**kwargs.get("http", {}))
        self.audio = AudioConfig(**kwargs.get("audio", {}))
        self.service = ServiceConfig(**kwargs.get("service", {}))
        self.telemetry = TelemetryConfig(**kwargs.get("telemetry", {}))


class TTSConfig:
    """TTS service configuration."""

    def __init__(
        self,
        model_path: str = "/app/models/piper",
        voice: str = "en_US-lessac-medium",
        **kwargs: Any,
    ) -> None:
        """Initialize TTS configuration."""
        self.model_path = model_path
        self.voice = voice

        # Initialize sub-configurations
        self.logging = LoggingConfig(**kwargs.get("logging", {}))
        self.http = HttpConfig(**kwargs.get("http", {}))
        self.audio = AudioConfig(**kwargs.get("audio", {}))
        self.service = ServiceConfig(**kwargs.get("service", {}))
        self.telemetry = TelemetryConfig(**kwargs.get("telemetry", {}))


class WakeConfig:
    """Wake detection configuration."""

    def __init__(
        self,
        wake_phrases: list[str] | None = None,
        model_paths: list[str] | None = None,
        activation_threshold: float = 0.5,
        target_sample_rate_hz: int = 16000,
        enabled: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize Wake configuration."""
        self.wake_phrases = wake_phrases or ["hey atlas", "ok atlas"]
        self.model_paths = model_paths or []
        self.activation_threshold = activation_threshold
        self.target_sample_rate_hz = target_sample_rate_hz
        self.enabled = enabled


class OrchestratorConfig:
    """Orchestrator service configuration."""

    def __init__(
        self,
        llm_url: str = "http://flan:8100",
        tts_url: str = "http://bark:7100",
        llm_auth_token: str = "",
        tts_auth_token: str = "",
        llm_max_tokens: int = 1000,
        llm_temperature: float = 0.7,
        llm_top_p: float = 0.9,
        llm_repeat_penalty: float = 1.1,
        base_url: str = "http://orchestrator:8200",
        **kwargs: Any,
    ) -> None:
        """Initialize Orchestrator configuration."""
        self.llm_url = llm_url
        self.tts_url = tts_url
        self.llm_auth_token = llm_auth_token
        self.tts_auth_token = tts_auth_token
        self.llm_max_tokens = llm_max_tokens
        self.llm_temperature = llm_temperature
        self.llm_top_p = llm_top_p
        self.llm_repeat_penalty = llm_repeat_penalty
        self.base_url = base_url

        # Initialize sub-configurations
        self.logging = LoggingConfig(**kwargs.get("logging", {}))
        self.http = HttpConfig(**kwargs.get("http", {}))
        self.audio = AudioConfig(**kwargs.get("audio", {}))
        self.service = ServiceConfig(**kwargs.get("service", {}))
        self.telemetry = TelemetryConfig(**kwargs.get("telemetry", {}))


def get_service_preset(service_name: str) -> dict[str, Any]:
    """Get configuration preset for a service.

    Args:
        service_name: Name of the service

    Returns:
        Configuration preset dictionary
    """
    presets = {
        "discord": {
            "discord": {
                "token": "",
                "guild_id": 0,
                "voice_channel_id": 0,
                "auto_join": False,
                "intents": ["guilds", "guild_voice_states"],
                "voice_connect_timeout_seconds": 10.0,
                "voice_connect_max_attempts": 3,
                "voice_reconnect_initial_backoff_seconds": 2.0,
                "voice_reconnect_max_backoff_seconds": 60.0,
            },
            "logging": {"level": "INFO", "json_logs": True, "service_name": "discord"},
            "http": {"timeout": 30.0, "max_retries": 3, "retry_delay": 1.0},
            "audio": {
                "sample_rate": 48000,
                "channels": 1,
                "enable_enhancement": True,
                "enable_vad": True,
                "service_url": "http://audio:9100",
                "service_timeout": 20,
            },
            "service": {"port": 8001, "host": "0.0.0.0", "workers": 1},
            "telemetry": {"enabled": True, "metrics_port": 9091, "jaeger_endpoint": ""},
            "wake": {
                "enabled": True,
                "wake_phrases": ["hey atlas", "ok atlas"],
                "model_paths": [],
                "activation_threshold": 0.5,
                "target_sample_rate_hz": 16000,
            },
            "stt": {
                "base_url": "http://stt:9000",
                "model": "medium.en",
                "device": "cpu",
                "model_path": "/app/models",
                "forced_language": None,
                "beam_size": 5,
                "request_timeout_seconds": 30,
                "max_retries": 3,
            },
        },
        "stt": {
            "logging": {"level": "INFO", "json_logs": True, "service_name": "stt"},
            "http": {"timeout": 45.0, "max_retries": 3, "retry_delay": 1.0},
            "audio": {
                "sample_rate": 16000,
                "channels": 1,
                "enable_enhancement": True,
                "enable_vad": False,
                "service_url": "http://audio:9100",
                "service_timeout": 50,
            },
            "service": {"port": 9000, "host": "0.0.0.0", "workers": 1},
            "telemetry": {
                "enabled": True,
                "metrics_port": 9092,
                "jaeger_endpoint": "",
                "stt_warmup": False,
                "log_sample_stt_request_n": 25,
            },
            "faster_whisper": {
                "model": "medium.en",
                "model_path": "/app/models",
                "device": "cpu",
                "compute_type": "int8",
                "audio_service_url": "http://audio:9100",
                "audio_service_timeout": 50.0,
                "enable_enhancement": True,
            },
        },
        "llm": {
            "logging": {"level": "INFO", "json_logs": True, "service_name": "llm"},
            "http": {"timeout": 30.0, "max_retries": 3, "retry_delay": 1.0},
            "service": {"port": 8000, "host": "0.0.0.0", "workers": 1},
            "telemetry": {"enabled": True, "metrics_port": 9096, "jaeger_endpoint": ""},
            "llama": {
                "model_path": "/app/models/llama",
                "context_length": 2048,
                "threads": 4,
            },
            "tts": {
                "base_url": "http://tts:8000",
                "voice": "default",
                "auth_token": "",
                "timeout": 30.0,
            },
        },
        "tts": {
            "logging": {"level": "INFO", "json_logs": True, "service_name": "tts"},
            "http": {"timeout": 30.0, "max_retries": 3, "retry_delay": 1.0},
            "audio": {
                "sample_rate": 22050,
                "channels": 1,
                "enable_enhancement": False,
                "enable_vad": False,
                "service_url": "http://audio:9100",
                "service_timeout": 100,
            },
            "service": {"port": 8000, "host": "0.0.0.0", "workers": 1},
            "telemetry": {"enabled": True, "metrics_port": 9093, "jaeger_endpoint": ""},
            "tts": {
                "model_path": "/app/models/piper",
                "model_config_path": "/app/models/piper/config.json",
                "default_voice": "en_US-lessac-medium",
                "max_text_length": 1000,
                "max_concurrency": 4,
                "rate_limit_per_minute": 60,
                "auth_token": "",
                "length_scale": 1.0,
                "noise_scale": 0.667,
                "noise_w": 0.8,
            },
        },
        "orchestrator": {
            "logging": {
                "level": "INFO",
                "json_logs": True,
                "service_name": "orchestrator",
            },
            "http": {"timeout": 30.0, "max_retries": 3, "retry_delay": 1.0},
            "audio": {
                "sample_rate": 16000,
                "channels": 1,
                "enable_enhancement": False,
                "enable_vad": False,
                "service_url": "http://audio:9100",
                "service_timeout": 20,
            },
            "service": {"port": 8000, "host": "0.0.0.0", "workers": 1},
            "telemetry": {"enabled": True, "metrics_port": 9094, "jaeger_endpoint": ""},
        },
        "audio": {
            "logging": {
                "level": "INFO",
                "json_logs": True,
                "service_name": "audio",
            },
            "http": {"timeout": 5.0, "max_retries": 1, "retry_delay": 0.1},
            "audio": {
                "sample_rate": 16000,
                "channels": 1,
                "enable_enhancement": True,
                "enable_vad": True,
                "service_url": "http://localhost:9100",
                "service_timeout": 20,
            },
            "service": {"port": 9100, "host": "0.0.0.0", "workers": 1},
            "telemetry": {"enabled": True, "metrics_port": 9095, "jaeger_endpoint": ""},
        },
    }

    return presets.get(service_name, presets["orchestrator"])
