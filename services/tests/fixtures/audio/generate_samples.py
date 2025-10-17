"""Generate synthetic audio samples for testing."""

import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from services.tests.utils.audio_quality_helpers import (  # noqa: E402
    create_wav_file,
    generate_test_audio,
)


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
            "noise_level": 0.0,
        },
        {
            "name": "sine_1000hz_2s",
            "duration": 2.0,
            "frequency": 1000.0,
            "amplitude": 0.3,
            "noise_level": 0.0,
        },
        {
            "name": "sine_440hz_noisy",
            "duration": 1.0,
            "frequency": 440.0,
            "amplitude": 0.5,
            "noise_level": 0.1,
        },
        {
            "name": "voice_range_300hz",
            "duration": 1.5,
            "frequency": 300.0,
            "amplitude": 0.4,
            "noise_level": 0.05,
        },
        {
            "name": "voice_range_3400hz",
            "duration": 1.5,
            "frequency": 3400.0,
            "amplitude": 0.4,
            "noise_level": 0.05,
        },
        {
            "name": "silence",
            "duration": 1.0,
            "frequency": 0.0,
            "amplitude": 0.0,
            "noise_level": 0.0,
        },
        {
            "name": "low_amplitude",
            "duration": 1.0,
            "frequency": 440.0,
            "amplitude": 0.01,
            "noise_level": 0.0,
        },
        {
            "name": "high_amplitude",
            "duration": 1.0,
            "frequency": 440.0,
            "amplitude": 0.9,
            "noise_level": 0.0,
        },
    ]

    # Generate samples
    for sample in samples:
        print(f"Generating {sample['name']}...")

        # Generate PCM data
        pcm_data = generate_test_audio(
            duration=float(sample["duration"]),
            sample_rate=16000,
            frequency=float(sample["frequency"]),
            amplitude=float(sample["amplitude"]),
            noise_level=float(sample["noise_level"]),
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
