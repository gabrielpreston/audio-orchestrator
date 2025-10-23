"""Create test dataset for voice pipeline validation."""
import json
from pathlib import Path


def create_test_dataset():
    """Create structured test dataset with ground truth.

    Structure:
    - tests/fixtures/voice_pipeline/
      - clean/  (50 samples)
        - sample_001.wav
        - sample_001.txt (ground truth transcript)
      - noisy/ (50 samples)
        - sample_001.wav
        - sample_001.txt (ground truth transcript)
      - wake_phrases/ (20 samples)
        - positive/ (true wake phrases)
        - negative/ (false positives to test)
      - metadata.json (sample metadata)
    """
    base_path = Path("tests/fixtures/voice_pipeline")
    base_path.mkdir(parents=True, exist_ok=True)

    # Create directories
    for subdir in ["clean", "noisy", "wake_phrases/positive", "wake_phrases/negative"]:
        (base_path / subdir).mkdir(parents=True, exist_ok=True)

    # Create metadata
    metadata = {
        "dataset_version": "1.0",
        "total_samples": 100,
        "clean_samples": 50,
        "noisy_samples": 50,
        "wake_phrase_samples": 20,
        "sample_rate": 16000,
        "format": "wav",
        "ground_truth_format": "text",
        "created": "2025-10-22"
    }

    with open(base_path / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"✓ Test dataset structure created at {base_path}")
    print("→ Next: Add real audio samples and ground truth transcripts")

if __name__ == "__main__":
    create_test_dataset()
