"""Test phrase recorder module for the orchestrator service."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import ffmpeg
from pydub import AudioSegment

from services.common.logging import get_logger

logger = get_logger(__name__, service_name="orchestrator")


class RecorderManager:
    """Manages test phrase recordings and conversions."""

    def __init__(
        self,
        recordings_dir: str = "/app/recordings",
        max_file_size: int = 10 * 1024 * 1024,
    ):
        """
        Initialize the test recorder manager.

        Args:
            recordings_dir: Directory to store recordings
            max_file_size: Maximum file size in bytes (default: 10MB)
        """
        self.recordings_dir = Path(recordings_dir)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = max_file_size
        self.recordings: dict[str, dict[str, Any]] = {}

        # Load existing recordings
        self._load_recordings()

    def _load_recordings(self) -> None:
        """Load existing recordings from the recordings directory."""
        metadata_file = self.recordings_dir / "recordings_metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file) as f:
                    self.recordings = json.load(f)
                logger.info(
                    "test_recorder.loaded_existing_recordings",
                    count=len(self.recordings),
                )
            except Exception as e:
                logger.error("test_recorder.failed_to_load_metadata", error=str(e))
                self.recordings = {}

    def _save_recordings(self) -> None:
        """Save recordings metadata to disk."""
        metadata_file = self.recordings_dir / "recordings_metadata.json"
        try:
            with open(metadata_file, "w") as f:
                json.dump(self.recordings, f, indent=2)
        except Exception as e:
            logger.error("test_recorder.failed_to_save_metadata", error=str(e))

    def add_phrase(self, text: str, category: str) -> dict[str, Any]:
        """
        Add a new test phrase.

        Args:
            text: The phrase text
            category: Category of the phrase (wake, core, edge, noise)

        Returns:
            Dictionary with phrase information
        """
        phrase_id = str(uuid.uuid4())
        phrase = {
            "id": phrase_id,
            "text": text,
            "category": category,
            "timestamp": datetime.utcnow().isoformat(),
            "audio_file": None,
            "audio_size": 0,
            "audio_duration": 0.0,
        }

        self.recordings[phrase_id] = phrase
        self._save_recordings()

        logger.info(
            "test_recorder.phrase_added",
            phrase_id=phrase_id,
            text=text,
            category=category,
        )
        return phrase

    def save_audio(
        self, phrase_id: str, audio_data: bytes, audio_format: str = "webm"
    ) -> dict[str, Any]:
        """
        Save audio data for a phrase.

        Args:
            phrase_id: ID of the phrase
            audio_data: Raw audio data
            audio_format: Audio format (webm, wav, etc.)

        Returns:
            Dictionary with save result
        """
        if phrase_id not in self.recordings:
            raise ValueError(f"Phrase {phrase_id} not found")

        if len(audio_data) > self.max_file_size:
            raise ValueError(
                f"Audio file too large: {len(audio_data)} bytes (max: {self.max_file_size})"
            )

        # Create filename
        safe_text = "".join(
            c
            for c in self.recordings[phrase_id]["text"]
            if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        safe_text = safe_text.replace(" ", "_")[:30]
        filename = f"{self.recordings[phrase_id]['category']}_{phrase_id}_{safe_text}.{audio_format}"
        audio_file_path = self.recordings_dir / filename

        # Save audio file
        with open(audio_file_path, "wb") as f:
            f.write(audio_data)

        # Get audio duration
        duration = 0.0
        try:
            if audio_format == "webm":
                # Use ffmpeg to get duration
                probe = ffmpeg.probe(str(audio_file_path))
                duration = float(probe["streams"][0]["duration"])
            elif audio_format == "wav":
                # Use pydub for WAV files
                audio = AudioSegment.from_wav(str(audio_file_path))
                duration = len(audio) / 1000.0  # Convert to seconds
        except Exception as e:
            logger.warning("test_recorder.failed_to_get_duration", error=str(e))

        # Update phrase record
        self.recordings[phrase_id].update(
            {
                "audio_file": str(audio_file_path),
                "audio_size": len(audio_data),
                "audio_duration": duration,
                "audio_format": audio_format,
            }
        )

        self._save_recordings()

        logger.info(
            "test_recorder.audio_saved",
            phrase_id=phrase_id,
            filename=filename,
            size=len(audio_data),
            duration=duration,
        )

        return {
            "phrase_id": phrase_id,
            "filename": filename,
            "size": len(audio_data),
            "duration": duration,
        }

    def convert_to_wav(
        self, phrase_id: str, sample_rate: int = 48000
    ) -> dict[str, Any]:
        """
        Convert phrase audio to WAV format.

        Args:
            phrase_id: ID of the phrase
            sample_rate: Target sample rate

        Returns:
            Dictionary with conversion result
        """
        if phrase_id not in self.recordings:
            raise ValueError(f"Phrase {phrase_id} not found")

        phrase = self.recordings[phrase_id]
        if not phrase.get("audio_file"):
            raise ValueError(f"No audio file for phrase {phrase_id}")

        input_file = Path(phrase["audio_file"])
        if not input_file.exists():
            raise ValueError(f"Audio file not found: {input_file}")

        # Create output filename
        output_filename = input_file.stem + "_converted.wav"
        output_file = self.recordings_dir / output_filename

        try:
            # Convert using ffmpeg
            (
                ffmpeg.input(str(input_file))
                .output(
                    str(output_file),
                    acodec="pcm_s16le",  # 16-bit PCM
                    ac=1,  # Mono channel
                    ar=sample_rate,  # Sample rate
                    af="aresample=resampler=soxr",  # High-quality resampling
                )
                .overwrite_output()
                .run(quiet=True)
            )

            # Get converted file info
            converted_size = output_file.stat().st_size

            # Update phrase record
            phrase["converted_file"] = str(output_file)
            phrase["converted_size"] = converted_size
            phrase["converted_sample_rate"] = sample_rate

            self._save_recordings()

            logger.info(
                "test_recorder.audio_converted",
                phrase_id=phrase_id,
                output_file=output_filename,
                sample_rate=sample_rate,
                size=converted_size,
            )

            return {
                "phrase_id": phrase_id,
                "output_file": str(output_file),
                "filename": output_filename,
                "sample_rate": sample_rate,
                "size": converted_size,
            }

        except ffmpeg.Error as e:
            logger.error(
                "test_recorder.conversion_failed", phrase_id=phrase_id, error=str(e)
            )
            raise ValueError(f"Audio conversion failed: {e}")
        except Exception as e:
            logger.error(
                "test_recorder.conversion_error", phrase_id=phrase_id, error=str(e)
            )
            raise ValueError(f"Audio conversion error: {e}")

    def get_phrase(self, phrase_id: str) -> dict[str, Any] | None:
        """Get a specific phrase by ID."""
        return self.recordings.get(phrase_id)

    def list_phrases(self, category: str | None = None) -> list[dict[str, Any]]:
        """
        List all phrases, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of phrase dictionaries
        """
        phrases = list(self.recordings.values())
        if category:
            phrases = [p for p in phrases if p.get("category") == category]
        return phrases

    def delete_phrase(self, phrase_id: str) -> bool:
        """
        Delete a phrase and its associated audio files.

        Args:
            phrase_id: ID of the phrase to delete

        Returns:
            True if deleted successfully
        """
        if phrase_id not in self.recordings:
            return False

        phrase = self.recordings[phrase_id]

        # Delete audio files
        for file_key in ["audio_file", "converted_file"]:
            if phrase.get(file_key):
                file_path = Path(phrase[file_key])
                if file_path.exists():
                    try:
                        file_path.unlink()
                        logger.info("test_recorder.file_deleted", file=str(file_path))
                    except Exception as e:
                        logger.warning(
                            "test_recorder.failed_to_delete_file",
                            file=str(file_path),
                            error=str(e),
                        )

        # Remove from recordings
        del self.recordings[phrase_id]
        self._save_recordings()

        logger.info("test_recorder.phrase_deleted", phrase_id=phrase_id)
        return True

    def get_audio_file(self, phrase_id: str, converted: bool = False) -> Path | None:
        """
        Get the path to an audio file for a phrase.

        Args:
            phrase_id: ID of the phrase
            converted: Whether to get the converted WAV file

        Returns:
            Path to the audio file, or None if not found
        """
        if phrase_id not in self.recordings:
            return None

        phrase = self.recordings[phrase_id]
        file_key = "converted_file" if converted else "audio_file"
        file_path = phrase.get(file_key)

        if file_path and Path(file_path).exists():
            return Path(file_path)

        return None

    def export_metadata(self) -> dict[str, Any]:
        """Export all recordings metadata."""
        return {
            "export_date": datetime.utcnow().isoformat(),
            "total_phrases": len(self.recordings),
            "categories": list(
                {p.get("category", "unknown") for p in self.recordings.values()}
            ),
            "recordings_dir": str(self.recordings_dir),
            "phrases": list(self.recordings.values()),
        }

    def clear_all(self) -> int:
        """
        Clear all recordings and delete associated files.

        Returns:
            Number of phrases cleared
        """
        count = len(self.recordings)

        # Delete all audio files
        for phrase in self.recordings.values():
            for file_key in ["audio_file", "converted_file"]:
                if phrase.get(file_key):
                    file_path = Path(phrase[file_key])
                    if file_path.exists():
                        try:
                            file_path.unlink()
                        except Exception as e:
                            logger.warning(
                                "test_recorder.failed_to_delete_file",
                                file=str(file_path),
                                error=str(e),
                            )

        # Clear recordings
        self.recordings.clear()
        self._save_recordings()

        logger.info("test_recorder.all_cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the recordings."""
        total_size = sum(p.get("audio_size", 0) for p in self.recordings.values())
        total_duration = sum(
            p.get("audio_duration", 0) for p in self.recordings.values()
        )

        categories: dict[str, int] = {}
        for phrase in self.recordings.values():
            cat = phrase.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_phrases": len(self.recordings),
            "total_size_bytes": total_size,
            "total_duration_seconds": total_duration,
            "categories": categories,
            "recordings_dir": str(self.recordings_dir),
        }
