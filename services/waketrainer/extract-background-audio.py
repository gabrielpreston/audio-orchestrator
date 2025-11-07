#!/usr/bin/env python3
"""Extract background audio from HuggingFace dataset to WAV files for torch_audiomentations."""

import argparse
import os
import sys
from pathlib import Path

try:
    from datasets import load_dataset
except ImportError:
    print(
        "Error: datasets library not available. Install with: pip install datasets",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    import soundfile as sf
    import numpy as np
except ImportError:
    print(
        "Error: soundfile or numpy not available. These should be in the container.",
        file=sys.stderr,
    )
    sys.exit(1)


def extract_background_audio(
    dataset_dir: str | Path,
    output_dir: str | Path,
    repo_id: str = "Myrtle/CAIMAN-ASR-BackgroundNoise",
    sample_rate: int = 16000,
) -> int:
    """Extract background audio from HuggingFace dataset to WAV files.

    Args:
        dataset_dir: Directory where dataset was downloaded
        output_dir: Directory to write WAV files
        repo_id: HuggingFace repository ID
        sample_rate: Target sample rate for WAV files (default: 16000)

    Returns:
        0 on success, 1 on error
    """
    dataset_path = Path(dataset_dir)
    output_path = Path(output_dir)

    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)

    # Set cache directory to writable location in workspace
    # Override HF_HOME (set by base Dockerfile to /app/models which isn't writable)
    # This matches the pattern used in training_data_utils.py
    cache_dir = "/workspace/.cache/huggingface"
    datasets_cache = Path(cache_dir) / "datasets"
    datasets_cache.mkdir(parents=True, exist_ok=True)

    # Override both environment variables to ensure writable cache
    os.environ["HF_HOME"] = cache_dir
    os.environ["HF_DATASETS_CACHE"] = str(datasets_cache)

    print(f"Loading dataset from: {dataset_path}")
    print(f"Output directory: {output_path}")
    print(f"Target sample rate: {sample_rate} Hz")
    print(f"Cache directory: {datasets_cache}")

    try:
        # Load dataset - try local directory first, then fall back to repo
        # HuggingFace datasets can be in various formats (Parquet, Arrow, etc.)
        if dataset_path.exists() and any(dataset_path.iterdir()):
            print("Loading dataset from local directory...")
            try:
                # Try loading as Parquet dataset from local directory
                dataset = load_dataset(
                    "parquet",
                    data_dir=str(dataset_path),
                    split="train",
                    cache_dir=str(datasets_cache),
                    trust_remote_code=True,
                )
            except Exception as local_error:
                print(
                    f"Could not load from local directory as Parquet: {local_error}",
                    file=sys.stderr,
                )
                print(f"Trying to load directly from {repo_id}...")
                dataset = load_dataset(
                    repo_id,
                    split="train",
                    cache_dir=str(datasets_cache),
                    trust_remote_code=True,
                )
        else:
            print(f"Local directory not found or empty, loading from {repo_id}...")
            dataset = load_dataset(
                repo_id,
                split="train",
                cache_dir=str(datasets_cache),
                trust_remote_code=True,
            )

        total_items = len(dataset)
        print(f"\nFound {total_items} audio items in dataset")
        print("Extracting audio to WAV files...")

        success_count = 0
        error_count = 0

        for idx, item in enumerate(dataset):
            try:
                # Extract audio data from item
                # Dataset items typically have an "audio" column
                if "audio" in item:
                    audio_data = item["audio"]
                    if isinstance(audio_data, dict):
                        # Audio dict with "array" and "sampling_rate"
                        audio_array = np.array(audio_data["array"], dtype=np.float32)
                        item_sample_rate = audio_data.get("sampling_rate", sample_rate)
                    else:
                        # Audio is already an array
                        audio_array = np.array(audio_data, dtype=np.float32)
                        item_sample_rate = sample_rate
                elif "array" in item:
                    # Direct array in item
                    audio_array = np.array(item["array"], dtype=np.float32)
                    item_sample_rate = item.get("sampling_rate", sample_rate)
                else:
                    # Try to find audio-like data in item
                    print(
                        f"Warning: Item {idx} doesn't have expected audio format, skipping",
                        file=sys.stderr,
                    )
                    error_count += 1
                    continue

                # Resample if needed (simple linear interpolation for now)
                if item_sample_rate != sample_rate:
                    # Calculate resampling ratio
                    ratio = sample_rate / item_sample_rate
                    new_length = int(len(audio_array) * ratio)
                    # Simple linear interpolation
                    indices = np.linspace(0, len(audio_array) - 1, new_length)
                    audio_array = np.interp(
                        indices, np.arange(len(audio_array)), audio_array
                    )

                # Normalize audio to [-1.0, 1.0] range if needed
                if audio_array.max() > 1.0 or audio_array.min() < -1.0:
                    audio_array = audio_array / np.max(np.abs(audio_array))

                # Generate filename (use index or item ID if available)
                if "id" in item:
                    filename = f"{item['id']}.wav"
                elif "file" in item:
                    # Extract filename from path if available
                    filepath = Path(item["file"])
                    filename = f"{filepath.stem}.wav"
                else:
                    filename = f"audio_{idx:06d}.wav"

                output_file = output_path / filename

                # Write WAV file
                sf.write(str(output_file), audio_array, sample_rate)

                success_count += 1

                # Progress reporting every 100 items
                if (idx + 1) % 100 == 0 or (idx + 1) == total_items:
                    print(
                        f"Progress: {idx + 1}/{total_items} ({100 * (idx + 1) / total_items:.1f}%) - "
                        f"Success: {success_count}, Errors: {error_count}"
                    )

            except Exception as e:
                error_count += 1
                print(
                    f"Error processing item {idx}: {e}",
                    file=sys.stderr,
                )
                # Continue processing other items
                continue

        print("\nExtraction complete!")
        print(f"  Successfully extracted: {success_count} files")
        print(f"  Errors: {error_count} files")
        print(f"  Output directory: {output_path}")

        if success_count == 0:
            print(
                "Warning: No files were successfully extracted!",
                file=sys.stderr,
            )
            return 1

        return 0

    except Exception as e:
        print(f"\nError loading dataset: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract background audio from HuggingFace dataset to WAV files"
    )
    parser.add_argument(
        "--dataset-dir",
        type=str,
        default="/workspace/services/models/wake/training-data/background_clips",
        help="Directory where dataset was downloaded",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="/workspace/services/models/wake/training-data/background_clips/wav",
        help="Directory to write WAV files",
    )
    parser.add_argument(
        "--repo-id",
        type=str,
        default="Myrtle/CAIMAN-ASR-BackgroundNoise",
        help="HuggingFace repository ID (used if dataset-dir not found)",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="Target sample rate for WAV files (default: 16000)",
    )

    args = parser.parse_args()

    return extract_background_audio(
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        repo_id=args.repo_id,
        sample_rate=args.sample_rate,
    )


if __name__ == "__main__":
    sys.exit(main())
