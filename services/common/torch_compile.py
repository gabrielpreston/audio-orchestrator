"""PyTorch model compilation utilities for performance optimization.

This module provides centralized torch.compile() functionality with consistent
error handling and configuration across all services.
"""

from __future__ import annotations

import os
import time
from typing import Any

from services.common.structured_logging import get_logger


def configure_torch_dynamo(
    suppress_errors: bool = True, logger: Any | None = None
) -> bool:
    """Configure torch._dynamo for Docker compatibility.

    This fixes getpwuid() errors in Docker containers without /etc/passwd entries.
    Must be set early to affect all subsequent torch.compile() calls.

    Args:
        suppress_errors: If True, configure suppress_errors=True
        logger: Optional logger instance for logging

    Returns:
        True if configuration succeeded, False otherwise
    """
    if not suppress_errors:
        return True

    try:
        import torch._dynamo

        torch._dynamo.config.suppress_errors = True
        if logger:
            logger.info(
                "torch_compile.dynamo_configured",
                suppress_errors=True,
                phase="optimization_setup",
                message="torch._dynamo configured to suppress errors and fallback gracefully",
            )
        return True
    except (ImportError, AttributeError) as e:
        if logger:
            logger.debug(
                "torch_compile.dynamo_unavailable",
                error=str(e),
                phase="optimization_setup",
                message="torch._dynamo not available, compilation may fail",
            )
        return False


def get_compile_mode(service_name: str, default: str = "default") -> str:
    """Get compile mode from environment variable.

    Args:
        service_name: Service name (e.g., "flan", "guardrails")
        default: Default compile mode if env var not set

    Returns:
        Compile mode string (e.g., "default", "max-autotune-no-cudagraphs")
    """
    env_var = f"{service_name.upper()}_COMPILE_MODE"
    return os.getenv(env_var, default)


def compile_model_if_enabled(
    model: Any,
    service_name: str,
    model_name: str,
    logger: Any | None = None,
    compile_mode: str | None = None,
    suppress_errors: bool = True,
) -> Any:
    """Apply torch.compile() if enabled via environment variable.

    Checks {SERVICE}_ENABLE_TORCH_COMPILE env var (default: true).
    Configures torch._dynamo for Docker compatibility and applies compilation
    with graceful error handling.

    Args:
        model: PyTorch model (torch.nn.Module) to compile
        service_name: Service name for env var lookup (e.g., "flan", "guardrails")
        model_name: Model name for logging (e.g., "flan_t5", "toxic_bert")
        logger: Optional logger instance for logging
        compile_mode: Optional compile mode override (uses env var if None)
        suppress_errors: If True, configure torch._dynamo to suppress errors

    Returns:
        Compiled model if compilation enabled and successful, original model otherwise
    """
    if logger is None:
        logger = get_logger(__name__)

    # Check if compilation is enabled
    enable_compile_env = f"{service_name.upper()}_ENABLE_TORCH_COMPILE"
    enable_compile = os.getenv(enable_compile_env, "true").lower() in (
        "true",
        "1",
        "yes",
    )

    if not enable_compile:
        logger.debug(
            "torch_compile.disabled",
            service=service_name,
            model=model_name,
            env_var=enable_compile_env,
            phase="compilation_check",
        )
        return model

    # Check if torch.compile is available
    try:
        import torch
    except ImportError:
        logger.warning(
            "torch_compile.torch_unavailable",
            service=service_name,
            model=model_name,
            phase="compilation_check",
            message="PyTorch not available, skipping compilation",
        )
        return model

    if not hasattr(torch, "compile"):
        logger.warning(
            "torch_compile.not_supported",
            service=service_name,
            model=model_name,
            pytorch_version=getattr(torch, "__version__", "unknown"),
            phase="compilation_check",
            message="torch.compile() not available (requires PyTorch 2.0+)",
        )
        return model

    # Configure torch._dynamo for Docker compatibility
    configure_torch_dynamo(suppress_errors=suppress_errors, logger=logger)

    # Get compile mode
    if compile_mode is None:
        compile_mode = get_compile_mode(service_name, default="default")

    # Attempt compilation
    compile_start = time.time()
    try:
        compiled_model = torch.compile(model, mode=compile_mode)
        compile_duration = (time.time() - compile_start) * 1000

        logger.info(
            "torch_compile.success",
            service=service_name,
            model=model_name,
            mode=compile_mode,
            duration_ms=round(compile_duration, 2),
            phase="compilation",
            message="torch.compile() optimization applied successfully",
        )
        return compiled_model
    except Exception as e:
        compile_duration = (time.time() - compile_start) * 1000
        logger.warning(
            "torch_compile.failed",
            service=service_name,
            model=model_name,
            mode=compile_mode,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=round(compile_duration, 2),
            phase="compilation",
            message="torch.compile() failed, continuing with uncompiled model",
        )
        # Return original model on failure (graceful degradation)
        return model
