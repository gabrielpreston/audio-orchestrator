"""
Standardized audio processing library for all services.

This module provides consistent audio processing capabilities across all services
in the voice pipeline, including format conversion, resampling, normalization,
and metadata extraction using librosa for robust audio processing.

REQUIRES: Services using this module must use python-ml base image or explicitly
install librosa and soundfile dependencies.
"""

import audioop
import io
import wave
from dataclasses import dataclass
from typing import Any, ClassVar

try:
    import librosa
    import numpy as np
    import soundfile as sf
except ImportError as exc:
    raise ImportError(
        f"Required audio processing libraries not available: {exc}. "
        "Services using audio processing must use python-ml base image or "
        "explicitly install librosa and soundfile."
    ) from exc


@dataclass(slots=True)
class AudioMetadata:
    """Standardized audio metadata structure."""

    sample_rate: int
    channels: int
    sample_width: int  # bytes per sample
    duration: float  # seconds
    frames: int
    format: str  # 'pcm', 'wav', etc.
    bit_depth: int  # bits per sample

    @property
    def bytes_per_second(self) -> int:
        """Calculate bytes per second."""
        return self.sample_rate * self.channels * self.sample_width

    @property
    def total_bytes(self) -> int:
        """Calculate total audio data bytes."""
        return self.frames * self.channels * self.sample_width


@dataclass(slots=True)
class AudioProcessingResult:
    """Result of audio processing operations."""

    audio_data: bytes
    metadata: AudioMetadata
    processing_info: dict[str, Any]
    success: bool
    error: str | None = None


class AudioProcessor:
    """Standardized audio processing for voice pipeline services using librosa."""

    # Standard audio formats and parameters
    STANDARD_SAMPLE_RATES: ClassVar[list[int]] = [8000, 16000, 22050, 44100, 48000]
    STANDARD_CHANNELS: ClassVar[list[int]] = [1, 2]  # mono, stereo
    STANDARD_BIT_DEPTHS: ClassVar[list[int]] = [8, 16, 24, 32]

    # Service-specific defaults
    DISCORD_DEFAULT_SAMPLE_RATE = 48000
    STT_DEFAULT_SAMPLE_RATE = 16000
    TTS_DEFAULT_SAMPLE_RATE = 22050

    def __init__(self, service_name: str = "common"):
        """Initialize audio processor for a specific service."""
        self.service_name = service_name
        self._logger = None  # Will be set by services that use logging

    def set_logger(self, logger: Any) -> None:
        """Set logger for audio processing operations."""
        self._logger = logger

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        """Log audio processing operations."""
        if self._logger:
            getattr(self._logger, level)(message, **kwargs)  # type: ignore[unreachable]

    def extract_metadata(
        self, audio_data: bytes, format_hint: str = "wav"
    ) -> AudioMetadata:
        """
        Extract metadata from audio data using librosa.

        Args:
            audio_data: Raw audio data bytes
            format_hint: Expected format ('wav', 'pcm')

        Returns:
            AudioMetadata object
        """
        try:
            # Use librosa to load and analyze audio
            if format_hint.lower() == "wav" or audio_data.startswith(b"RIFF"):
                # Load as WAV using librosa
                audio_array, sample_rate = librosa.load(
                    io.BytesIO(audio_data), sr=None, mono=False
                )
                channels = 1 if audio_array.ndim == 1 else audio_array.shape[0]

                duration = len(audio_array) / sample_rate if sample_rate > 0 else 0.0
                frames = len(audio_array)

                return AudioMetadata(
                    sample_rate=int(sample_rate),
                    channels=channels,
                    sample_width=2,  # librosa loads as float32, we'll assume 16-bit equivalent
                    duration=duration,
                    frames=frames,
                    format="wav",
                    bit_depth=16,
                )
            else:
                # For PCM data, we need to make assumptions
                return self._extract_pcm_metadata(audio_data)
        except Exception as exc:
            self._log("error", "audio.metadata_extraction_failed", error=str(exc))
            # Return default metadata
            return AudioMetadata(
                sample_rate=16000,
                channels=1,
                sample_width=2,
                duration=0.0,
                frames=0,
                format="unknown",
                bit_depth=16,
            )

    def _extract_wav_metadata(self, wav_data: bytes) -> AudioMetadata:
        """Extract metadata from WAV data."""
        with wave.open(io.BytesIO(wav_data), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frames = wav_file.getnframes()
            duration = frames / sample_rate if sample_rate > 0 else 0.0
            bit_depth = sample_width * 8

            return AudioMetadata(
                sample_rate=sample_rate,
                channels=channels,
                sample_width=sample_width,
                duration=duration,
                frames=frames,
                format="wav",
                bit_depth=bit_depth,
            )

    def _extract_pcm_metadata(
        self,
        pcm_data: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
    ) -> AudioMetadata:
        """Extract metadata from PCM data."""
        frames = len(pcm_data) // (channels * sample_width)
        duration = frames / sample_rate if sample_rate > 0 else 0.0
        bit_depth = sample_width * 8

        return AudioMetadata(
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
            duration=duration,
            frames=frames,
            format="pcm",
            bit_depth=bit_depth,
        )

    def pcm_to_wav(
        self,
        pcm_data: bytes,
        sample_rate: int,
        channels: int = 1,
        sample_width: int = 2,
    ) -> bytes:
        """
        Convert PCM data to WAV format using soundfile.

        Args:
            pcm_data: Raw PCM audio data
            sample_rate: Sample rate in Hz
            channels: Number of channels (1=mono, 2=stereo)
            sample_width: Bytes per sample (typically 2 for 16-bit)

        Returns:
            WAV-formatted audio data

        Raises:
            ValueError: If input validation fails or WAV encoding produces invalid file
        """
        # Input validation
        if not pcm_data or len(pcm_data) == 0:
            raise ValueError("Cannot encode empty PCM data")

        # Validate minimum size
        min_size = channels * sample_width
        if len(pcm_data) < min_size:
            raise ValueError(
                f"PCM too small: {len(pcm_data)} bytes (minimum: {min_size})"
            )

        # Validate alignment (PCM length must be multiple of frame size)
        frame_size = channels * sample_width
        if len(pcm_data) % frame_size != 0:
            raise ValueError(
                f"PCM length {len(pcm_data)} not multiple of frame size {frame_size}"
            )

        try:
            # Convert bytes to numpy array
            if sample_width == 2:
                dtype = np.int16
            elif sample_width == 4:
                dtype = np.int32
            else:
                raise ValueError(f"Unsupported sample width: {sample_width}")

            audio_array = np.frombuffer(pcm_data, dtype=dtype)

            # Reshape for multi-channel if needed
            if channels > 1 and audio_array.ndim == 1:
                audio_array = audio_array.reshape(-1, channels)

            # Convert to float32 for soundfile
            audio_float = audio_array.astype(np.float32)
            if sample_width == 2:
                audio_float = audio_float / 32768.0  # Normalize from int16
            elif sample_width == 4:
                audio_float = audio_float / 2147483648.0  # Normalize from int32

            # Use soundfile with proper buffer setup
            buffer = io.BytesIO()
            buffer.name = "file.wav"  # Help format detection (from soundfile docs)

            sf.write(buffer, audio_float, sample_rate, format="WAV", subtype="PCM_16")
            buffer.seek(0)  # Ensure position is at start (best practice)

            wav_bytes = buffer.getvalue()

            # Validate WAV file was created properly
            if len(wav_bytes) < 44:  # Minimum WAV header size
                raise ValueError("Generated WAV file too small (invalid header)")

            # Verify WAV can be read back (using existing validate_audio_data)
            if not self.validate_audio_data(wav_bytes, expected_format="wav"):
                raise ValueError("Generated WAV file failed validation")

            return wav_bytes
        except Exception as exc:
            self._log(
                "error",
                "audio.pcm_to_wav_failed",
                error=str(exc),
                pcm_size=len(pcm_data),
                sample_rate=sample_rate,
                channels=channels,
                sample_width=sample_width,
            )
            raise

    def wav_to_pcm(self, wav_data: bytes) -> tuple[bytes, AudioMetadata]:
        """
        Extract PCM data from WAV format using librosa.

        Args:
            wav_data: WAV-formatted audio data

        Returns:
            Tuple of (PCM data, metadata)

        Raises:
            ValueError: If input data is invalid or empty
            TypeError: If input is not bytes
        """
        # Input validation
        if not isinstance(wav_data, bytes):
            raise TypeError(f"wav_data must be bytes, got {type(wav_data).__name__}")
        if not wav_data:
            raise ValueError("wav_data cannot be empty")
        if len(wav_data) < 44:  # Minimum WAV header size
            raise ValueError(
                f"wav_data too small (minimum 44 bytes for WAV header, got {len(wav_data)} bytes)"
            )

        try:
            # Use librosa to load audio
            audio_array, sample_rate = librosa.load(
                io.BytesIO(wav_data), sr=None, mono=False
            )

            # Validate loaded audio
            if audio_array.size == 0:
                raise ValueError("Loaded audio array is empty")
            if not isinstance(sample_rate, (int, float)) or sample_rate <= 0:
                raise ValueError(
                    f"Invalid sample rate: {sample_rate} (must be positive number)"
                )

            # Convert to mono if stereo
            if audio_array.ndim > 1:
                audio_array = librosa.to_mono(audio_array)

            # Validate after mono conversion
            if audio_array.size == 0:
                raise ValueError("Audio array is empty after mono conversion")

            # Convert back to int16 PCM
            # Use 32768.0 for symmetric conversion (matches normalization factor)
            # Clamp to prevent overflow when converting back to int16
            audio_float = audio_array * 32768.0
            audio_int16 = np.clip(audio_float, -32768.0, 32767.0).astype(np.int16)
            pcm_data = audio_int16.tobytes()

            # Validate output
            if not pcm_data:
                raise ValueError("Generated PCM data is empty")

            # Create metadata
            metadata = AudioMetadata(
                sample_rate=int(sample_rate),
                channels=1,
                sample_width=2,
                duration=len(audio_array) / sample_rate,
                frames=len(audio_array),
                format="wav",
                bit_depth=16,
            )

            return pcm_data, metadata
        except (ValueError, TypeError) as exc:
            # Specific exception types with context
            self._log(
                "error",
                "audio.wav_to_pcm_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                wav_data_size=len(wav_data),
            )
            raise
        except MemoryError as exc:
            # Memory errors with context
            self._log(
                "error",
                "audio.wav_to_pcm_memory_error",
                error=str(exc),
                error_type="MemoryError",
                wav_data_size=len(wav_data),
            )
            raise
        except Exception as exc:
            # Catch-all for unexpected errors
            self._log(
                "error",
                "audio.wav_to_pcm_unexpected_error",
                error=str(exc),
                error_type=type(exc).__name__,
                wav_data_size=len(wav_data),
            )
            raise

    def resample_audio(
        self,
        audio_data: bytes,
        from_rate: int,
        to_rate: int,
        sample_width: int = 2,
    ) -> bytes:
        """
        Resample audio data to a different sample rate using librosa.

        Args:
            audio_data: Raw PCM audio data
            from_rate: Source sample rate
            to_rate: Target sample rate
            sample_width: Bytes per sample

        Returns:
            Resampled audio data

        Raises:
            ValueError: If input data is invalid, empty, or misaligned
            TypeError: If input types are incorrect
        """
        # Input validation
        if not isinstance(audio_data, bytes):
            raise TypeError(
                f"audio_data must be bytes, got {type(audio_data).__name__}"
            )
        if not isinstance(from_rate, int) or from_rate <= 0:
            raise ValueError(f"from_rate must be positive integer, got {from_rate}")
        if not isinstance(to_rate, int) or to_rate <= 0:
            raise ValueError(f"to_rate must be positive integer, got {to_rate}")
        if not isinstance(sample_width, int):
            raise TypeError(
                f"sample_width must be int, got {type(sample_width).__name__}"
            )

        # Validate empty data
        if not audio_data:
            raise ValueError("audio_data cannot be empty")

        # Validate minimum size (at least one sample)
        if len(audio_data) < sample_width:
            raise ValueError(
                f"audio_data too small (minimum {sample_width} bytes for one sample, got {len(audio_data)} bytes)"
            )

        # Validate alignment (data length must be multiple of sample_width)
        if len(audio_data) % sample_width != 0:
            raise ValueError(
                f"audio_data length ({len(audio_data)} bytes) must be multiple of sample_width ({sample_width} bytes)"
            )

        try:
            if from_rate == to_rate:
                return audio_data

            # Convert bytes to numpy array
            if sample_width == 2:
                dtype = np.int16
            elif sample_width == 4:
                dtype = np.int32
            else:
                raise ValueError(
                    f"Unsupported sample width: {sample_width}. Must be 2 (int16) or 4 (int32)"
                )

            audio_array = np.frombuffer(audio_data, dtype=dtype)

            # Convert to float32 for librosa
            audio_float = audio_array.astype(np.float32)
            if sample_width == 2:
                audio_float = audio_float / 32768.0
            elif sample_width == 4:
                audio_float = audio_float / 2147483648.0

            # Use librosa for high-quality resampling
            resampled_float = librosa.resample(
                audio_float, orig_sr=from_rate, target_sr=to_rate
            )

            # Convert back to original format
            # Clamp after multiplication to prevent overflow when converting back
            if sample_width == 2:
                resampled_float = resampled_float * 32768.0
                resampled_array = np.clip(resampled_float, -32768.0, 32767.0).astype(
                    np.int16
                )
            elif sample_width == 4:
                resampled_float = resampled_float * 2147483648.0
                resampled_array = np.clip(
                    resampled_float, -2147483648.0, 2147483647.0
                ).astype(np.int32)
            else:
                # Fallback to int16 for unsupported sample widths
                resampled_float = resampled_float * 32768.0
                resampled_array = np.clip(resampled_float, -32768.0, 32767.0).astype(
                    np.int16
                )

            resampled_data = resampled_array.tobytes()

            self._log(
                "debug",
                "audio.resampled",
                from_rate=from_rate,
                to_rate=to_rate,
                original_bytes=len(audio_data),
                resampled_bytes=len(resampled_data),
            )

            return bytes(resampled_data)
        except (ValueError, TypeError) as exc:
            # Specific exception types with context
            self._log(
                "error",
                "audio.resample_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                audio_data_length=len(audio_data),
                from_rate=from_rate,
                to_rate=to_rate,
                sample_width=sample_width,
            )
            raise
        except MemoryError as exc:
            # Memory errors with context
            self._log(
                "error",
                "audio.resample_memory_error",
                error=str(exc),
                error_type="MemoryError",
                audio_data_length=len(audio_data),
                from_rate=from_rate,
                to_rate=to_rate,
                sample_width=sample_width,
            )
            raise
        except Exception as exc:
            # Catch-all for unexpected errors
            self._log(
                "error",
                "audio.resample_unexpected_error",
                error=str(exc),
                error_type=type(exc).__name__,
                audio_data_length=len(audio_data),
                from_rate=from_rate,
                to_rate=to_rate,
                sample_width=sample_width,
            )
            raise

    def normalize_audio(
        self,
        pcm_data: bytes,
        target_rms: float = 2000.0,
        sample_width: int = 2,
        log_sample_rate: float = 0.01,
        user_id: int | None = None,
        telemetry_config: Any = None,
    ) -> tuple[bytes, float]:
        """Normalize audio to target RMS level with proper scaling."""
        try:
            if not pcm_data:
                return pcm_data, 0.0

            # Convert to numpy array
            if sample_width == 2:
                dtype = np.int16
                max_val = 32768.0
            elif sample_width == 4:
                dtype = np.int32
                max_val = 2147483648.0
            else:
                raise ValueError(f"Unsupported sample width: {sample_width}")

            array = np.frombuffer(pcm_data, dtype=dtype)
            if array.size == 0:
                return pcm_data, 0.0

            # Calculate current RMS
            current_rms = np.sqrt(np.mean(np.square(array.astype(np.float64))))

            if current_rms < 1.0:  # Avoid amplifying silence
                # Only log silence skipping occasionally to reduce verbosity
                # Sample rate can be tuned via telemetry config
                if (
                    telemetry_config
                    and telemetry_config.log_sample_audio_rate is not None
                ):
                    configured_rate = telemetry_config.log_sample_audio_rate
                else:
                    configured_rate = log_sample_rate
                if np.random.random() < max(0.0, min(1.0, configured_rate)):
                    self._log(
                        "debug",
                        "audio.normalize_skipped_silence",
                        current_rms=current_rms,
                    )
                return pcm_data, float(current_rms)

            # Scale to target RMS
            scaling_factor = target_rms / current_rms
            # Safety rails to avoid annihilating or blasting audio
            min_shrink = 1e-3  # do not shrink below this factor
            max_boost = 50.0  # do not boost above this factor
            if scaling_factor < min_shrink:
                # Sample logging via LOG_SAMPLE_AUDIO_RATE
                if (
                    telemetry_config
                    and telemetry_config.log_sample_audio_rate is not None
                ):
                    configured_rate = telemetry_config.log_sample_audio_rate
                else:
                    configured_rate = log_sample_rate
                if np.random.random() < max(0.0, min(1.0, configured_rate)):
                    self._log(
                        "debug",
                        "audio.normalize_scaling_capped",
                        scaling_factor=float(scaling_factor),
                        reason="too_small",
                    )
                scaling_factor = min_shrink
            elif scaling_factor > max_boost:
                # Sample logging via LOG_SAMPLE_AUDIO_RATE
                if (
                    telemetry_config
                    and telemetry_config.log_sample_audio_rate is not None
                ):
                    configured_rate = telemetry_config.log_sample_audio_rate
                else:
                    configured_rate = log_sample_rate
                if np.random.random() < max(0.0, min(1.0, configured_rate)):
                    self._log(
                        "debug",
                        "audio.normalize_scaling_capped",
                        scaling_factor=float(scaling_factor),
                        reason="too_large",
                    )
                scaling_factor = max_boost
            normalized_float = array.astype(np.float64) * scaling_factor
            normalized_array = np.clip(normalized_float, -max_val, max_val - 1).astype(
                dtype
            )

            # Verify new RMS
            new_rms = np.sqrt(np.mean(np.square(normalized_array.astype(np.float64))))

            # Only log normalization occasionally to reduce verbosity
            # Sample rate can be tuned via telemetry config
            if telemetry_config and telemetry_config.log_sample_audio_rate is not None:
                configured_rate = telemetry_config.log_sample_audio_rate
            else:
                configured_rate = log_sample_rate
            if np.random.random() < max(0.0, min(1.0, configured_rate)):
                log_data = {
                    "current_rms": float(current_rms),
                    "target_rms": target_rms,
                    "new_rms": float(new_rms),
                    "scaling_factor": float(scaling_factor),
                }
                if user_id is not None:
                    log_data["user_id"] = user_id

                self._log("debug", "audio.normalized", **log_data)

            return normalized_array.tobytes(), float(new_rms)
        except (ValueError, TypeError) as exc:
            # Specific exception types with context
            self._log(
                "error",
                "audio.normalize_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                pcm_length=len(pcm_data) if pcm_data else 0,
                sample_width=sample_width,
                target_rms=target_rms,
            )
            # Try to calculate RMS for graceful degradation
            try:
                fallback_rms = self.calculate_rms(pcm_data, sample_width)
                return pcm_data, fallback_rms
            except Exception:
                # If RMS calculation also fails, return 0.0
                return pcm_data, 0.0
        except MemoryError as exc:
            # Memory errors with context
            self._log(
                "error",
                "audio.normalize_memory_error",
                error=str(exc),
                error_type="MemoryError",
                pcm_length=len(pcm_data) if pcm_data else 0,
                sample_width=sample_width,
                target_rms=target_rms,
            )
            # Return original data with 0.0 RMS on memory error
            return pcm_data, 0.0
        except Exception as exc:
            # Catch-all for unexpected errors
            self._log(
                "error",
                "audio.normalize_unexpected_error",
                error=str(exc),
                error_type=type(exc).__name__,
                pcm_length=len(pcm_data) if pcm_data else 0,
                sample_width=sample_width,
                target_rms=target_rms,
            )
            # Try to calculate RMS for graceful degradation
            try:
                fallback_rms = self.calculate_rms(pcm_data, sample_width)
                return pcm_data, fallback_rms
            except Exception:
                # If RMS calculation also fails, return 0.0
                return pcm_data, 0.0

    def convert_audio_format(
        self,
        audio_data: bytes,
        from_format: str,
        to_format: str,
        from_sample_rate: int,
        to_sample_rate: int,
        from_channels: int = 1,
        to_channels: int = 1,
        from_sample_width: int = 2,
        to_sample_width: int = 2,
    ) -> AudioProcessingResult:
        """
        Convert audio between different formats and parameters.

        Args:
            audio_data: Input audio data
            from_format: Source format ('pcm', 'wav')
            to_format: Target format ('pcm', 'wav')
            from_sample_rate: Source sample rate
            to_sample_rate: Target sample rate
            from_channels: Source channels
            to_channels: Target channels
            from_sample_width: Source sample width
            to_sample_width: Target sample width

        Returns:
            AudioProcessingResult with converted data and metadata
        """
        # Initialize processing_info early for error returns
        processing_info: dict[str, Any] = {
            "from_format": from_format,
            "to_format": to_format,
            "from_sample_rate": from_sample_rate,
            "to_sample_rate": to_sample_rate,
            "from_channels": from_channels,
            "to_channels": to_channels,
            "from_sample_width": from_sample_width,
            "to_sample_width": to_sample_width,
        }

        # Validate input before processing
        if not audio_data or len(audio_data) == 0:
            error_msg = "Cannot convert empty audio data"
            self._log("error", "audio.format_conversion_failed", error=error_msg)
            return AudioProcessingResult(
                audio_data=audio_data,
                metadata=self.extract_metadata(audio_data, from_format),
                processing_info={
                    **processing_info,
                    "success": False,
                    "error": error_msg,
                },
                success=False,
                error=error_msg,
            )

        try:
            # Extract PCM data if input is WAV
            if from_format.lower() == "wav":
                pcm_data, input_metadata = self.wav_to_pcm(audio_data)
                from_sample_rate = input_metadata.sample_rate
                from_channels = input_metadata.channels
                from_sample_width = input_metadata.sample_width
            else:
                pcm_data = audio_data

            # Resample if needed
            if from_sample_rate != to_sample_rate:
                pcm_data = self.resample_audio(
                    pcm_data, from_sample_rate, to_sample_rate, from_sample_width
                )

            # Convert channels if needed (simplified - just duplicate or drop)
            if from_channels != to_channels:
                pcm_data = self._convert_channels(
                    pcm_data, from_channels, to_channels, to_sample_width
                )

            # Convert sample width if needed
            if from_sample_width != to_sample_width:
                pcm_data = self._convert_sample_width(
                    pcm_data, from_sample_width, to_sample_width
                )

            # Convert to target format
            if to_format.lower() == "wav":
                output_data = self.pcm_to_wav(
                    pcm_data, to_sample_rate, to_channels, to_sample_width
                )
            else:
                output_data = pcm_data

            # Create metadata
            metadata = AudioMetadata(
                sample_rate=to_sample_rate,
                channels=to_channels,
                sample_width=to_sample_width,
                duration=len(pcm_data)
                / (to_sample_rate * to_channels * to_sample_width),
                frames=len(pcm_data) // (to_channels * to_sample_width),
                format=to_format,
                bit_depth=to_sample_width * 8,
            )

            processing_info.update(
                {
                    "success": True,
                    "input_bytes": len(audio_data),
                    "output_bytes": len(output_data),
                    "compression_ratio": (
                        len(output_data) / len(audio_data)
                        if len(audio_data) > 0
                        else 1.0
                    ),
                }
            )

            return AudioProcessingResult(
                audio_data=output_data,
                metadata=metadata,
                processing_info=processing_info,
                success=True,
            )

        except Exception as exc:
            # Enhanced error logging
            self._log(
                "error",
                "audio.format_conversion_failed",
                error=str(exc),
                input_size=len(audio_data),
                from_format=from_format,
                to_format=to_format,
            )
            return AudioProcessingResult(
                audio_data=audio_data,
                metadata=self.extract_metadata(audio_data, from_format),
                processing_info={
                    **processing_info,
                    "success": False,
                    "error": str(exc),
                },
                success=False,
                error=str(exc),
            )

    def _convert_channels(
        self, pcm_data: bytes, from_channels: int, to_channels: int, sample_width: int
    ) -> bytes:
        """Convert between mono and stereo."""
        if from_channels == to_channels:
            return pcm_data

        if from_channels == 1 and to_channels == 2:
            # Mono to stereo - duplicate channel
            return audioop.tomono(pcm_data, sample_width, 1, 1)
        elif from_channels == 2 and to_channels == 1:
            # Stereo to mono - mix channels
            return audioop.tomono(pcm_data, sample_width, 1, 1)
        else:
            # Unsupported conversion
            return pcm_data

    def _convert_sample_width(
        self, pcm_data: bytes, from_width: int, to_width: int
    ) -> bytes:
        """Convert between different sample widths."""
        if from_width == to_width:
            return pcm_data

        if from_width == 1 and to_width == 2:
            return audioop.lin2lin(pcm_data, 1, 2)
        elif from_width == 2 and to_width == 1:
            return audioop.lin2lin(pcm_data, 2, 1)
        elif from_width == 2 and to_width == 4:
            return audioop.lin2lin(pcm_data, 2, 4)
        elif from_width == 4 and to_width == 2:
            return audioop.lin2lin(pcm_data, 4, 2)
        else:
            # Unsupported conversion
            return pcm_data

    def calculate_rms(self, pcm_data: bytes, sample_width: int = 2) -> float:
        """Calculate RMS (Root Mean Square) of PCM audio data using librosa."""
        try:
            if not pcm_data:
                return 0.0

            # Convert to numpy array
            if sample_width == 2:
                array = np.frombuffer(pcm_data, dtype=np.int16)
            elif sample_width == 4:
                array = np.frombuffer(pcm_data, dtype=np.int32)
            else:
                return 0.0

            if array.size == 0:
                return 0.0

            # Convert to float32 for librosa
            audio_float = array.astype(np.float32)
            if sample_width == 2:
                audio_float = audio_float / 32768.0
            elif sample_width == 4:
                audio_float = audio_float / 2147483648.0

            # Use librosa's RMS calculation
            rms = librosa.feature.rms(y=audio_float)[0]
            return float(np.mean(rms).item())
        except Exception:
            return 0.0

    def validate_audio_data(
        self, audio_data: bytes, expected_format: str = "wav"
    ) -> bool:
        """Validate audio data format and integrity."""
        try:
            if expected_format.lower() == "wav":
                # Check for WAV header
                if not audio_data.startswith(b"RIFF"):
                    return False
                # Try to open as WAV
                with wave.open(io.BytesIO(audio_data), "rb") as wav_file:
                    wav_file.getnframes()  # This will raise an exception if invalid
                return True
            else:
                # For PCM, just check if we have data
                return len(audio_data) > 0
        except Exception:
            return False

    def get_service_defaults(self, service_name: str) -> dict[str, Any]:
        """Get default audio parameters for a specific service."""
        defaults = {
            "discord": {
                "sample_rate": self.DISCORD_DEFAULT_SAMPLE_RATE,
                "channels": 1,
                "sample_width": 2,
                "format": "pcm",
            },
            "stt": {
                "sample_rate": self.STT_DEFAULT_SAMPLE_RATE,
                "channels": 1,
                "sample_width": 2,
                "format": "wav",
            },
            "tts": {
                "sample_rate": self.TTS_DEFAULT_SAMPLE_RATE,
                "channels": 1,
                "sample_width": 2,
                "format": "wav",
            },
            "orchestrator": {
                "sample_rate": self.TTS_DEFAULT_SAMPLE_RATE,
                "channels": 1,
                "sample_width": 2,
                "format": "wav",
            },
        }
        return defaults.get(service_name.lower(), defaults["stt"])


# Convenience functions for backward compatibility
def create_audio_processor(service_name: str = "common") -> AudioProcessor:
    """Create an audio processor for a specific service."""
    return AudioProcessor(service_name)


def pcm_to_wav(
    pcm_data: bytes, sample_rate: int, channels: int = 1, sample_width: int = 2
) -> bytes:
    """Convert PCM to WAV format."""
    processor = AudioProcessor()
    return processor.pcm_to_wav(pcm_data, sample_rate, channels, sample_width)


def wav_to_pcm(wav_data: bytes) -> tuple[bytes, AudioMetadata]:
    """Convert WAV to PCM format."""
    processor = AudioProcessor()
    return processor.wav_to_pcm(wav_data)


def resample_audio(
    audio_data: bytes, from_rate: int, to_rate: int, sample_width: int = 2
) -> bytes:
    """Resample audio data."""
    processor = AudioProcessor()
    return processor.resample_audio(audio_data, from_rate, to_rate, sample_width)


def normalize_audio(
    pcm_data: bytes,
    target_rms: float = 2000.0,
    sample_width: int = 2,
    user_id: int | None = None,
) -> tuple[bytes, float]:
    """Normalize audio to target RMS."""
    processor = AudioProcessor()
    return processor.normalize_audio(
        pcm_data, target_rms, sample_width, user_id=user_id
    )


def calculate_rms(pcm_data: bytes, sample_width: int = 2) -> float:
    """Calculate RMS of PCM audio data (normalized 0-1).

    Note: This function returns normalized RMS (0-1) for backward compatibility.
    For threshold comparisons, use calculate_rms_int16() instead.

    Args:
        pcm_data: PCM audio data bytes
        sample_width: Bytes per sample (2 for int16, 4 for int32)

    Returns:
        Normalized RMS value (0-1)
    """
    processor = AudioProcessor()
    return processor.calculate_rms(pcm_data, sample_width)


def calculate_rms_int16(pcm_data: bytes, sample_width: int = 2) -> float:
    """Calculate RMS in int16 domain (0-32767 for 16-bit audio).

    This is the primary function for threshold comparisons and filtering.
    Returns RMS in the native PCM format domain, making threshold values
    intuitive (e.g., 10-1000 range for typical audio levels).

    Args:
        pcm_data: PCM audio data bytes
        sample_width: Bytes per sample (2 for int16, 4 for int32)

    Returns:
        RMS value in int16 domain (0-32767 for 16-bit, 0-2147483647 for 32-bit)

    Example:
        >>> pcm = b"\\x00\\x01\\x02\\x03"
        >>> rms = calculate_rms_int16(pcm, sample_width=2)
        >>> # rms will be in range 0-32767
    """
    # Type validation
    if not isinstance(pcm_data, bytes):
        raise TypeError(f"pcm_data must be bytes, got {type(pcm_data).__name__}")
    if not isinstance(sample_width, int):
        raise TypeError(f"sample_width must be int, got {type(sample_width).__name__}")

    # Sample width validation
    if sample_width not in (2, 4):
        raise ValueError(
            f"Unsupported sample_width: {sample_width}. Must be 2 (int16) or 4 (int32)"
        )

    try:
        if not pcm_data:
            return 0.0

        # Use audioop.rms() as primary method (fast, standard library)
        try:
            rms = audioop.rms(pcm_data, sample_width)
            return float(rms)
        except (audioop.error, OSError) as exc:
            # Fallback to numpy if audioop fails
            # Log fallback for debugging
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(
                "audioop.rms failed, using numpy fallback",
                extra={
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "pcm_length": len(pcm_data),
                    "sample_width": sample_width,
                },
            )

            if sample_width == 2:
                array = np.frombuffer(pcm_data, dtype=np.int16)
            elif sample_width == 4:
                array = np.frombuffer(pcm_data, dtype=np.int32)
            else:
                # This should not happen due to validation above, but keep for safety
                return 0.0

            if array.size == 0:
                return 0.0

            # Calculate RMS directly in int domain
            rms = np.sqrt(np.mean(array.astype(np.float64) ** 2))
            return float(rms)

    except (ValueError, TypeError, MemoryError) as exc:
        # Log specific error types with context
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            "calculate_rms_int16 failed",
            extra={
                "error": str(exc),
                "error_type": type(exc).__name__,
                "pcm_length": len(pcm_data) if pcm_data else 0,
                "sample_width": sample_width,
            },
        )
        return 0.0
    except Exception as exc:
        # Catch-all for unexpected errors
        import logging

        logger = logging.getLogger(__name__)
        logger.error(
            "calculate_rms_int16 unexpected error",
            extra={
                "error": str(exc),
                "error_type": type(exc).__name__,
                "pcm_length": len(pcm_data) if pcm_data else 0,
                "sample_width": sample_width,
            },
        )
        return 0.0


def int16_to_normalized(rms_int16: float) -> float:
    """Convert RMS from int16 domain to normalized (0-1).

    Args:
        rms_int16: RMS value in int16 domain (0-32767)

    Returns:
        Normalized RMS value (0-1)

    Example:
        >>> rms_int16 = 16384.0  # Half of max int16
        >>> rms_norm = int16_to_normalized(rms_int16)
        >>> # rms_norm ≈ 0.5
    """
    if rms_int16 <= 0.0:
        return 0.0
    # Normalize by max int16 value (32768.0, not 32767.0, for symmetric range)
    return rms_int16 / 32768.0


def normalized_to_int16(rms_normalized: float) -> float:
    """Convert RMS from normalized (0-1) to int16 domain.

    Args:
        rms_normalized: Normalized RMS value (0-1)

    Returns:
        RMS value in int16 domain (0-32767)

    Example:
        >>> rms_norm = 0.5
        >>> rms_int16 = normalized_to_int16(rms_norm)
        >>> # rms_int16 ≈ 16384.0
    """
    if rms_normalized <= 0.0:
        return 0.0
    # Convert to int16 domain (32768.0 for symmetric range)
    return rms_normalized * 32768.0
