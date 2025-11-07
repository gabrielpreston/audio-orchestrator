#!/usr/bin/env python3
"""Download wake word training data from Hugging Face Hub."""

import argparse
import sys
from pathlib import Path

# Add common to path (works in both local and container environments)
common_path = Path(__file__).parent.parent / "common"
if common_path.exists():
    sys.path.insert(0, str(common_path))
    from training_data_utils import download_all_training_data
else:
    # Try importing from services.common (container environment)
    try:
        from services.common.training_data_utils import download_all_training_data
    except ImportError:
        print("Error: Could not find training_data_utils module", file=sys.stderr)
        sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download wake word training data from Hugging Face Hub"
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default="./services/models/wake/training-data",
        help="Base directory for training data",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if files exist",
    )

    args = parser.parse_args()

    print("Downloading wake word training data from Hugging Face Hub...")
    print(f"Target directory: {args.base_dir}")

    try:
        results = download_all_training_data(
            base_dir=args.base_dir,
            force=args.force,
        )

        print("\nDownload complete!")
        print("\nDownloaded files:")
        for data_type, path in results.items():
            print(f"  {data_type}: {path}")

        return 0
    except Exception as e:
        print(f"\nError downloading training data: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
