"""
Debug file utilities for saving debug data across all services.

This module provides a centralized way to save debug files grouped by correlation_id
in a flattened directory structure: debug/correlation_id/

All debug data (except WAV files) is consolidated into a single debug log file
per correlation ID for easier analysis and debugging.
"""

import json
import os
import struct
from datetime import datetime
from pathlib import Path
from typing import Any

from services.common.logging import get_logger


class DebugFileManager:
    """Manages debug file saving with correlation-based organization."""

    def __init__(
        self, base_dir: str = "/app/debug", enabled_env_var: str = "DEBUG_SAVE"
    ):
        """
        Initialize the debug file manager.

        Args:
            base_dir: Base directory for debug files (default: /app/debug)
            enabled_env_var: Environment variable name to check if debug saving is enabled
        """
        self.base_dir = Path(base_dir)
        self.enabled_env_var = enabled_env_var
        self._logger = get_logger("debug", service_name="common")

    def is_enabled(self) -> bool:
        """Check if debug saving is enabled via environment variable."""
        return os.getenv(self.enabled_env_var, "false").lower() == "true"

    def _append_to_debug_log(
        self,
        correlation_id: str,
        entry_type: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Append an entry to the consolidated debug log file.

        Args:
            correlation_id: Unique identifier for grouping files
            entry_type: Type of debug entry (e.g., "text", "metadata", "audio_info")
            content: Content to append
            metadata: Optional metadata to include
        """
        if not self.is_enabled():
            return

        try:
            correlation_dir = self._ensure_correlation_dir(correlation_id)
            debug_log_path = correlation_dir / "debug_log.json"

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[
                :-3
            ]  # Include milliseconds

            # Create log entry
            log_entry = {
                "timestamp": timestamp,
                "type": entry_type,
                "content": content,
                "metadata": metadata or {},
            }

            # Load existing entries or create new list
            existing_entries = []
            if debug_log_path.exists():
                try:
                    with open(debug_log_path, encoding="utf-8") as f:
                        existing_data = json.load(f)
                        if (
                            isinstance(existing_data, dict)
                            and "entries" in existing_data
                        ):
                            existing_entries = existing_data["entries"]
                        elif isinstance(existing_data, list):
                            existing_entries = existing_data
                except (json.JSONDecodeError, KeyError):
                    # If file is corrupted or in old format, start fresh
                    existing_entries = []

            # Add new entry
            existing_entries.append(log_entry)

            # Create structured debug log
            debug_log = {
                "correlation_id": correlation_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "total_entries": len(existing_entries),
                "entries": existing_entries,
            }

            # Save to JSON file
            with open(debug_log_path, "w", encoding="utf-8") as f:
                json.dump(debug_log, f, indent=2, default=str)

            self._logger.info(
                "debug.log_entry_appended",
                correlation_id=correlation_id,
                entry_type=entry_type,
                log_path=str(debug_log_path),
                total_entries=len(existing_entries),
            )

        except Exception as exc:
            self._logger.error(
                "debug.log_append_failed",
                correlation_id=correlation_id,
                entry_type=entry_type,
                error=str(exc),
            )

    def save_text_file(
        self,
        correlation_id: str,
        content: str,
        filename_prefix: str = "debug",
        metadata: dict[str, Any] | None = None,
    ) -> Path | None:
        """
        Save text content to the consolidated debug log.

        Args:
            correlation_id: Unique identifier for grouping files
            content: Text content to save
            filename_prefix: Prefix for the filename (used for entry type)
            metadata: Optional metadata to include

        Returns:
            Path to consolidated debug log file, or None if debug saving is disabled
        """
        if not self.is_enabled():
            return None

        try:
            # Append to consolidated debug log
            self._append_to_debug_log(
                correlation_id=correlation_id,
                entry_type=f"text_{filename_prefix}",
                content=content,
                metadata=metadata,
            )

            # Return path to the consolidated debug log
            correlation_dir = self._ensure_correlation_dir(correlation_id)
            return correlation_dir / "debug_log.json"

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
        sample_rate: int = 48000,
    ) -> Path | None:
        """
        Save audio data to a separate WAV file and log audio info to consolidated log.

        Args:
            correlation_id: Unique identifier for grouping files
            audio_data: Raw audio data bytes
            filename_prefix: Prefix for the filename (default: "audio")
            convert_to_wav: Whether to convert raw PCM to WAV format
            sample_rate: Sample rate for WAV conversion (default: 48000)

        Returns:
            Path to saved WAV file, or None if debug saving is disabled
        """
        if not self.is_enabled():
            return None

        try:
            correlation_dir = self._ensure_correlation_dir(correlation_id)
            filename = f"{filename_prefix}.wav"
            file_path = correlation_dir / filename

            # Convert raw PCM to WAV if requested
            if convert_to_wav:
                logger = get_logger(
                    "debug", correlation_id=correlation_id, service_name="common"
                )
                logger.info(
                    "debug.audio_conversion_start",
                    correlation_id=correlation_id,
                    filename_prefix=filename_prefix,
                    sample_rate=sample_rate,
                    original_size=len(audio_data),
                )
                wav_data = self._convert_raw_to_wav(audio_data, sample_rate)
                logger.info(
                    "debug.audio_conversion_complete",
                    correlation_id=correlation_id,
                    filename_prefix=filename_prefix,
                    sample_rate=sample_rate,
                    wav_size=len(wav_data),
                )
            else:
                wav_data = audio_data

            # Save WAV file separately
            with open(file_path, "wb") as f:
                f.write(wav_data)

            # Log audio information to consolidated debug log
            audio_info = f"""Audio File: {filename}
Size: {len(wav_data)} bytes
Format: WAV
Original Size: {len(audio_data)} bytes
Converted: {convert_to_wav}
Sample Rate: {sample_rate} Hz"""

            self._append_to_debug_log(
                correlation_id=correlation_id,
                entry_type=f"audio_{filename_prefix}",
                content=audio_info,
                metadata={
                    "filename": filename,
                    "size_bytes": len(wav_data),
                    "original_size_bytes": len(audio_data),
                    "converted": convert_to_wav,
                    "format": "WAV",
                },
            )

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
        data: dict[str, Any],
        filename_prefix: str = "data",
    ) -> Path | None:
        """
        Save JSON data to the consolidated debug log.

        Args:
            correlation_id: Unique identifier for grouping files
            data: Dictionary to save as JSON
            filename_prefix: Prefix for the filename (used for entry type)

        Returns:
            Path to consolidated debug log file, or None if debug saving is disabled
        """
        if not self.is_enabled():
            return None

        try:
            # Format JSON data for the consolidated log
            json_content = json.dumps(data, indent=2)

            # Append to consolidated debug log
            self._append_to_debug_log(
                correlation_id=correlation_id,
                entry_type=f"metadata_{filename_prefix}",
                content=json_content,
                metadata={
                    "data_keys": (
                        list(data.keys()) if isinstance(data, dict) else "non-dict"
                    ),
                    "data_type": "json",
                },
            )

            # Return path to the consolidated debug log
            correlation_dir = self._ensure_correlation_dir(correlation_id)
            return correlation_dir / "debug_log.json"

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
        metadata: dict[str, Any],
        files: dict[str, str] | None = None,
        stats: dict[str, Any] | None = None,
    ) -> Path | None:
        """
        Save manifest data to the consolidated debug log.

        Args:
            correlation_id: Unique identifier for grouping files
            metadata: Metadata about the session
            files: Dictionary of file paths and descriptions
            stats: Statistics about the session

        Returns:
            Path to consolidated debug log file, or None if debug saving is disabled
        """
        if not self.is_enabled():
            return None

        try:
            manifest = {
                "correlation_id": correlation_id,
                "created_at": datetime.now().isoformat(),
                "metadata": metadata,
                "files": files or {},
                "stats": stats or {},
            }

            # Format manifest for the consolidated log
            manifest_content = f"""Manifest Summary:
Correlation ID: {correlation_id}
Created: {manifest['created_at']}

Metadata:
{json.dumps(metadata, indent=2)}

Files:
{json.dumps(files or {}, indent=2)}

Statistics:
{json.dumps(stats or {}, indent=2)}"""

            # Append to consolidated debug log
            self._append_to_debug_log(
                correlation_id=correlation_id,
                entry_type="manifest",
                content=manifest_content,
                metadata=manifest,
            )

            # Return path to the consolidated debug log
            correlation_dir = self._ensure_correlation_dir(correlation_id)
            return correlation_dir / "debug_log.json"

        except Exception as exc:
            self._logger.error(
                "debug.manifest_save_failed",
                correlation_id=correlation_id,
                error=str(exc),
            )
            return None

    def _ensure_correlation_dir(self, correlation_id: str) -> Path:
        """Ensure the correlation directory exists with hierarchical structure."""
        self.base_dir.mkdir(exist_ok=True)

        # Create hierarchical directory structure based on correlation_id
        # Format: debug/YYYY/MM/DD/correlation_id/
        now = datetime.now()
        year_dir = self.base_dir / str(now.year)
        month_dir = year_dir / f"{now.month:02d}"
        day_dir = month_dir / f"{now.day:02d}"
        correlation_dir = day_dir / correlation_id

        # Create all directories in the hierarchy
        correlation_dir.mkdir(parents=True, exist_ok=True)
        return correlation_dir

    def find_correlation_dir(self, correlation_id: str) -> Path | None:
        """
        Find a correlation directory in the hierarchical structure.

        Args:
            correlation_id: The correlation ID to find

        Returns:
            Path to the correlation directory if found, None otherwise
        """
        # Search through the hierarchical structure
        for year_dir in self.base_dir.iterdir():
            if not year_dir.is_dir():
                continue
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue
                for day_dir in month_dir.iterdir():
                    if not day_dir.is_dir():
                        continue
                    correlation_dir = day_dir / correlation_id
                    if correlation_dir.exists():
                        return correlation_dir
        return None

    def list_correlation_ids(self, date_filter: str | None = None) -> list[str]:
        """
        List all correlation IDs in the hierarchical structure.

        Args:
            date_filter: Optional date filter in YYYY-MM-DD format

        Returns:
            List of correlation IDs found
        """
        correlation_ids = []

        if date_filter:
            try:
                filter_date = datetime.strptime(date_filter, "%Y-%m-%d")
                year_dir = self.base_dir / str(filter_date.year)
                month_dir = year_dir / f"{filter_date.month:02d}"
                day_dir = month_dir / f"{filter_date.day:02d}"

                if day_dir.exists():
                    for item in day_dir.iterdir():
                        if item.is_dir():
                            correlation_ids.append(item.name)
            except ValueError:
                # Invalid date format, search all directories
                pass

        if not correlation_ids:
            # Search all directories if no filter or filter failed
            for year_dir in self.base_dir.iterdir():
                if not year_dir.is_dir():
                    continue
                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir():
                        continue
                    for day_dir in month_dir.iterdir():
                        if not day_dir.is_dir():
                            continue
                        for item in day_dir.iterdir():
                            if item.is_dir():
                                correlation_ids.append(item.name)

        return sorted(correlation_ids)

    def _convert_raw_to_wav(self, audio_data: bytes, sample_rate: int = 48000) -> bytes:
        """
        Convert raw PCM audio data to WAV format.

        This is a simplified version - in production you might want to use
        a proper audio library like pydub or librosa.
        """
        # Use provided sample rate, default to 48kHz
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

        return (
            riff_chunk
            + fmt_chunk
            + struct.pack("<4sI", data_id, data_size)
            + audio_data
        )


# Convenience functions for easy usage
def get_debug_manager(service_name: str = "common") -> DebugFileManager:
    """Get a debug manager instance for a specific service."""
    return DebugFileManager(enabled_env_var=f"{service_name.upper()}_DEBUG_SAVE")


def save_debug_text(
    correlation_id: str,
    content: str,
    service_name: str = "common",
    filename_prefix: str = "debug",
    metadata: dict[str, Any] | None = None,
) -> Path | None:
    """Convenience function to save debug text."""
    manager = get_debug_manager(service_name)
    return manager.save_text_file(correlation_id, content, filename_prefix, metadata)


def save_debug_audio(
    correlation_id: str,
    audio_data: bytes,
    service_name: str = "common",
    filename_prefix: str = "audio",
    convert_to_wav: bool = True,
) -> Path | None:
    """Convenience function to save debug audio."""
    manager = get_debug_manager(service_name)
    return manager.save_audio_file(
        correlation_id, audio_data, filename_prefix, convert_to_wav
    )


def save_debug_json(
    correlation_id: str,
    data: dict[str, Any],
    service_name: str = "common",
    filename_prefix: str = "data",
) -> Path | None:
    """Convenience function to save debug JSON."""
    manager = get_debug_manager(service_name)
    return manager.save_json_file(correlation_id, data, filename_prefix)


def save_debug_manifest(
    correlation_id: str,
    metadata: dict[str, Any],
    service_name: str = "common",
    files: dict[str, str] | None = None,
    stats: dict[str, Any] | None = None,
) -> Path | None:
    """Convenience function to save debug manifest."""
    manager = get_debug_manager(service_name)
    return manager.save_manifest(correlation_id, metadata, files, stats)
