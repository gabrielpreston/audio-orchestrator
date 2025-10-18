"""Generate synthetic audio samples for testing (without numpy dependency)."""

import math
import struct
from pathlib import Path
from typing import cast


def generate_sine_wave(
    duration: float, sample_rate: int, frequency: float, amplitude: float
) -> bytes:
    """Generate a sine wave as PCM data."""
    samples = int(duration * sample_rate)
    audio_data = []

    for i in range(samples):
        t = i / sample_rate
        sample = amplitude * math.sin(2 * math.pi * frequency * t)
        # Convert to 16-bit PCM
        pcm_sample = int(sample * 32767)
        # Clamp to 16-bit range
        pcm_sample = max(-32768, min(32767, pcm_sample))
        audio_data.append(pcm_sample)

    return struct.pack("<" + "h" * len(audio_data), *audio_data)


def create_wav_file(
    pcm_data: bytes, sample_rate: int = 16000, channels: int = 1
) -> bytes:
    """Create WAV file from PCM data."""
    # WAV header
    data_size = len(pcm_data)
    file_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",  # ChunkID
        file_size,  # ChunkSize
        b"WAVE",  # Format
        b"fmt ",  # Subchunk1ID
        16,  # Subchunk1Size (PCM)
        1,  # AudioFormat (PCM)
        channels,  # NumChannels
        sample_rate,  # SampleRate
        sample_rate * channels * 2,  # ByteRate
        channels * 2,  # BlockAlign
        16,  # BitsPerSample
        b"data",  # Subchunk2ID
        data_size,  # Subchunk2Size
    )

    return header + pcm_data


def generate_audio_samples():
    """Generate various audio samples for testing."""

    # Create fixtures directory
    fixtures_dir = Path(__file__).parent
    fixtures_dir.mkdir(exist_ok=True)

    # Sample configurations
    samples = [
        {
            "name": "sine_440hz_1s",
            "duration": 1.0,
            "frequency": 440.0,
            "amplitude": 0.5,
        },
        {
            "name": "sine_1000hz_2s",
            "duration": 2.0,
            "frequency": 1000.0,
            "amplitude": 0.3,
        },
        {
            "name": "voice_range_300hz",
            "duration": 1.5,
            "frequency": 300.0,
            "amplitude": 0.4,
        },
        {
            "name": "voice_range_3400hz",
            "duration": 1.5,
            "frequency": 3400.0,
            "amplitude": 0.4,
        },
        {"name": "silence", "duration": 1.0, "frequency": 0.0, "amplitude": 0.0},
        {
            "name": "low_amplitude",
            "duration": 1.0,
            "frequency": 440.0,
            "amplitude": 0.01,
        },
        {
            "name": "high_amplitude",
            "duration": 1.0,
            "frequency": 440.0,
            "amplitude": 0.9,
        },
    ]

    # Generate samples
    for sample in samples:
        print(f"Generating {sample['name']}...")

        # Generate PCM data
        pcm_data = generate_sine_wave(
            duration=cast(float, sample["duration"]),
            sample_rate=16000,
            frequency=cast(float, sample["frequency"]),
            amplitude=cast(float, sample["amplitude"]),
        )

        # Create WAV file
        wav_data = create_wav_file(pcm_data, sample_rate=16000, channels=1)

        # Save to file
        output_path = fixtures_dir / f"{sample['name']}.wav"
        with open(output_path, "wb") as f:
            f.write(wav_data)

        print(f"  Saved to {output_path}")

    print(f"\nGenerated {len(samples)} audio samples in {fixtures_dir}")


if __name__ == "__main__":
    generate_audio_samples()
