"""
Debug file utilities for saving debug data across all services.

This module provides a centralized way to save debug files grouped by correlation_id
in a flattened directory structure: debug/correlation_id/
"""

import json
import os
import struct
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import structlog


class DebugFileManager:
    """Manages debug file saving with correlation-based organization."""

    def __init__(self, base_dir: str = "/app/debug", enabled_env_var: str = "DEBUG_SAVE"):
        """
        Initialize the debug file manager.

        Args:
            base_dir: Base directory for debug files (default: /app/debug)
            enabled_env_var: Environment variable name to check if debug saving is enabled
        """
        self.base_dir = Path(base_dir)
        self.enabled_env_var = enabled_env_var
        self._logger = structlog.get_logger(service="common", component="debug")

    def is_enabled(self) -> bool:
        """Check if debug saving is enabled via environment variable."""
        return os.getenv(self.enabled_env_var, "false").lower() == "true"

    def save_text_file(
        self,
        correlation_id: str,
        content: str,
        filename_prefix: str = "debug",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Path]:
        """
        Save text content to a debug file.

        Args:
            correlation_id: Unique identifier for grouping files
            content: Text content to save
            filename_prefix: Prefix for the filename (default: "debug")
            metadata: Optional metadata to include in filename

        Returns:
            Path to saved file, or None if debug saving is disabled
        """
        if not self.is_enabled():
            return None

        try:
            correlation_dir = self._ensure_correlation_dir(correlation_id)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Create filename with optional metadata suffix
            metadata_suffix = (
                f"_{metadata.get('suffix', '')}" if metadata and metadata.get("suffix") else ""
            )
            filename = f"{timestamp}_{filename_prefix}{metadata_suffix}.txt"
            file_path = correlation_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            self._logger.info(
                "debug.text_file_saved",
                correlation_id=correlation_id,
                file_path=str(file_path),
                content_length=len(content),
            )

            return file_path

        except Exception as exc:
            self._logger.error(
                "debug.text_file_save_failed",
                correlation_id=correlation_id,
                error=str(exc),
            )
            return None

    def save_audio_file(
        self,
        correlation_id: str,
        audio_data: bytes,
        filename_prefix: str = "audio",
        convert_to_wav: bool = True,
    ) -> Optional[Path]:
        """
        Save audio data to a debug file.

        Args:
            correlation_id: Unique identifier for grouping files
            audio_data: Raw audio data bytes
            filename_prefix: Prefix for the filename (default: "audio")
            convert_to_wav: Whether to convert raw PCM to WAV format

        Returns:
            Path to saved file, or None if debug saving is disabled
        """
        if not self.is_enabled():
            return None

        try:
            correlation_dir = self._ensure_correlation_dir(correlation_id)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{filename_prefix}.wav"
            file_path = correlation_dir / filename

            # Convert raw PCM to WAV if requested
            if convert_to_wav:
                wav_data = self._convert_raw_to_wav(audio_data)
            else:
                wav_data = audio_data

            with open(file_path, "wb") as f:
                f.write(wav_data)

            self._logger.info(
                "debug.audio_file_saved",
                correlation_id=correlation_id,
                file_path=str(file_path),
                size_bytes=len(wav_data),
            )

            return file_path

        except Exception as exc:
            self._logger.error(
                "debug.audio_file_save_failed",
                correlation_id=correlation_id,
                error=str(exc),
            )
            return None

    def save_json_file(
        self,
        correlation_id: str,
        data: Dict[str, Any],
        filename_prefix: str = "data",
    ) -> Optional[Path]:
        """
        Save JSON data to a debug file.

        Args:
            correlation_id: Unique identifier for grouping files
            data: Dictionary to save as JSON
            filename_prefix: Prefix for the filename (default: "data")

        Returns:
            Path to saved file, or None if debug saving is disabled
        """
        if not self.is_enabled():
            return None

        try:
            correlation_dir = self._ensure_correlation_dir(correlation_id)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{filename_prefix}.json"
            file_path = correlation_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            self._logger.info(
                "debug.json_file_saved",
                correlation_id=correlation_id,
                file_path=str(file_path),
                data_keys=list(data.keys()) if isinstance(data, dict) else "non-dict",
            )

            return file_path

        except Exception as exc:
            self._logger.error(
                "debug.json_file_save_failed",
                correlation_id=correlation_id,
                error=str(exc),
            )
            return None

    def save_manifest(
        self,
        correlation_id: str,
        metadata: Dict[str, Any],
        files: Optional[Dict[str, str]] = None,
        stats: Optional[Dict[str, Any]] = None,
    ) -> Optional[Path]:
        """
        Save a manifest file with metadata about the debug session.

        Args:
            correlation_id: Unique identifier for grouping files
            metadata: Metadata about the session
            files: Dictionary of file paths and descriptions
            stats: Statistics about the session

        Returns:
            Path to saved manifest file, or None if debug saving is disabled
        """
        if not self.is_enabled():
            return None

        try:
            correlation_dir = self._ensure_correlation_dir(correlation_id)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_manifest.json"
            file_path = correlation_dir / filename

            manifest = {
                "correlation_id": correlation_id,
                "timestamp": timestamp,
                "datetime": datetime.now().isoformat(),
                "metadata": metadata,
                "files": files or {},
                "stats": stats or {},
            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

            self._logger.info(
                "debug.manifest_saved",
                correlation_id=correlation_id,
                file_path=str(file_path),
            )

            return file_path

        except Exception as exc:
            self._logger.error(
                "debug.manifest_save_failed",
                correlation_id=correlation_id,
                error=str(exc),
            )
            return None

    def _ensure_correlation_dir(self, correlation_id: str) -> Path:
        """Ensure the correlation directory exists."""
        self.base_dir.mkdir(exist_ok=True)
        correlation_dir = self.base_dir / correlation_id
        correlation_dir.mkdir(exist_ok=True)
        return correlation_dir

    def _convert_raw_to_wav(self, audio_data: bytes) -> bytes:
        """
        Convert raw PCM audio data to WAV format.

        This is a simplified version - in production you might want to use
        a proper audio library like pydub or librosa.
        """
        # Assume 16-bit PCM, 48kHz, mono for now
        sample_rate = 48000
        num_channels = 1
        sample_width = 2  # 16-bit = 2 bytes per sample

        # Create WAV header
        riff_id = b"RIFF"
        file_size = 36 + len(audio_data)
        riff_format = b"WAVE"

        fmt_id = b"fmt "
        fmt_size = 16
        audio_format = 1  # PCM
        byte_rate = sample_rate * num_channels * sample_width
        block_align = num_channels * sample_width

        data_id = b"data"
        data_size = len(audio_data)

        # Pack the header
        riff_chunk = struct.pack("<4sI4s", riff_id, file_size, riff_format)
        fmt_chunk = struct.pack(
            "<4sIHHIIHH",
            fmt_id,
            fmt_size,
            audio_format,
            num_channels,
            sample_rate,
            byte_rate,
            block_align,
            sample_width * 8,
        )

        return riff_chunk + fmt_chunk + struct.pack("<4sI", data_id, data_size) + audio_data


# Convenience functions for easy usage
def get_debug_manager(service_name: str = "common") -> DebugFileManager:
    """Get a debug manager instance for a specific service."""
    return DebugFileManager(enabled_env_var=f"{service_name.upper()}_DEBUG_SAVE")


def save_debug_text(
    correlation_id: str,
    content: str,
    service_name: str = "common",
    filename_prefix: str = "debug",
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Path]:
    """Convenience function to save debug text."""
    manager = get_debug_manager(service_name)
    return manager.save_text_file(correlation_id, content, filename_prefix, metadata)


def save_debug_audio(
    correlation_id: str,
    audio_data: bytes,
    service_name: str = "common",
    filename_prefix: str = "audio",
    convert_to_wav: bool = True,
) -> Optional[Path]:
    """Convenience function to save debug audio."""
    manager = get_debug_manager(service_name)
    return manager.save_audio_file(correlation_id, audio_data, filename_prefix, convert_to_wav)


def save_debug_json(
    correlation_id: str,
    data: Dict[str, Any],
    service_name: str = "common",
    filename_prefix: str = "data",
) -> Optional[Path]:
    """Convenience function to save debug JSON."""
    manager = get_debug_manager(service_name)
    return manager.save_json_file(correlation_id, data, filename_prefix)


def save_debug_manifest(
    correlation_id: str,
    metadata: Dict[str, Any],
    service_name: str = "common",
    files: Optional[Dict[str, str]] = None,
    stats: Optional[Dict[str, Any]] = None,
) -> Optional[Path]:
    """Convenience function to save debug manifest."""
    manager = get_debug_manager(service_name)
    return manager.save_manifest(correlation_id, metadata, files, stats)
