"""
Policy configuration for voice assistant behavior.

This module defines configuration options for the policy engine
that controls VAD, endpointing, barge-in, and other voice interaction policies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from services.common.logging import get_logger


logger = get_logger(__name__)


class VADMode(Enum):
    """Voice Activity Detection modes."""

    AGGRESSIVE = "aggressive"
    NORMAL = "normal"
    CONSERVATIVE = "conservative"


class EndpointingMode(Enum):
    """Endpointing behavior modes."""

    FAST = "fast"
    BALANCED = "balanced"
    ACCURATE = "accurate"


class BargeInMode(Enum):
    """Barge-in behavior modes."""

    DISABLED = "disabled"
    IMMEDIATE = "immediate"
    GRACEFUL = "graceful"


@dataclass
class VADPolicy:
    """Voice Activity Detection policy configuration."""

    enabled: bool = True
    mode: VADMode = VADMode.NORMAL
    sensitivity: float = 0.5  # 0.0 = most sensitive, 1.0 = least sensitive
    silence_threshold_ms: float = 1000.0  # Silence duration before endpointing
    speech_threshold_ms: float = 200.0  # Minimum speech duration to trigger
    aggressiveness: int = 2  # 0-3, higher = more aggressive

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "mode": self.mode.value,
            "sensitivity": self.sensitivity,
            "silence_threshold_ms": self.silence_threshold_ms,
            "speech_threshold_ms": self.speech_threshold_ms,
            "aggressiveness": self.aggressiveness,
        }


@dataclass
class EndpointingPolicy:
    """Endpointing policy configuration."""

    enabled: bool = True
    mode: EndpointingMode = EndpointingMode.BALANCED
    max_speech_duration_ms: float = 30000.0  # 30 seconds max
    min_speech_duration_ms: float = 100.0  # 100ms minimum
    silence_timeout_ms: float = 2000.0  # 2 seconds of silence
    confidence_threshold: float = 0.7  # Minimum confidence for endpointing

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "mode": self.mode.value,
            "max_speech_duration_ms": self.max_speech_duration_ms,
            "min_speech_duration_ms": self.min_speech_duration_ms,
            "silence_timeout_ms": self.silence_timeout_ms,
            "confidence_threshold": self.confidence_threshold,
        }


@dataclass
class BargeInPolicy:
    """Barge-in policy configuration."""

    enabled: bool = True
    mode: BargeInMode = BargeInMode.GRACEFUL
    detection_threshold: float = 0.8  # Confidence threshold for barge-in
    response_delay_ms: float = 100.0  # Delay before responding to barge-in
    max_interruption_duration_ms: float = 5000.0  # Max interruption time

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "mode": self.mode.value,
            "detection_threshold": self.detection_threshold,
            "response_delay_ms": self.response_delay_ms,
            "max_interruption_duration_ms": self.max_interruption_duration_ms,
        }


@dataclass
class WakePolicy:
    """Wake phrase detection policy configuration."""

    enabled: bool = True
    confidence_threshold: float = 0.8  # Minimum confidence for wake detection
    cooldown_ms: float = 2000.0  # Cooldown between wake detections
    timeout_ms: float = 10000.0  # Timeout for wake phrase response

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "confidence_threshold": self.confidence_threshold,
            "cooldown_ms": self.cooldown_ms,
            "timeout_ms": self.timeout_ms,
        }


@dataclass
class LatencyPolicy:
    """Latency and performance policy configuration."""

    max_e2e_latency_ms: float = 400.0  # Maximum end-to-end latency
    max_barge_in_delay_ms: float = 250.0  # Maximum barge-in delay
    max_stt_latency_ms: float = 1000.0  # Maximum STT processing time
    max_tts_latency_ms: float = 2000.0  # Maximum TTS processing time

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_e2e_latency_ms": self.max_e2e_latency_ms,
            "max_barge_in_delay_ms": self.max_barge_in_delay_ms,
            "max_stt_latency_ms": self.max_stt_latency_ms,
            "max_tts_latency_ms": self.max_tts_latency_ms,
        }


@dataclass
class PolicyConfig:
    """Complete policy configuration."""

    vad: VADPolicy = field(default_factory=VADPolicy)
    endpointing: EndpointingPolicy = field(default_factory=EndpointingPolicy)
    barge_in: BargeInPolicy = field(default_factory=BargeInPolicy)
    wake: WakePolicy = field(default_factory=WakePolicy)
    latency: LatencyPolicy = field(default_factory=LatencyPolicy)

    # Global settings
    debug_mode: bool = False
    log_level: str = "INFO"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "vad": self.vad.to_dict(),
            "endpointing": self.endpointing.to_dict(),
            "barge_in": self.barge_in.to_dict(),
            "wake": self.wake.to_dict(),
            "latency": self.latency.to_dict(),
            "debug_mode": self.debug_mode,
            "log_level": self.log_level,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicyConfig:
        """Create PolicyConfig from dictionary."""
        config = cls()

        if "vad" in data:
            vad_data = data["vad"]
            config.vad = VADPolicy(
                enabled=vad_data.get("enabled", True),
                mode=VADMode(vad_data.get("mode", "normal")),
                sensitivity=vad_data.get("sensitivity", 0.5),
                silence_threshold_ms=vad_data.get("silence_threshold_ms", 1000.0),
                speech_threshold_ms=vad_data.get("speech_threshold_ms", 200.0),
                aggressiveness=vad_data.get("aggressiveness", 2),
            )

        if "endpointing" in data:
            ep_data = data["endpointing"]
            config.endpointing = EndpointingPolicy(
                enabled=ep_data.get("enabled", True),
                mode=EndpointingMode(ep_data.get("mode", "balanced")),
                max_speech_duration_ms=ep_data.get("max_speech_duration_ms", 30000.0),
                min_speech_duration_ms=ep_data.get("min_speech_duration_ms", 100.0),
                silence_timeout_ms=ep_data.get("silence_timeout_ms", 2000.0),
                confidence_threshold=ep_data.get("confidence_threshold", 0.7),
            )

        if "barge_in" in data:
            bi_data = data["barge_in"]
            config.barge_in = BargeInPolicy(
                enabled=bi_data.get("enabled", True),
                mode=BargeInMode(bi_data.get("mode", "graceful")),
                detection_threshold=bi_data.get("detection_threshold", 0.8),
                response_delay_ms=bi_data.get("response_delay_ms", 100.0),
                max_interruption_duration_ms=bi_data.get(
                    "max_interruption_duration_ms", 5000.0
                ),
            )

        if "wake" in data:
            wake_data = data["wake"]
            config.wake = WakePolicy(
                enabled=wake_data.get("enabled", True),
                confidence_threshold=wake_data.get("confidence_threshold", 0.8),
                cooldown_ms=wake_data.get("cooldown_ms", 2000.0),
                timeout_ms=wake_data.get("timeout_ms", 10000.0),
            )

        if "latency" in data:
            lat_data = data["latency"]
            config.latency = LatencyPolicy(
                max_e2e_latency_ms=lat_data.get("max_e2e_latency_ms", 400.0),
                max_barge_in_delay_ms=lat_data.get("max_barge_in_delay_ms", 250.0),
                max_stt_latency_ms=lat_data.get("max_stt_latency_ms", 1000.0),
                max_tts_latency_ms=lat_data.get("max_tts_latency_ms", 2000.0),
            )

        config.debug_mode = data.get("debug_mode", False)
        config.log_level = data.get("log_level", "INFO")

        return config

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        # Validate VAD policy
        if not 0.0 <= self.vad.sensitivity <= 1.0:
            errors.append("VAD sensitivity must be between 0.0 and 1.0")

        if self.vad.silence_threshold_ms < 0:
            errors.append("VAD silence threshold must be non-negative")

        if self.vad.speech_threshold_ms < 0:
            errors.append("VAD speech threshold must be non-negative")

        if not 0 <= self.vad.aggressiveness <= 3:
            errors.append("VAD aggressiveness must be between 0 and 3")

        # Validate endpointing policy
        if self.endpointing.max_speech_duration_ms <= 0:
            errors.append("Endpointing max speech duration must be positive")

        if self.endpointing.min_speech_duration_ms < 0:
            errors.append("Endpointing min speech duration must be non-negative")

        if self.endpointing.silence_timeout_ms < 0:
            errors.append("Endpointing silence timeout must be non-negative")

        if not 0.0 <= self.endpointing.confidence_threshold <= 1.0:
            errors.append(
                "Endpointing confidence threshold must be between 0.0 and 1.0"
            )

        # Validate barge-in policy
        if not 0.0 <= self.barge_in.detection_threshold <= 1.0:
            errors.append("Barge-in detection threshold must be between 0.0 and 1.0")

        if self.barge_in.response_delay_ms < 0:
            errors.append("Barge-in response delay must be non-negative")

        if self.barge_in.max_interruption_duration_ms < 0:
            errors.append("Barge-in max interruption duration must be non-negative")

        # Validate wake policy
        if not 0.0 <= self.wake.confidence_threshold <= 1.0:
            errors.append("Wake confidence threshold must be between 0.0 and 1.0")

        if self.wake.cooldown_ms < 0:
            errors.append("Wake cooldown must be non-negative")

        if self.wake.timeout_ms < 0:
            errors.append("Wake timeout must be non-negative")

        # Validate latency policy
        if self.latency.max_e2e_latency_ms <= 0:
            errors.append("Max E2E latency must be positive")

        if self.latency.max_barge_in_delay_ms <= 0:
            errors.append("Max barge-in delay must be positive")

        if self.latency.max_stt_latency_ms <= 0:
            errors.append("Max STT latency must be positive")

        if self.latency.max_tts_latency_ms <= 0:
            errors.append("Max TTS latency must be positive")

        return errors
