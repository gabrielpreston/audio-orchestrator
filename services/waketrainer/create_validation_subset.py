#!/usr/bin/env python3
"""Create a smaller subset of the validation features file for testing.

This script creates a subset of the full validation dataset to avoid OOM errors
while still providing some false-positive validation during training.
"""

import argparse
import sys
from pathlib import Path
import numpy as np


def create_subset(
    input_path: Path,
    output_path: Path,
    size: int,
    use_memmap: bool = True,
) -> None:
    """Create a subset of the validation features file.

    Args:
        input_path: Path to the original validation_set_features.npy file
        output_path: Path to save the subset
        size: Number of samples to include in the subset
        use_memmap: Use memory-mapped loading to avoid loading entire file
    """
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading original validation data from {input_path}...")
    if use_memmap:
        original_data = np.load(input_path, mmap_mode="r")
    else:
        original_data = np.load(input_path)

    print(f"Original data shape: {original_data.shape}")
    print(f"Original data size: {original_data.nbytes / (1024**2):.2f} MB")

    if size > original_data.shape[0]:
        print(
            f"Warning: Requested size ({size}) is larger than available samples "
            f"({original_data.shape[0]}). Using all available samples."
        )
        subset = original_data[:]
    else:
        print(f"Creating subset of size {size}...")
        # Take first N samples (they should be representative)
        subset = original_data[:size]

    print(f"Subset shape: {subset.shape}")
    print(f"Subset size: {subset.nbytes / (1024**2):.2f} MB")

    # Calculate memory after reshape (for reference)
    window_size = 16  # Typical input_shape[0] for openwakeword
    n_windows = subset.shape[0] - window_size + 1
    if n_windows > 0:
        memory_after_reshape_gb = (n_windows * window_size * subset.shape[1] * 4) / (
            1024**3
        )
        print(
            f"Estimated memory after reshape (window_size={window_size}): {memory_after_reshape_gb:.2f} GB"
        )

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Saving subset to {output_path}...")
    np.save(output_path, subset)
    print(f"Subset created successfully: {output_path}")
    print(f"File size: {output_path.stat().st_size / (1024**2):.2f} MB")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a smaller subset of validation features for testing"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "/workspace/services/models/wake/training-data/validation_set_features.npy"
        ),
        help="Path to the original validation_set_features.npy file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "/workspace/services/models/wake/training-data/validation_set_features_small.npy"
        ),
        help="Path to save the subset",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=10000,
        help="Number of samples for the subset (default: 10000)",
    )
    parser.add_argument(
        "--no-memmap",
        action="store_true",
        help="Disable memory-mapped loading (loads entire file into memory)",
    )

    args = parser.parse_args()

    try:
        create_subset(
            args.input,
            args.output,
            args.size,
            use_memmap=not args.no_memmap,
        )
        return 0
    except Exception as e:
        print(f"Error creating subset: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
