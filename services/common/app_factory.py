"""Factory for creating FastAPI apps with standardized observability setup."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from collections.abc import Awaitable, Callable

from fastapi import FastAPI

from services.common.middleware import ObservabilityMiddleware
from services.common.structured_logging import get_logger
from services.common.tracing import setup_service_observability

logger = get_logger(__name__)


def create_service_app(
    service_name: str,
    service_version: str = "1.0.0",
    title: str | None = None,
    *,
    startup_callback: Callable[[], Any] | Callable[[], Awaitable[Any]] | None = None,
    shutdown_callback: Callable[[], Any] | Callable[[], Awaitable[Any]] | None = None,
) -> FastAPI:
    """Create a FastAPI app with standardized observability setup.

    This factory function provides:
    - Standardized lifespan context manager
    - Automatic observability setup (tracing + metrics)
    - Automatic FastAPI instrumentation (before app starts)
    - Automatic ObservabilityMiddleware registration
    - Service-specific startup/shutdown callbacks

    IMPORTANT: Services can access the observability_manager after factory setup
    using `get_observability_manager(service_name)` from `services.common.tracing`.
    This is necessary for creating service-specific metrics and setting it in
    health_manager.

    Args:
        service_name: Name of the service
        service_version: Version of the service
        title: FastAPI app title (defaults to service_name)
        startup_callback: Optional callback for service-specific startup logic.
                         Can be sync or async. Observability is already setup
                         before this callback runs, so services can access it via
                         get_observability_manager(service_name).
        shutdown_callback: Optional callback for service-specific shutdown logic.
                           Can be sync or async.

    Returns:
        Configured FastAPI app with observability middleware and instrumentation

    Example:
        ```python
        from services.common.tracing import get_observability_manager

        async def _startup():
            # Observability is already setup, get the manager
            _observability_manager = get_observability_manager("orchestrator")

            # Create service-specific metrics
            _llm_metrics = create_llm_metrics(_observability_manager)

            # Set in health manager
            _health_manager.set_observability_manager(_observability_manager)

            # Service-specific initialization
            _cfg = load_config()
            _health_manager.mark_startup_complete()

        app = create_service_app(
            "orchestrator",
            "1.0.0",
            startup_callback=_startup,
        )
        ```
    """

    # Setup observability BEFORE creating app (required for instrumentation)
    observability_manager = setup_service_observability(service_name, service_version)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> Any:  # noqa: ARG001
        """Standardized lifespan handler with service-specific startup/shutdown."""
        # Startup
        try:
            # Call service-specific startup (services can access observability_manager
            # via get_observability_manager(service_name) if needed)
            if startup_callback:
                if asyncio.iscoroutinefunction(startup_callback):
                    await startup_callback()
                else:
                    startup_callback()

            logger.info(f"{service_name}.startup_complete")
        except Exception as exc:
            logger.error(f"{service_name}.startup_failed", error=str(exc))
            # Continue without crashing - service will report not_ready

        yield

        # Shutdown
        if shutdown_callback:
            try:
                if asyncio.iscoroutinefunction(shutdown_callback):
                    await shutdown_callback()
                else:
                    shutdown_callback()
            except Exception as exc:
                logger.error(f"{service_name}.shutdown_failed", error=str(exc))

        logger.info(f"{service_name}.shutdown")

    # Create FastAPI app with lifespan
    app = FastAPI(
        title=title or service_name,
        version=service_version,
        lifespan=lifespan,
    )

    # Instrument FastAPI IMMEDIATELY after app creation (before middleware is added)
    # This ensures instrumentation happens before uvicorn initializes the app
    observability_manager.instrument_fastapi(app)

    # Add observability middleware automatically (after instrumentation)
    app.add_middleware(ObservabilityMiddleware)

    return app


__all__ = ["create_service_app"]
