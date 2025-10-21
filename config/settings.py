"""Configuration management for the Audio Orchestrator Platform."""

from typing import Optional
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Discord Configuration
    discord_token: str = Field(..., description="Discord bot token for voice integration")

    # Database Configuration
    db_url: str = Field(
        default="sqlite+aiosqlite:///./audio_orchestrator.db", description="Database connection URL"
    )

    # Audio Configuration
    audio_sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    audio_channels: int = Field(
        default=1, description="Number of audio channels (1=mono, 2=stereo)"
    )
    ffmpeg_path: str = Field(default="ffmpeg", description="Path to FFmpeg executable")

    # Logging Configuration
    log_level: str = Field(
        default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    # Service Configuration
    stt_service_url: Optional[str] = Field(default=None, description="URL for external STT service")
    tts_service_url: Optional[str] = Field(default=None, description="URL for external TTS service")

    # Orchestrator Configuration
    default_adapter: str = Field(default="discord", description="Default I/O adapter to use")
    max_conversation_history: int = Field(
        default=50, description="Maximum number of conversation turns to keep in memory"
    )

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def dict(self) -> dict:
        """Return settings as dictionary for convenience."""
        return super().dict()
