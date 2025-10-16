"""
Media gateway for codec conversion and normalization.

This module handles conversion between transport codecs (Opus/PCM)
and enforces the canonical audio contract at network edges.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from services.common.logging import get_logger

from .audio_contract import AudioContract, AudioContractSpec

logger = get_logger(__name__)


@dataclass
class JitterBuffer:
    """Jitter buffer for handling network timing variations."""

    max_size: int = 10  # Maximum frames to buffer
    target_latency_ms: float = 100.0  # Target latency in milliseconds
    current_frames: list[tuple[bytes, float]] = None  # (audio_data, timestamp)

    def __post_init__(self) -> None:
        if self.current_frames is None:
            self.current_frames = []

    def add_frame(self, audio_data: bytes, timestamp: float) -> None:
        """Add frame to jitter buffer."""
        self.current_frames.append((audio_data, timestamp))

        # Remove old frames if buffer is too large
        if len(self.current_frames) > self.max_size:
            self.current_frames.pop(0)

    def get_ready_frames(self, current_time: float) -> list[bytes]:
        """Get frames that are ready to play based on target latency."""
        ready_frames = []
        ready_indices = []

        for i, (audio_data, timestamp) in enumerate(self.current_frames):
            age_ms = (current_time - timestamp) * 1000.0
            if age_ms >= self.target_latency_ms:
                ready_frames.append(audio_data)
                ready_indices.append(i)

        # Remove ready frames from buffer
        for i in reversed(ready_indices):
            self.current_frames.pop(i)

        return ready_frames

    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        return len(self.current_frames) == 0


class MediaGateway:
    """Gateway for media conversion and normalization."""

    def __init__(
        self,
        contract_spec: AudioContractSpec | None = None,
        enable_jitter_buffer: bool = True,
    ) -> None:
        self.contract = AudioContract(contract_spec)
        self.enable_jitter_buffer = enable_jitter_buffer
        self.jitter_buffer = JitterBuffer() if enable_jitter_buffer else None
        self._logger = get_logger(__name__)

        # Performance tracking
        self._conversion_count = 0
        self._total_conversion_time = 0.0

    async def normalize_audio(
        self,
        audio_data: bytes,
        input_metadata: dict[str, Any],
        output_format: str = "pcm",
    ) -> tuple[bytes, dict[str, Any]]:
        """Normalize audio to canonical contract format."""
        start_time = time.time()

        try:
            # Validate input
            if not self.contract.validate_audio_data(audio_data, input_metadata):
                self._logger.warning("media_gateway.invalid_input")
                return audio_data, input_metadata

            # Normalize to canonical format
            normalized_data, normalized_metadata = self.contract.normalize_audio(
                audio_data, input_metadata
            )

            # Convert to output format if needed
            if output_format == "wav":
                normalized_data = self.contract.create_wav_header(
                    normalized_data, normalized_metadata
                )
                normalized_metadata["format"] = "wav"

            # Track performance
            conversion_time = time.time() - start_time
            self._conversion_count += 1
            self._total_conversion_time += conversion_time

            self._logger.debug(
                "media_gateway.normalized",
                input_format=input_metadata.get("format", "unknown"),
                output_format=output_format,
                conversion_time_ms=conversion_time * 1000,
            )

            return normalized_data, normalized_metadata

        except (ValueError, TypeError, OSError) as e:
            self._logger.error("media_gateway.normalization_failed", error=str(e))
            return audio_data, input_metadata

    async def convert_from_transport(
        self,
        transport_data: bytes,
        transport_codec: str,
        transport_metadata: dict[str, Any],
    ) -> tuple[bytes, dict[str, Any]]:
        """Convert from transport codec to canonical format."""
        try:
            if transport_codec == "opus":
                # Opus to PCM conversion would go here
                # For now, assume data is already PCM
                return await self.normalize_audio(
                    transport_data, transport_metadata, "pcm"
                )
            elif transport_codec == "pcm":
                return await self.normalize_audio(
                    transport_data, transport_metadata, "pcm"
                )
            else:
                self._logger.warning(
                    "media_gateway.unsupported_transport_codec",
                    codec=transport_codec,
                )
                return transport_data, transport_metadata

        except (ValueError, TypeError, OSError) as e:
            self._logger.error(
                "media_gateway.transport_conversion_failed", error=str(e)
            )
            return transport_data, transport_metadata

    async def convert_to_transport(
        self,
        canonical_data: bytes,
        canonical_metadata: dict[str, Any],
        transport_codec: str,
    ) -> tuple[bytes, dict[str, Any]]:
        """Convert from canonical format to transport codec."""
        try:
            if transport_codec == "opus":
                # PCM to Opus conversion would go here
                # For now, return as-is with updated metadata
                transport_metadata = canonical_metadata.copy()
                transport_metadata.update(
                    {
                        "format": "opus",
                        "sample_rate": 48000,  # Opus native rate
                    }
                )
                return canonical_data, transport_metadata
            elif transport_codec == "pcm":
                return canonical_data, canonical_metadata
            else:
                self._logger.warning(
                    "media_gateway.unsupported_transport_codec",
                    codec=transport_codec,
                )
                return canonical_data, canonical_metadata

        except (ValueError, TypeError, OSError) as e:
            self._logger.error(
                "media_gateway.transport_conversion_failed", error=str(e)
            )
            return canonical_data, canonical_metadata

    def add_to_jitter_buffer(self, audio_data: bytes, timestamp: float) -> None:
        """Add audio frame to jitter buffer."""
        if self.jitter_buffer:
            self.jitter_buffer.add_frame(audio_data, timestamp)

    def get_from_jitter_buffer(self) -> list[bytes]:
        """Get ready frames from jitter buffer."""
        if self.jitter_buffer:
            current_time = time.time()
            return self.jitter_buffer.get_ready_frames(current_time)
        return []

    def clear_jitter_buffer(self) -> None:
        """Clear jitter buffer."""
        if self.jitter_buffer:
            self.jitter_buffer.current_frames.clear()

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        avg_conversion_time = (
            self._total_conversion_time / self._conversion_count
            if self._conversion_count > 0
            else 0.0
        )

        return {
            "conversion_count": self._conversion_count,
            "total_conversion_time": self._total_conversion_time,
            "avg_conversion_time_ms": avg_conversion_time * 1000,
            "jitter_buffer_enabled": self.enable_jitter_buffer,
            "jitter_buffer_size": (
                len(self.jitter_buffer.current_frames) if self.jitter_buffer else 0
            ),
        }

    async def handle_drift_correction(
        self,
        audio_data: bytes,
        expected_timestamp: float,
        actual_timestamp: float,
    ) -> bytes:
        """Handle clock drift correction."""
        try:
            drift_ms = (actual_timestamp - expected_timestamp) * 1000.0

            # If drift is significant, apply correction
            if abs(drift_ms) > 50.0:  # 50ms threshold
                self._logger.debug(
                    "media_gateway.drift_correction",
                    drift_ms=drift_ms,
                    expected=expected_timestamp,
                    actual=actual_timestamp,
                )

                # Simple drift correction: adjust playback speed
                if drift_ms > 0:
                    # Audio is late, speed up slightly
                    return self._speed_up_audio(audio_data, min(drift_ms / 1000.0, 0.1))
                else:
                    # Audio is early, slow down slightly
                    return self._slow_down_audio(
                        audio_data, min(abs(drift_ms) / 1000.0, 0.1)
                    )

            return audio_data

        except (ValueError, TypeError, OSError) as e:
            self._logger.warning("media_gateway.drift_correction_failed", error=str(e))
            return audio_data

    def _speed_up_audio(self, audio_data: bytes, factor: float) -> bytes:
        """Speed up audio by removing samples."""
        try:
            # Simple speed up by dropping samples
            drop_ratio = int(len(audio_data) * factor)
            if drop_ratio > 0:
                return audio_data[drop_ratio:]
            return audio_data
        except Exception:
            return audio_data

    def _slow_down_audio(self, audio_data: bytes, factor: float) -> bytes:
        """Slow down audio by duplicating samples."""
        try:
            # Simple slow down by duplicating samples
            duplicate_ratio = int(len(audio_data) * factor)
            if duplicate_ratio > 0:
                return audio_data + audio_data[:duplicate_ratio]
            return audio_data
        except Exception:
            return audio_data
