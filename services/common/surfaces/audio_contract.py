"""
Canonical audio contract implementation.

This module enforces the standardized audio format requirements
across all surface adapters for consistent processing.
"""

from __future__ import annotations

import audioop
import io
import wave
from dataclasses import dataclass
from typing import Any

from services.common.logging import get_logger


# Note: numpy and soundfile are optional dependencies for advanced audio processing


logger = get_logger(__name__)


@dataclass
class AudioContractSpec:
    """Canonical audio contract specification."""

    # Core format requirements
    sample_rate: int = 16000  # 16 kHz canonical rate
    channels: int = 1  # Mono only
    sample_width: int = 2  # 16-bit samples
    bit_depth: int = 16  # 16-bit depth

    # Frame requirements
    frame_duration_ms: float = 20.0  # 20ms frames
    frame_size_samples: int = 320  # 16000 * 0.02

    # Transport codec (for network efficiency)
    transport_codec: str = "opus"  # Opus for transport
    transport_sample_rate: int = 48000  # Opus native rate

    @property
    def frame_size_bytes(self) -> int:
        """Frame size in bytes."""
        return self.frame_size_samples * self.channels * self.sample_width

    @property
    def bytes_per_second(self) -> int:
        """Bytes per second for canonical format."""
        return self.sample_rate * self.channels * self.sample_width


class AudioContract:
    """Enforces canonical audio contract across all surfaces."""

    def __init__(self, spec: AudioContractSpec | None = None) -> None:
        self.spec = spec or AudioContractSpec()
        self._logger = get_logger(__name__)

    def validate_audio_data(self, audio_data: bytes, metadata: dict[str, Any]) -> bool:
        """Validate audio data against canonical contract."""
        try:
            # Check basic requirements
            if not audio_data:
                self._logger.warning("audio_contract.empty_data")
                return False

            # Validate sample rate
            if metadata.get("sample_rate") != self.spec.sample_rate:
                self._logger.warning(
                    "audio_contract.invalid_sample_rate",
                    expected=self.spec.sample_rate,
                    actual=metadata.get("sample_rate"),
                )
                return False

            # Validate channels
            if metadata.get("channels", 1) != self.spec.channels:
                self._logger.warning(
                    "audio_contract.invalid_channels",
                    expected=self.spec.channels,
                    actual=metadata.get("channels", 1),
                )
                return False

            # Validate sample width
            if metadata.get("sample_width", 2) != self.spec.sample_width:
                self._logger.warning(
                    "audio_contract.invalid_sample_width",
                    expected=self.spec.sample_width,
                    actual=metadata.get("sample_width", 2),
                )
                return False

            return True

        except (ValueError, TypeError, OSError) as e:
            self._logger.error("audio_contract.validation_error", error=str(e))
            return False

    def normalize_audio(
        self, audio_data: bytes, metadata: dict[str, Any]
    ) -> tuple[bytes, dict[str, Any]]:
        """Normalize audio data to canonical contract."""
        try:
            # Extract current metadata
            current_rate = metadata.get("sample_rate", self.spec.sample_rate)
            current_channels = metadata.get("channels", 1)
            current_width = metadata.get("sample_width", 2)

            # Resample if needed
            if current_rate != self.spec.sample_rate:
                audio_data = self._resample_audio(
                    audio_data, current_rate, self.spec.sample_rate, current_width
                )
                current_rate = self.spec.sample_rate

            # Convert to mono if needed
            if current_channels != self.spec.channels:
                audio_data = self._convert_to_mono(
                    audio_data, current_channels, current_width
                )
                current_channels = self.spec.channels

            # Convert to 16-bit if needed
            if current_width != self.spec.sample_width:
                audio_data = self._convert_sample_width(
                    audio_data, current_width, self.spec.sample_width
                )
                current_width = self.spec.sample_width

            # Update metadata
            normalized_metadata = {
                "sample_rate": self.spec.sample_rate,
                "channels": self.spec.channels,
                "sample_width": self.spec.sample_width,
                "bit_depth": self.spec.bit_depth,
                "format": "pcm",
            }

            self._logger.debug(
                "audio_contract.normalized",
                original_rate=metadata.get("sample_rate"),
                original_channels=metadata.get("channels", 1),
                original_width=metadata.get("sample_width", 2),
            )

            return audio_data, normalized_metadata

        except (ValueError, TypeError, OSError) as e:
            self._logger.error("audio_contract.normalization_error", error=str(e))
            return audio_data, metadata

    def _resample_audio(
        self, audio_data: bytes, from_rate: int, to_rate: int, sample_width: int
    ) -> bytes:
        """Resample audio using audioop."""
        try:
            # Use audioop for simple resampling
            resampled, _ = audioop.ratecv(
                audio_data, sample_width, 1, from_rate, to_rate, None
            )
            return resampled
        except (ValueError, TypeError, OSError) as e:
            self._logger.warning("audio_contract.resample_failed", error=str(e))
            return audio_data

    def _convert_to_mono(
        self, audio_data: bytes, channels: int, sample_width: int
    ) -> bytes:
        """Convert stereo to mono."""
        if channels == 1:
            return audio_data

        try:
            # Simple downmix: average left and right channels
            if channels == 2:
                return audioop.tomono(audio_data, sample_width, 0.5, 0.5)
            else:
                # For more than 2 channels, just take the first channel
                return audioop.tomono(audio_data, sample_width, 1.0, 0.0)
        except (ValueError, TypeError, OSError) as e:
            self._logger.warning("audio_contract.mono_conversion_failed", error=str(e))
            return audio_data

    def _convert_sample_width(
        self, audio_data: bytes, from_width: int, to_width: int
    ) -> bytes:
        """Convert sample width."""
        if from_width == to_width:
            return audio_data

        try:
            if from_width == 1 and to_width == 2:
                # 8-bit to 16-bit
                return audioop.lin2lin(audio_data, 1, 2)
            elif from_width == 2 and to_width == 1:
                # 16-bit to 8-bit
                return audioop.lin2lin(audio_data, 2, 1)
            else:
                # Use audioop for other conversions
                return audioop.lin2lin(audio_data, from_width, to_width)
        except (ValueError, TypeError, OSError) as e:
            self._logger.warning("audio_contract.width_conversion_failed", error=str(e))
            return audio_data

    def create_wav_header(self, audio_data: bytes, metadata: dict[str, Any]) -> bytes:
        """Create WAV header for audio data."""
        try:
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wav_file:
                wav_file.setnchannels(metadata.get("channels", 1))
                wav_file.setsampwidth(metadata.get("sample_width", 2))
                wav_file.setframerate(metadata.get("sample_rate", 16000))
                wav_file.writeframes(audio_data)
            return buffer.getvalue()
        except (ValueError, TypeError, OSError) as e:
            self._logger.error("audio_contract.wav_header_failed", error=str(e))
            return audio_data

    def extract_metadata(self, audio_data: bytes) -> dict[str, Any]:
        """Extract metadata from audio data."""
        try:
            # Try to read as WAV first
            if audio_data.startswith(b"RIFF"):
                with wave.open(io.BytesIO(audio_data), "rb") as wav_file:
                    return {
                        "sample_rate": wav_file.getframerate(),
                        "channels": wav_file.getnchannels(),
                        "sample_width": wav_file.getsampwidth(),
                        "bit_depth": wav_file.getsampwidth() * 8,
                        "format": "wav",
                        "frames": wav_file.getnframes(),
                        "duration": wav_file.getnframes() / wav_file.getframerate(),
                    }
            else:
                # Assume raw PCM
                return {
                    "sample_rate": self.spec.sample_rate,
                    "channels": self.spec.channels,
                    "sample_width": self.spec.sample_width,
                    "bit_depth": self.spec.bit_depth,
                    "format": "pcm",
                    "frames": len(audio_data)
                    // (self.spec.channels * self.spec.sample_width),
                }
        except (ValueError, TypeError, OSError) as e:
            self._logger.warning(
                "audio_contract.metadata_extraction_failed", error=str(e)
            )
            return {
                "sample_rate": self.spec.sample_rate,
                "channels": self.spec.channels,
                "sample_width": self.spec.sample_width,
                "bit_depth": self.spec.bit_depth,
                "format": "pcm",
            }
