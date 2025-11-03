"""Common GPU/CUDA utilities for consistent device detection and verification across services.

This module provides standardized functions for:
- CUDA device detection and verification
- Model device information extraction
- GPU health checking
- Consistent logging patterns
"""

from __future__ import annotations

import contextlib
from typing import Any


def get_pytorch_cuda_info() -> dict[str, Any]:
    """Get PyTorch CUDA information.

    Returns:
        Dict with CUDA availability and device information:
        - pytorch_cuda_available: bool
        - pytorch_cuda_device_count: int
        - pytorch_cuda_device_name: str or None
        - cuda_version: str or None (if available)
    """
    cuda_info = {
        "pytorch_cuda_available": False,
        "pytorch_cuda_device_count": 0,
        "pytorch_cuda_device_name": None,
        "cuda_version": None,
    }

    try:
        import torch

        cuda_info["pytorch_cuda_available"] = torch.cuda.is_available()
        if cuda_info["pytorch_cuda_available"]:
            device_count = torch.cuda.device_count()
            cuda_info["pytorch_cuda_device_count"] = device_count
            if device_count > 0:
                cuda_info["pytorch_cuda_device_name"] = torch.cuda.get_device_name(0)
                with contextlib.suppress(AttributeError, Exception):
                    cuda_info["cuda_version"] = torch.version.cuda
    except (ImportError, RuntimeError):
        pass

    return cuda_info


def validate_cuda_runtime() -> bool:
    """Validate CUDA runtime is actually usable.

    Performs a simple CUDA operation to verify the runtime works,
    not just that CUDA is detected.

    Returns:
        True if CUDA is available and working, False otherwise
    """
    try:
        import torch

        if not torch.cuda.is_available():
            return False

        # Try a simple CUDA operation to verify runtime works
        test_tensor = torch.zeros(1).cuda()
        del test_tensor
        torch.cuda.empty_cache()
        return True
    except (ImportError, RuntimeError, Exception):
        return False


def get_pytorch_model_device_info(model: Any) -> dict[str, Any]:
    """Get device information from a PyTorch model.

    Attempts to determine the actual device being used by checking:
    - Model's device property (if available)
    - Model parameters' device

    Args:
        model: PyTorch model instance

    Returns:
        Dict with device information:
        - actual_device: "cuda" or "cpu" (if determinable)
        - device_verified: bool indicating if we could verify device
        - model_on_device: str or None (device the model is actually on, e.g., "cuda:0")
    """
    device_info = {
        "actual_device": "unknown",
        "device_verified": False,
        "model_on_device": None,
    }

    try:
        if model is not None:
            # Check if model has a device property (some models expose this)
            if hasattr(model, "device"):
                try:
                    device_value = model.device
                    if device_value:
                        device_str = str(device_value)
                        device_info["model_on_device"] = device_str
                        # Extract "cuda" or "cpu" from "cuda:0" or "cpu"
                        base_device = device_str.split(":")[0].lower()
                        device_info["actual_device"] = base_device
                        device_info["device_verified"] = True
                except Exception:  # noqa: S110
                    # Non-critical: device property access failed, continue with parameter check
                    pass

            # Also check model parameters to see where they are
            try:
                first_param = next(model.parameters(), None)
                if first_param is not None:
                    param_device_str = str(first_param.device)
                    device_info["model_on_device"] = param_device_str
                    # Extract "cuda" or "cpu" from "cuda:0" or "cpu"
                    base_device = param_device_str.split(":")[0].lower()
                    device_info["actual_device"] = base_device
                    device_info["device_verified"] = True
            except (StopIteration, Exception):  # noqa: S110
                # Non-critical: parameter iteration failed, continue
                pass
    except Exception:  # noqa: S110
        # Non-critical: model device detection failed entirely, return partial info
        pass

    return device_info


def get_full_device_info(
    model: Any | None = None,
    intended_device: str | None = None,
) -> dict[str, Any]:
    """Get comprehensive device information combining PyTorch CUDA info and model device info.

    This is the standard function for services to use to get complete device information
    for logging and health checks.

    Args:
        model: Optional PyTorch model instance to check device
        intended_device: Optional intended device (e.g., from config)

    Returns:
        Dict with comprehensive device information:
        - intended_device: str or None (from config/request)
        - actual_device: "cuda" or "cpu" (if determinable)
        - device_verified: bool indicating if we could verify device
        - model_on_device: str or None (device the model is actually on)
        - pytorch_cuda_available: bool
        - pytorch_cuda_device_count: int
        - pytorch_cuda_device_name: str or None
        - cuda_version: str or None
    """
    device_info = {
        "intended_device": intended_device,
        "actual_device": "unknown",
        "device_verified": False,
        "model_on_device": None,
        "pytorch_cuda_available": False,
        "pytorch_cuda_device_count": 0,
        "pytorch_cuda_device_name": None,
        "cuda_version": None,
    }

    # Get PyTorch CUDA info
    cuda_info = get_pytorch_cuda_info()
    device_info.update(cuda_info)

    # Get model device info if model provided
    if model is not None:
        model_device_info = get_pytorch_model_device_info(model)
        device_info["actual_device"] = model_device_info.get("actual_device", "unknown")
        device_info["device_verified"] = model_device_info.get("device_verified", False)
        device_info["model_on_device"] = model_device_info.get("model_on_device")

    return device_info


def log_device_info(
    logger: Any,
    event_name: str,
    device_info: dict[str, Any],
    phase: str = "device_info",
    warn_on_mismatch: bool = True,
) -> None:
    """Log device information in a standardized format.

    Args:
        logger: Logger instance (from structured_logging)
        event_name: Event name for the log (e.g., "stt.model_loaded")
        device_info: Device info dict from get_full_device_info()
        phase: Phase identifier for the log
        warn_on_mismatch: If True, log warning if intended != actual device
    """
    logger.info(
        event_name,
        intended_device=device_info.get("intended_device"),
        actual_device=device_info.get("actual_device", "unknown"),
        device_verified=device_info.get("device_verified", False),
        model_on_device=device_info.get("model_on_device"),
        pytorch_cuda_available=device_info.get("pytorch_cuda_available", False),
        pytorch_cuda_device_count=device_info.get("pytorch_cuda_device_count", 0),
        pytorch_cuda_device_name=device_info.get("pytorch_cuda_device_name"),
        cuda_version=device_info.get("cuda_version"),
        phase=phase,
    )

    # Warn on device mismatch if enabled
    if warn_on_mismatch:
        intended = device_info.get("intended_device")
        actual = device_info.get("actual_device", "unknown")
        if intended == "cuda" and actual != "cuda":
            logger.warning(
                f"{event_name}.device_mismatch",
                intended_device=intended,
                actual_device=actual,
                model_on_device=device_info.get("model_on_device"),
                note="Model may have fallen back to CPU despite CUDA request",
                phase=phase,
            )
        elif intended == "cuda" and actual == "cuda":
            logger.info(
                f"{event_name}.gpu_usage_confirmed",
                device=actual,
                gpu_name=device_info.get("pytorch_cuda_device_name"),
                phase=phase,
            )


__all__ = [
    "get_pytorch_cuda_info",
    "validate_cuda_runtime",
    "get_pytorch_model_device_info",
    "get_full_device_info",
    "log_device_info",
]
