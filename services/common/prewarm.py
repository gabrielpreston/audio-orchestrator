"""Model pre-warming utilities for performance optimization.

This module provides generic pre-warming patterns for any model service to
trigger torch.compile() warmup and ensure models are ready before serving traffic.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

from services.common.structured_logging import get_logger


async def wait_for_model_loader(
    model_loader: Any,
    logger: Any,
    max_wait_seconds: float = 300.0,
    poll_interval: float = 0.5,
) -> bool:
    """Wait for model loader to finish loading.

    Args:
        model_loader: BackgroundModelLoader instance
        logger: Logger instance for logging
        max_wait_seconds: Maximum time to wait (default: 5 minutes)
        poll_interval: Interval between checks in seconds (default: 0.5)

    Returns:
        True if models loaded successfully, False if timeout
    """
    if not model_loader:
        return False

    if not model_loader.is_loading():
        return bool(model_loader.is_loaded())

    logger.info(
        "prewarm.waiting_for_models",
        max_wait_seconds=max_wait_seconds,
        message="Waiting for models to finish loading before pre-warming",
    )

    elapsed = 0.0
    while model_loader.is_loading() and elapsed < max_wait_seconds:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    if model_loader.is_loading():
        logger.warning(
            "prewarm.timeout",
            elapsed_seconds=elapsed,
            max_wait_seconds=max_wait_seconds,
            message="Model loading timeout exceeded, skipping pre-warm",
        )
        return False

    # Ensure models are actually loaded
    if not model_loader.is_loaded():
        logger.warning(
            "prewarm.models_not_loaded",
            message="Models finished loading but not marked as loaded",
        )
        return False

    return True


async def prewarm_if_enabled(
    prewarm_func: Callable[[], Awaitable[Any]],
    service_name: str,
    logger: Any | None = None,
    model_loader: Any | None = None,
    dependency_name: str = "prewarm",
    health_manager: Any | None = None,
    max_wait_seconds: float = 300.0,
) -> bool:
    """Execute pre-warming if enabled and register health dependency.

    Pre-warming ensures the first compilation run happens during startup rather than
    on the first real request, preventing timeouts. This function:
    1. Checks if pre-warming is enabled via {SERVICE}_ENABLE_PREWARM env var
    2. Waits for models to load (if model_loader provided)
    3. Executes prewarm_func() to trigger compilation warmup
    4. Registers health dependency (if health_manager provided)
    5. Logs duration and errors (non-blocking - marks complete on failure)

    Args:
        prewarm_func: Async function that performs the actual pre-warming
        service_name: Service name for env var lookup and logging
        logger: Optional logger instance (creates one if None)
        model_loader: Optional BackgroundModelLoader to wait for
        dependency_name: Name for health dependency registration
        health_manager: Optional HealthManager to register dependency with
        max_wait_seconds: Maximum time to wait for model loading

    Returns:
        True if pre-warming completed successfully, False otherwise
    """
    if logger is None:
        logger = get_logger(__name__, service_name=service_name)

    # Check if pre-warm is enabled via environment variable
    enable_prewarm_env = f"{service_name.upper()}_ENABLE_PREWARM"
    enable_prewarm = os.getenv(enable_prewarm_env, "true").lower() in (
        "true",
        "1",
        "yes",
    )

    if not enable_prewarm:
        logger.info(
            "prewarm.disabled",
            service=service_name,
            env_var=enable_prewarm_env,
            message="Pre-warm disabled via environment variable",
        )
        return True  # Mark complete if disabled (not an error)

    logger.info(
        "prewarm.start",
        service=service_name,
        message="Starting model pre-warming to trigger torch.compile() warmup",
    )

    prewarm_start = time.time()

    try:
        # Wait for models to be loaded before pre-warming
        if model_loader:
            models_ready = await wait_for_model_loader(
                model_loader,
                logger,
                max_wait_seconds=max_wait_seconds,
            )
            if not models_ready:
                logger.warning(
                    "prewarm.models_not_ready",
                    service=service_name,
                    message="Models not ready, skipping pre-warm",
                )
                return False

            logger.info(
                "prewarm.models_ready",
                service=service_name,
                message="Models loaded, proceeding with pre-warm",
            )

        # Perform pre-warming
        await prewarm_func()

        prewarm_duration = (time.time() - prewarm_start) * 1000

        logger.info(
            "prewarm.complete",
            service=service_name,
            duration_ms=round(prewarm_duration, 2),
            message="Model pre-warming completed successfully",
        )

        # Register health dependency if health manager provided
        if health_manager:

            def check_prewarm_complete() -> bool:
                """Health check function for pre-warming dependency."""
                return True  # Always return True once pre-warming completes

            health_manager.register_dependency(dependency_name, check_prewarm_complete)
            logger.debug(
                "prewarm.health_dependency_registered",
                service=service_name,
                dependency=dependency_name,
            )

        return True

    except Exception as exc:
        # Log error but don't block startup - service can still work
        prewarm_duration = (time.time() - prewarm_start) * 1000
        logger.error(
            "prewarm.failed",
            service=service_name,
            error=str(exc),
            error_type=type(exc).__name__,
            duration_ms=round(prewarm_duration, 2),
            message="Pre-warm failed but continuing startup - first request may be slower",
        )

        # Still register health dependency to allow service to start
        # The health check will still report ready, but first request might be slow
        if health_manager:

            def check_prewarm_complete() -> bool:
                return True  # Mark complete anyway

            health_manager.register_dependency(dependency_name, check_prewarm_complete)

        return False
