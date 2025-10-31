"""Unified model download utilities for force download functionality.

This module provides library-specific helpers for forcing model downloads
across different ML libraries (transformers, faster-whisper, speechbrain).
"""

from __future__ import annotations

import os
import shutil
import warnings
from pathlib import Path
from typing import Any

# Suppress transformers TRANSFORMERS_CACHE deprecation warnings (we've migrated to HF_HOME)
# Must be before transformers import
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module="transformers.utils.hub",
    message=".*TRANSFORMERS_CACHE.*",
)
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module="transformers",
    message=".*TRANSFORMERS_CACHE.*",
)


def force_download_transformers(
    model_name: str,
    cache_dir: str | None = None,
    force: bool = False,
    model_class: type[Any] | None = None,
) -> Any:
    """Force download transformers model.

    Args:
        model_name: HuggingFace model identifier (e.g., "google/flan-t5-large")
        cache_dir: Cache directory for transformers (optional)
        force: If True, forces re-download by passing force_download=True
        model_class: Optional model class (e.g., AutoModelForSeq2SeqLM)

    Returns:
        Loaded model instance

    Raises:
        ImportError: If transformers library is not available
    """
    try:
        from transformers import AutoModel

        if model_class is None:
            model_class = AutoModel

        kwargs: dict[str, Any] = {}
        if cache_dir:
            kwargs["cache_dir"] = cache_dir
        if force:
            kwargs["force_download"] = True

        return model_class.from_pretrained(model_name, **kwargs)
    except ImportError as e:
        raise ImportError(
            "transformers library not available. Install with: pip install transformers"
        ) from e


def force_download_faster_whisper(
    model_name: str,
    download_root: str,
    force: bool = False,
) -> str:
    """Force download faster-whisper model by deleting cache directory.

    Args:
        model_name: Model name (e.g., "medium.en")
        download_root: Root directory for model downloads
        force: If True, deletes cache directory before returning path

    Returns:
        Path to model (for use with WhisperModel initialization)

    Note:
        faster-whisper doesn't have a built-in force_download parameter,
        so we delete the cache directory when force=True.
    """
    model_path = Path(download_root) / model_name

    if force and model_path.exists():
        # Delete existing cache directory
        shutil.rmtree(model_path)
        # Return model name (not path) so WhisperModel will download
        return model_name

    # If cache exists and not forcing, return path
    if model_path.exists():
        return str(model_path)

    # Cache doesn't exist, return model name for download
    return model_name


def force_download_speechbrain(
    model_source: str,
    savedir: str,
    force: bool = False,
    enhancement_class: type[Any] | None = None,
) -> Any:
    """Force download SpeechBrain model by deleting cache directory.

    Args:
        model_source: Model source identifier (e.g., "speechbrain/metricgan-plus-voicebank")
        savedir: Directory where model will be saved
        force: If True, deletes savedir directory before loading
        enhancement_class: Optional enhancement class for dependency injection (testing)

    Returns:
        Loaded model instance

    Raises:
        ImportError: If speechbrain library is not available
    """
    savedir_path = Path(savedir)

    if force and savedir_path.exists():
        # Delete existing cache directory
        shutil.rmtree(savedir_path)

    try:
        if enhancement_class is not None:
            return enhancement_class.from_hparams(source=model_source, savedir=savedir)
        else:
            from speechbrain.inference.enhancement import SpectralMaskEnhancement

            return SpectralMaskEnhancement.from_hparams(
                source=model_source, savedir=savedir
            )
    except ImportError as e:
        raise ImportError(
            "speechbrain library not available. Install with: pip install speechbrain"
        ) from e


def force_download_bark(
    force: bool = False,
) -> None:
    """Force download Bark models by manipulating HuggingFace cache.

    Args:
        force: If True, manipulates HF cache to force re-download

    Note:
        Bark uses HuggingFace transformers under the hood, so we can use
        transformers force_download mechanism. This function is meant to be
        called before preload_models() to set up the environment.
    """
    if force:
        # Set environment variables to force HuggingFace to re-download
        # This will be checked by transformers library when Bark loads models
        os.environ["HF_HUB_FORCE_DOWNLOAD"] = "1"
    else:
        # Remove force download flag
        os.environ.pop("HF_HUB_FORCE_DOWNLOAD", None)


__all__ = [
    "force_download_transformers",
    "force_download_faster_whisper",
    "force_download_speechbrain",
    "force_download_bark",
]
