"""TTS test helper functions for audio validation and baseline generation."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from services.tests.utils.audio_quality_helpers import (
    calculate_snr,
    calculate_thd,
    create_wav_file,
    generate_test_audio,
    measure_frequency_response,
    validate_wav_format,
)


def generate_tts_baseline_samples(samples_dir: Path, text_samples: list[dict[str, Any]]) -> None:
    """
    Generate baseline TTS samples with metadata.

    Args:
        samples_dir: Directory to save samples
        text_samples: List of sample configurations
    """
    samples_dir.mkdir(parents=True, exist_ok=True)

    for sample in text_samples:
        # Generate synthetic audio based on text length
        duration = len(sample["text"]) * 0.1  # 0.1s per character
        pcm_data = generate_test_audio(
            duration=duration,
            sample_rate=sample.get("sample_rate", 22050),
            frequency=sample.get("frequency", 440.0),
            amplitude=sample.get("amplitude", 0.5),
            noise_level=sample.get("noise_level", 0.0),
        )
        wav_data = create_wav_file(pcm_data, sample.get("sample_rate", 22050), channels=1)

        # Save audio file
        audio_file = samples_dir / f"{sample['name']}.wav"
        audio_file.write_bytes(wav_data)

        # Calculate quality metrics
        wav_info = validate_wav_format(wav_data)
        snr = calculate_snr(wav_data)
        thd = calculate_thd(wav_data)
        freq_response = measure_frequency_response(wav_data, sample.get("sample_rate", 22050))

        # Create metadata
        metadata = {
            "text": sample["text"],
            "sample_rate": sample.get("sample_rate", 22050),
            "duration": duration,
            "voice": sample.get("voice", "default"),
            "quality_metrics": {
                "snr_db": snr,
                "thd_percent": thd,
                "voice_range_ratio": freq_response.get("voice_range_ratio", 0.0),
            },
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "wav_info": wav_info,
        }

        # Save metadata
        metadata_file = samples_dir / f"{sample['name']}.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))


def load_tts_baseline_metadata(samples_dir: Path, sample_name: str) -> dict[str, Any]:
    """
    Load baseline sample metadata.

    Args:
        samples_dir: Directory containing samples
        sample_name: Name of the sample (without extension)

    Returns:
        Sample metadata dictionary
    """
    metadata_file = samples_dir / f"{sample_name}.json"
    if not metadata_file.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

    return json.loads(metadata_file.read_text())


def validate_tts_audio_format(audio_data: bytes) -> dict[str, Any]:
    """
    Validate TTS audio format.

    Args:
        audio_data: WAV audio data

    Returns:
        Format validation results
    """
    wav_info = validate_wav_format(audio_data)

    # TTS-specific format requirements
    tts_requirements = {
        "sample_rate_ok": wav_info.get("sample_rate", 0) == 22050,
        "channels_ok": wav_info.get("channels", 0) == 1,
        "bit_depth_ok": wav_info.get("bit_depth", 0) == 16,
        "duration_ok": wav_info.get("duration", 0) > 0.1,  # At least 0.1s
    }

    return {
        **wav_info,
        "tts_requirements": tts_requirements,
        "is_tts_compliant": all(tts_requirements.values()),
    }


def validate_tts_audio_quality(
    audio_data: bytes,
    min_snr: float = 5.0,
    max_thd: float = 5.0,
    min_voice_range: float = 0.5,
) -> dict[str, Any]:
    """
    Validate TTS audio quality metrics.

    Args:
        audio_data: WAV audio data
        min_snr: Minimum SNR in dB
        max_thd: Maximum THD percentage
        min_voice_range: Minimum voice range ratio (300-3400Hz power / total power)

    Returns:
        Quality validation results
    """
    snr = calculate_snr(audio_data)
    thd = calculate_thd(audio_data)
    freq_response = measure_frequency_response(audio_data, 22050)

    quality_checks = {
        "snr_ok": snr >= min_snr,
        "thd_ok": thd <= max_thd,
        "voice_range_ok": freq_response.get("voice_range_ratio", 0) >= min_voice_range,
    }

    return {
        "snr_db": snr,
        "thd_percent": thd,
        "frequency_response": freq_response,
        "quality_checks": quality_checks,
        "meets_quality_thresholds": all(quality_checks.values()),
    }
