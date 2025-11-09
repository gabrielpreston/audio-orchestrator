#!/usr/bin/env python3
"""Diagnostic script to investigate CUDA OOM during openwakeword validation.

This script examines:
1. Validation data file size and shape
2. openwakeword train.py code around line 518 (OOM location)
3. Memory usage patterns
"""

from pathlib import Path
import numpy as np


def check_validation_data() -> None:
    """Check the validation data file size and shape."""
    val_path = Path(
        "/workspace/services/models/wake/training-data/validation_set_features.npy"
    )

    print("=" * 60)
    print("VALIDATION DATA FILE ANALYSIS")
    print("=" * 60)

    if not val_path.exists():
        print(f"ERROR: Validation file not found: {val_path}")
        return

    # Get file size
    file_size = val_path.stat().st_size
    file_size_mb = file_size / (1024**2)
    file_size_gb = file_size / (1024**3)

    print(f"File path: {val_path}")
    print(
        f"File size: {file_size:,} bytes ({file_size_mb:.2f} MB / {file_size_gb:.2f} GB)"
    )

    try:
        # Load and check shape (memory-mapped to avoid loading into RAM)
        data = np.load(val_path, mmap_mode="r")
        print(f"Data shape: {data.shape}")
        print(f"Data dtype: {data.dtype}")

        # Calculate memory if fully loaded
        if data.size > 0:
            element_size = data.itemsize
            total_elements = data.size
            memory_mb = (total_elements * element_size) / (1024**2)
            memory_gb = (total_elements * element_size) / (1024**3)
            print(f"Memory if fully loaded: {memory_mb:.2f} MB / {memory_gb:.2f} GB")

            # Check if shape matches expected format (n, 16, 96) or similar
            if len(data.shape) == 3:
                print(
                    f"Shape breakdown: {data.shape[0]} samples, {data.shape[1]}x{data.shape[2]} features per sample"
                )
            elif len(data.shape) == 2:
                print(
                    f"Shape breakdown: {data.shape[0]} samples, {data.shape[1]} features per sample"
                )
                print("WARNING: 2D shape detected - may need reshaping")
            else:
                print(f"WARNING: Unexpected shape dimensions: {len(data.shape)}")

    except Exception as e:
        print(f"ERROR loading validation data: {e}")
        import traceback

        traceback.print_exc()


def inspect_train_py() -> None:
    """Inspect the openwakeword train.py code around line 518."""
    print("\n" + "=" * 60)
    print("OPENWAKEWORD TRAIN.PY INSPECTION")
    print("=" * 60)

    try:
        import openwakeword

        train_py_path = Path(openwakeword.__file__).parent / "train.py"

        print(f"Train.py path: {train_py_path}")

        if not train_py_path.exists():
            print(f"ERROR: train.py not found at {train_py_path}")
            return

        # Read the file and find relevant sections
        with train_py_path.open() as f:
            lines = f.readlines()

        print(f"Total lines in train.py: {len(lines)}")

        # Show context around line 518 (where OOM occurs)
        print("\n--- Code around line 518 (OOM location) ---")
        start_line = max(0, 505)
        end_line = min(len(lines), 530)
        for i in range(start_line, end_line):
            marker = ">>> " if i == 517 else "    "
            print(f"{marker}{i+1:4d}: {lines[i].rstrip()}")

        # Search for validation data loading and reshaping
        print("\n--- Searching for validation data loading/reshaping ---")
        keywords = ["X_val_fp", "validation", "reshape", "false_positive_validation"]

        for keyword in keywords:
            matches = [
                (i + 1, line.strip())
                for i, line in enumerate(lines)
                if keyword.lower() in line.lower() and not line.strip().startswith("#")
            ]
            if matches:
                print(f"\nFound '{keyword}' at:")
                for line_num, line_content in matches[:10]:  # Show first 10 matches
                    print(f"  Line {line_num}: {line_content[:100]}")
                if len(matches) > 10:
                    print(f"  ... and {len(matches) - 10} more occurrences")

        # Look for the specific reshape line mentioned in suggestions
        print("\n--- Searching for reshape operation on validation data ---")
        reshape_found = False
        for i, line in enumerate(lines):
            if "X_val_fp" in line and ("reshape" in line.lower() or "np.array" in line):
                context_start = max(0, i - 2)
                context_end = min(len(lines), i + 3)
                print(f"\nFound potential reshape at line {i+1}:")
                for j in range(context_start, context_end):
                    marker = ">>> " if j == i else "    "
                    print(f"{marker}{j+1:4d}: {lines[j].rstrip()}")
                reshape_found = True

        if not reshape_found:
            print("No obvious reshape operation found with X_val_fp")

        # Look for where validation data is loaded
        print("\n--- Searching for validation data loading ---")
        for i, line in enumerate(lines):
            if (
                "false_positive_validation_data_path" in line
                or "validation_set_features" in line
            ):
                context_start = max(0, i - 3)
                context_end = min(len(lines), i + 5)
                print(f"\nFound validation data loading around line {i+1}:")
                for j in range(context_start, context_end):
                    marker = ">>> " if j == i else "    "
                    print(f"{marker}{j+1:4d}: {lines[j].rstrip()}")

    except Exception as e:
        print(f"ERROR inspecting train.py: {e}")
        import traceback

        traceback.print_exc()


def check_gpu_memory() -> None:
    """Check current GPU memory usage."""
    print("\n" + "=" * 60)
    print("GPU MEMORY STATUS")
    print("=" * 60)

    try:
        import torch

        if torch.cuda.is_available():
            print("CUDA available: Yes")
            print(f"CUDA device count: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                print(f"\nDevice {i}: {torch.cuda.get_device_name(i)}")
                props = torch.cuda.get_device_properties(i)
                print(f"  Total memory: {props.total_memory / (1024**3):.2f} GB")
                print(
                    f"  Allocated: {torch.cuda.memory_allocated(i) / (1024**3):.2f} GB"
                )
                print(f"  Reserved: {torch.cuda.memory_reserved(i) / (1024**3):.2f} GB")
        else:
            print("CUDA not available")
    except ImportError:
        print("PyTorch not available")
    except Exception as e:
        print(f"ERROR checking GPU memory: {e}")


def main() -> None:
    """Run all diagnostic checks."""
    print("\n" + "=" * 60)
    print("OPENWAKEWORD VALIDATION OOM DIAGNOSTIC")
    print("=" * 60)
    print()

    check_validation_data()
    inspect_train_py()
    check_gpu_memory()

    print("\n" + "=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
