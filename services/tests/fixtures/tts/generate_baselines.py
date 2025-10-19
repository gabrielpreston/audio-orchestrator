"""Generate baseline TTS samples for testing."""

import sys
from pathlib import Path


# Add the project root to the path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Import after path manipulation - this is necessary for the script to work
from services.tests.fixtures.tts.tts_test_helpers import (  # noqa: E402
    generate_tts_baseline_samples,
)


def main():
    """Generate baseline TTS samples."""
    # Create samples directory
    samples_dir = Path(__file__).parent / "samples"

    # Define baseline samples
    text_samples = [
        {
            "name": "short_phrase",
            "text": "Hello world.",
            "sample_rate": 22050,
            "frequency": 440.0,
            "amplitude": 0.5,
            "noise_level": 0.0,
            "voice": "default",
        },
        {
            "name": "medium_phrase",
            "text": "This is a longer test phrase for TTS validation.",
            "sample_rate": 22050,
            "frequency": 440.0,
            "amplitude": 0.5,
            "noise_level": 0.0,
            "voice": "default",
        },
        {
            "name": "ssml_sample",
            "text": "<speak>This is SSML text with <break time='0.5s'/> a pause.</speak>",
            "sample_rate": 22050,
            "frequency": 440.0,
            "amplitude": 0.5,
            "noise_level": 0.0,
            "voice": "default",
        },
        {
            "name": "silence",
            "text": "",
            "sample_rate": 22050,
            "frequency": 0.0,
            "amplitude": 0.0,
            "noise_level": 0.0,
            "voice": "default",
        },
        {
            "name": "low_amplitude",
            "text": "Quiet test.",
            "sample_rate": 22050,
            "frequency": 440.0,
            "amplitude": 0.1,
            "noise_level": 0.0,
            "voice": "default",
        },
        {
            "name": "high_amplitude",
            "text": "Loud test!",
            "sample_rate": 22050,
            "frequency": 440.0,
            "amplitude": 0.8,
            "noise_level": 0.0,
            "voice": "default",
        },
    ]

    # Generate samples
    generate_tts_baseline_samples(samples_dir, text_samples)
    print(f"Generated {len(text_samples)} baseline TTS samples in {samples_dir}")


if __name__ == "__main__":
    main()
