"""Factory for creating FastAPI apps with standardized observability setup."""

from __future__ import annotations

import asyncio
import warnings
from contextlib import asynccontextmanager
from typing import Any
from collections.abc import Awaitable, Callable

from fastapi import FastAPI

from services.common.health import HealthManager
from services.common.middleware import ObservabilityMiddleware
from services.common.structured_logging import get_logger
from services.common.tracing import setup_service_observability

# Suppress deprecation warnings (known issues, will be resolved by dependency updates)
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    module="pkg_resources",
)
# Suppress transformers TRANSFORMERS_CACHE deprecation warnings (we've migrated to HF_HOME)
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

logger = get_logger(__name__)


def create_service_app(
    service_name: str,
    service_version: str = "1.0.0",
    title: str | None = None,
    *,
    startup_callback: Callable[[], Any] | Callable[[], Awaitable[Any]] | None = None,
    shutdown_callback: Callable[[], Any] | Callable[[], Awaitable[Any]] | None = None,
    health_manager: HealthManager | None = None,
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
        health_manager: Optional HealthManager instance for tracking startup failures.
                        If provided, startup callback exceptions will be recorded
                        in the HealthManager. Services should create HealthManager at
                        module level and pass it here.

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
        """Standardized lifespan handler with service-specific startup/shutdown.

        IMPORTANT: FastAPI routes (including health endpoints) are registered immediately
        when the app is created, before this lifespan startup runs. This means:
        1. Uvicorn can accept HTTP requests as soon as it starts
        2. Health endpoints are accessible during startup
        3. Services should return 503 from /health/ready during startup and model loading
        4. Services should use BackgroundModelLoader for non-blocking model loading
        5. Services should mark_startup_complete() early (after initiating background loading)
        """
        # Startup
        try:
            # Call service-specific startup (services can access observability_manager
            # via get_observability_manager(service_name) if needed)
            # NOTE: This runs asynchronously, so uvicorn can still accept requests during startup
            if startup_callback:
                if asyncio.iscoroutinefunction(startup_callback):
                    await startup_callback()
                else:
                    startup_callback()

            logger.info(f"{service_name}.startup_complete")
        except Exception as exc:
            logger.error(f"{service_name}.startup_failed", error=str(exc))
            # Record failure in HealthManager if available
            if health_manager is not None:
                health_manager.record_startup_failure(
                    error=exc,
                    component="startup_callback",
                    is_critical=True,
                )
            # Continue without crashing - HealthManager now controls readiness

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

    # Store service name and create HTTP metrics for middleware access
    # Services can override this in their startup callbacks if needed
    from services.common.audio_metrics import create_http_metrics

    app.state.service_name = service_name
    http_metrics = create_http_metrics(observability_manager)
    app.state.http_metrics = http_metrics

    # Debug: Log metrics creation
    if http_metrics:
        logger.debug(
            "http_metrics.created",
            service=service_name,
            metrics=list(http_metrics.keys()),
            has_meter=observability_manager.get_meter() is not None,
        )
    else:
        logger.warning(
            "http_metrics.not_created",
            service=service_name,
            has_meter=observability_manager.get_meter() is not None,
        )

    # Add observability middleware automatically (after instrumentation)
    app.add_middleware(ObservabilityMiddleware)

    return app


__all__ = ["create_service_app"]
