"""Training data download utilities for wake word training.

Downloads training datasets from Hugging Face Hub to local directories.
"""

from __future__ import annotations

from pathlib import Path


try:
    from huggingface_hub import snapshot_download
except ImportError as e:
    raise ImportError(
        "huggingface_hub library not available. Install with: pip install huggingface_hub"
    ) from e

try:
    from datasets import load_dataset
    import numpy as np
except ImportError as e:
    raise ImportError(
        "datasets library not available. Install with: pip install datasets"
    ) from e


def download_mit_rirs(
    target_dir: str | Path,
    repo_id: str = "davidscripka/MIT_environmental_impulse_responses",
    force: bool = False,
) -> Path:
    """Download MIT Room Impulse Responses dataset.

    Args:
        target_dir: Directory to download RIRs to
        repo_id: HuggingFace repository ID (default: "davidscripka/MIT_environmental_impulse_responses")
        force: If True, re-download even if files exist

    Returns:
        Path to downloaded directory
    """
    import os

    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)

    # Set cache directory to writable location if not already set
    cache_dir = os.environ.get("HF_HOME", "/workspace/.cache/huggingface")
    cache_path = Path(cache_dir) / "hub"
    cache_path.mkdir(parents=True, exist_ok=True)

    # Download entire repository snapshot
    snapshot_download(
        repo_id=repo_id,
        repo_type="dataset",
        local_dir=str(target_path),
        cache_dir=str(cache_path),
        force_download=force,
    )

    return target_path


def download_background_audio(
    target_dir: str | Path,
    repo_id: str = "Myrtle/CAIMAN-ASR-BackgroundNoise",
    force: bool = False,
) -> Path:
    """Download background audio clips for augmentation.

    Args:
        target_dir: Directory to download clips to
        repo_id: HuggingFace repository ID
        force: If True, re-download even if files exist

    Returns:
        Path to downloaded directory
    """
    import os

    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)

    # Set cache directory to writable location if not already set
    cache_dir = os.environ.get("HF_HOME", "/workspace/.cache/huggingface")
    cache_path = Path(cache_dir) / "hub"
    cache_path.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id=repo_id,
        repo_type="dataset",
        local_dir=str(target_path),
        cache_dir=str(cache_path),
        force_download=force,
    )

    return target_path


def download_validation_features(
    target_file: str | Path,
    repo_id: str = "davidscripka/openwakeword_features",
    split_name: str = "False-Positive Validation Set",
    force: bool = False,
) -> Path:
    """Download pre-computed validation features.

    Args:
        target_file: Full path to save the .npy file
        repo_id: HuggingFace dataset repository ID
        split_name: Name of the dataset split (default: "False-Positive Validation Set")
        force: If True, re-download even if file exists

    Returns:
        Path to downloaded file
    """
    import os
    import shutil

    target_path = Path(target_file)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Skip if file exists and not forcing
    if target_path.exists() and not force:
        return target_path

    # Set cache directory to writable location if not already set
    cache_dir = os.environ.get("HF_HOME", "/workspace/.cache/huggingface")
    cache_path = Path(cache_dir) / "hub"
    cache_path.mkdir(parents=True, exist_ok=True)

    # Try using snapshot_download to get all files, then look for the validation features
    temp_dir = target_path.parent / f".temp_{target_path.stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Download entire repository snapshot
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            local_dir=str(temp_dir),
            cache_dir=str(cache_path),
            force_download=force,
        )

        # Look for validation features file in the downloaded directory
        # The file might be named differently or in a subdirectory
        validation_files = list(temp_dir.rglob("*validation*.npy"))
        validation_files.extend(list(temp_dir.rglob("*False-Positive*.npy")))
        validation_files.extend(list(temp_dir.rglob("*.npy")))

        if validation_files:
            # Use the first .npy file found (or the most specific one)
            # Prefer files with "validation" or "False-Positive" in the name
            preferred = [
                f
                for f in validation_files
                if "validation" in f.name.lower() or "false" in f.name.lower()
            ]
            source_file = preferred[0] if preferred else validation_files[0]
            # Copy to target location
            shutil.copy2(source_file, target_path)
            # Validate file was created successfully
            if not target_path.exists():
                raise FileNotFoundError(
                    f"Failed to copy {source_file} to {target_path}"
                )
            if target_path.stat().st_size == 0:
                raise ValueError(f"Copied file {target_path} is empty")
        else:
            # Try loading as dataset if files aren't found directly
            dataset_cache = Path(cache_dir) / "datasets"
            dataset_cache.mkdir(parents=True, exist_ok=True)
            dataset = load_dataset(
                repo_id,
                split=split_name,
                cache_dir=str(dataset_cache),
                trust_remote_code=True,
            )
            # Extract and save features
            if hasattr(dataset, "features") and "features" in dataset.column_names:
                features_array = np.array([item["features"] for item in dataset])
            elif len(dataset) > 0 and isinstance(dataset[0], dict):
                first_item = dataset[0]
                if "features" in first_item:
                    features_array = np.array([item["features"] for item in dataset])
                else:
                    features_array = np.array(
                        [next(iter(item.values())) for item in dataset]
                    )
            else:
                features_array = np.array(dataset)
            np.save(str(target_path), features_array)
            # Validate file was created successfully
            if not target_path.exists():
                raise FileNotFoundError(f"Failed to save features to {target_path}")
            if target_path.stat().st_size == 0:
                raise ValueError(f"Saved file {target_path} is empty")
    finally:
        # Only clean up temp directory if target file exists and is valid
        if target_path.exists() and target_path.stat().st_size > 0:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        else:
            # Preserve temp directory for debugging if file wasn't created successfully
            print(
                f"Warning: Target file not found or empty. Temp directory preserved at {temp_dir}"
            )

    return target_path


def download_feature_data_file(
    target_file: str | Path,
    repo_id: str = "davidscripka/openwakeword_features",
    split_name: str = "ACAV100M",
    force: bool = False,
) -> Path:
    """Download pre-computed openwakeword features.

    Args:
        target_file: Full path to save the .npy file
        repo_id: HuggingFace dataset repository ID
        split_name: Name of the dataset split (default: "ACAV100M")
        force: If True, re-download even if file exists

    Returns:
        Path to downloaded file
    """
    import os
    import shutil

    target_path = Path(target_file)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Skip if file exists and not forcing
    if target_path.exists() and not force:
        return target_path

    # Set cache directory to writable location if not already set
    cache_dir = os.environ.get("HF_HOME", "/workspace/.cache/huggingface")
    cache_path = Path(cache_dir) / "hub"
    cache_path.mkdir(parents=True, exist_ok=True)

    # Try using snapshot_download to get all files, then look for the feature file
    temp_dir = target_path.parent / f".temp_{target_path.stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Download entire repository snapshot
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            local_dir=str(temp_dir),
            cache_dir=str(cache_path),
            force_download=force,
        )

        # Look for ACAV100M feature file in the downloaded directory
        # The file might be named differently or in a subdirectory
        feature_files = list(temp_dir.rglob("*ACAV100M*.npy"))
        feature_files.extend(list(temp_dir.rglob("*acav*.npy")))
        feature_files.extend(list(temp_dir.rglob("*.npy")))

        if feature_files:
            # Use the first .npy file found (or the most specific one)
            # Prefer files with "ACAV100M" in the name
            preferred = [
                f
                for f in feature_files
                if "ACAV100M" in f.name.upper() or "acav" in f.name.lower()
            ]
            source_file = preferred[0] if preferred else feature_files[0]
            # Copy to target location
            shutil.copy2(source_file, target_path)
            # Validate file was created successfully
            if not target_path.exists():
                raise FileNotFoundError(
                    f"Failed to copy {source_file} to {target_path}"
                )
            if target_path.stat().st_size == 0:
                raise ValueError(f"Copied file {target_path} is empty")
        else:
            # Try loading as dataset if files aren't found directly
            dataset_cache = Path(cache_dir) / "datasets"
            dataset_cache.mkdir(parents=True, exist_ok=True)
            dataset = load_dataset(
                repo_id,
                split=split_name,
                cache_dir=str(dataset_cache),
                trust_remote_code=True,
            )
            # Extract and save features
            if hasattr(dataset, "features") and "features" in dataset.column_names:
                features_array = np.array([item["features"] for item in dataset])
            elif len(dataset) > 0 and isinstance(dataset[0], dict):
                first_item = dataset[0]
                if "features" in first_item:
                    features_array = np.array([item["features"] for item in dataset])
                else:
                    features_array = np.array(
                        [next(iter(item.values())) for item in dataset]
                    )
            else:
                features_array = np.array(dataset)
            np.save(str(target_path), features_array)
            # Validate file was created successfully
            if not target_path.exists():
                raise FileNotFoundError(f"Failed to save features to {target_path}")
            if target_path.stat().st_size == 0:
                raise ValueError(f"Saved file {target_path} is empty")
    finally:
        # Only clean up temp directory if target file exists and is valid
        if target_path.exists() and target_path.stat().st_size > 0:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        else:
            # Preserve temp directory for debugging if file wasn't created successfully
            print(
                f"Warning: Target file not found or empty. Temp directory preserved at {temp_dir}"
            )

    return target_path


def download_all_training_data(
    base_dir: str | Path = "./services/models/wake/training-data",
    force: bool = False,
) -> dict[str, Path]:
    """Download all required training data files.

    Args:
        base_dir: Base directory for training data
        force: If True, re-download even if files exist

    Returns:
        Dictionary mapping data type to downloaded path
    """
    base_path = Path(base_dir)

    results = {
        "mit_rirs": download_mit_rirs(
            base_path / "mit_rirs",
            force=force,
        ),
        "background_clips": download_background_audio(
            base_path / "background_clips",
            force=force,
        ),
        "validation_features": download_validation_features(
            base_path / "validation_set_features.npy",
            force=force,
        ),
        "feature_data": download_feature_data_file(
            base_path / "openwakeword_features_ACAV100M_2000_hrs_16bit.npy",
            force=force,
        ),
    }

    return results


__all__ = [
    "download_mit_rirs",
    "download_background_audio",
    "download_validation_features",
    "download_feature_data_file",
    "download_all_training_data",
]
