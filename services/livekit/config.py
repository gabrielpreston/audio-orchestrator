"""Configuration management for LiveKit agent service."""

import os
from typing import List, Optional

from pydantic import BaseSettings, Field


class LiveKitConfig(BaseSettings):
    """LiveKit agent configuration."""
    
    # Service configuration
    service_name: str = "livekit-agent"
    port: int = Field(default=8080, env="PORT")
    host: str = Field(default="0.0.0.0", env="HOST")
    
    # LiveKit configuration
    livekit_url: str = Field(..., env="LIVEKIT_URL")
    livekit_api_key: str = Field(..., env="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(..., env="LIVEKIT_API_SECRET")
    
    # STT/TTS service URLs
    stt_base_url: str = Field(default="http://stt:9000", env="STT_BASE_URL")
    tts_base_url: str = Field(default="http://tts:7000", env="TTS_BASE_URL")
    orchestrator_base_url: str = Field(default="http://orch:8000", env="ORCHESTRATOR_BASE_URL")
    
    # Audio processing
    canonical_sample_rate: int = Field(default=16000, env="CANONICAL_SAMPLE_RATE")
    canonical_frame_ms: int = Field(default=20, env="CANONICAL_FRAME_MS")
    opus_sample_rate: int = Field(default=48000, env="OPUS_SAMPLE_RATE")
    
    # Session management
    max_session_duration_minutes: int = Field(default=30, env="MAX_SESSION_DURATION_MINUTES")
    wake_cooldown_ms: int = Field(default=1000, env="WAKE_COOLDOWN_MS")
    vad_timeout_ms: int = Field(default=2000, env="VAD_TIMEOUT_MS")
    endpointing_timeout_ms: int = Field(default=5000, env="ENDPOINTING_TIMEOUT_MS")
    
    # Barge-in configuration
    barge_in_enabled: bool = Field(default=True, env="BARGE_IN_ENABLED")
    barge_in_pause_delay_ms: int = Field(default=250, env="BARGE_IN_PAUSE_DELAY_MS")
    max_pause_duration_ms: int = Field(default=10000, env="MAX_PAUSE_DURATION_MS")
    
    # Quality targets
    target_rtt_median_ms: int = Field(default=400, env="TARGET_RTT_MEDIAN_MS")
    target_rtt_p95_ms: int = Field(default=650, env="TARGET_RTT_P95_MS")
    max_packet_loss_percent: float = Field(default=10.0, env="MAX_PACKET_LOSS_PERCENT")
    max_jitter_ms: float = Field(default=80.0, env="MAX_JITTER_MS")
    
    # Logging
    log_level: str = Field(default="info", env="LOG_LEVEL")
    log_json: bool = Field(default=True, env="LOG_JSON")
    
    # Debug
    debug_save: bool = Field(default=False, env="LIVEKIT_DEBUG_SAVE")
    debug_save_dir: str = Field(default="/app/debug", env="DEBUG_SAVE_DIR")
    
    # Authentication
    auth_token: str = Field(..., env="AUTH_TOKEN")
    
    # STT/TTS timeouts
    stt_timeout: int = Field(default=45, env="STT_TIMEOUT")
    tts_timeout: int = Field(default=30, env="TTS_TIMEOUT")
    orchestrator_timeout: int = Field(default=60, env="ORCHESTRATOR_TIMEOUT")
    
    # Retry configuration
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    retry_delay_ms: int = Field(default=1000, env="RETRY_DELAY_MS")
    
    # Telemetry
    telemetry_interval_ms: int = Field(default=5000, env="TELEMETRY_INTERVAL_MS")
    metrics_enabled: bool = Field(default=True, env="METRICS_ENABLED")
    
    class Config:
        env_file = ".env.service"
        case_sensitive = False


# Global config instance
config = LiveKitConfig()