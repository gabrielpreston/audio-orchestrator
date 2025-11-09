"""
Discord service HTTP API for tool integration.
"""

import asyncio
from contextlib import suppress
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from fastapi import HTTPException

from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints
from services.common.http_client_factory import create_dependency_health_client
from services.common.model_loader import BackgroundModelLoader

# Configure logging
from services.common.structured_logging import get_logger
from services.common.tracing import get_observability_manager
from services.common.app_factory import create_service_app

from .audio_processor_wrapper import AudioProcessorWrapper
from .config import load_config
from .discord_voice import TranscriptPublisher, VoiceBot
from .models import (
    CapabilitiesResponse,
    CapabilityInfo,
    MessageSendRequest,
    MessageSendResponse,
    TranscriptNotificationRequest,
    TranscriptNotificationResponse,
)
from .wake import WakeDetector


logger = get_logger(__name__, service_name="discord")

# Health manager for service resilience (must remain module-level for app creation)
_health_manager = HealthManager("discord")
# Note: Other stateful components (_bot, _bot_task, _stt_health_client, etc.)
# are now stored in app.state during startup and accessed via app.state or request.app.state


# Remove old tool models - now using models.py


def _create_transcript_publisher() -> TranscriptPublisher:
    """Create a transcript publisher for the VoiceBot."""

    async def transcript_publisher(transcript_data: dict[str, Any]) -> None:
        """Publish transcript data - currently just logs it."""
        logger.info("discord.transcript_received", **transcript_data)

    return transcript_publisher


def _get_wake_model_directory() -> Path:
    """Resolve wake model directory path.

    Uses openwakeword's default location which is mounted via volume in containers.
    With HOME=/app, this resolves to /app/.local/share/openwakeword/models,
    which is mounted from ./services/models/wake on the host.

    Returns:
        Path to wake model directory
    """
    # Use openwakeword's default location: ~/.local/share/openwakeword/models
    # With HOME=/app in docker-compose, this becomes /app/.local/share/openwakeword/models
    # This matches the volume mount: ./services/models/wake -> /app/.local/share/openwakeword/models
    home_dir = Path.home()
    default_wake_dir = home_dir / ".local" / "share" / "openwakeword" / "models"
    return default_wake_dir


def _load_wake_models_from_cache() -> bool | None:
    """Check if wake models exist in cache directory.

    Returns:
        True if models found, None if cache miss
    """
    wake_dir = _get_wake_model_directory()
    if wake_dir.exists():
        model_files = list(wake_dir.glob("*.tflite")) + list(wake_dir.glob("*.onnx"))
        return True if model_files else None
    return None


def _download_wake_models() -> bool:
    """Download openwakeword models to target directory.

    This is a side-effect function that downloads files but returns None.
    BackgroundModelLoader will use True as sentinel value for success.

    Returns:
        True if download successful, False if openwakeword unavailable
    """
    try:
        from openwakeword import utils as openwakeword_utils
    except ImportError:
        # Graceful degradation - openwakeword not available
        logger.warning(
            "discord.openwakeword_unavailable",
            message="openwakeword not available, cannot download models",
        )
        return False

    wake_dir = _get_wake_model_directory()
    # Ensure directory exists (mkdir will create parent directories if needed)
    wake_dir.mkdir(parents=True, exist_ok=True)

    # openwakeword.utils.download_models() signature:
    # download_models(model_names: List[str] = [], target_directory: str = ...)
    # Empty model_names list downloads all pre-trained models
    openwakeword_utils.download_models(
        model_names=[],  # Download all pre-trained models
        target_directory=str(wake_dir),
    )
    return True  # Side-effect function, return success indicator


def _get_infrastructure_models_directory() -> Path:
    """Resolve infrastructure models directory path.

    Returns the package-level infrastructure models directory where openwakeword
    expects to find infrastructure models (melspectrogram, embedding_model, silero_vad).
    This directory is mounted via volume in containers.

    Returns:
        Path to infrastructure models directory
    """
    try:
        import openwakeword
    except ImportError:
        # Fallback if openwakeword not available
        return Path(
            "/usr/local/lib/python3.11/site-packages/openwakeword/resources/models"
        )

    # Get package directory: Path(openwakeword.__file__).parent / "resources" / "models"
    package_dir = Path(openwakeword.__file__).parent / "resources" / "models"
    return package_dir


def _check_infrastructure_models() -> bool:
    """Check if all required infrastructure models exist.

    Returns:
        True if all required infrastructure models exist, False otherwise
    """
    infrastructure_models = [
        "melspectrogram.onnx",
        "embedding_model.onnx",
        "silero_vad.onnx",
    ]
    package_dir = _get_infrastructure_models_directory()

    if not package_dir.exists():
        return False

    for model_name in infrastructure_models:
        model_path = package_dir / model_name
        if not model_path.exists():
            return False

    return True


def _download_infrastructure_models() -> bool:
    """Download infrastructure models to mounted package directory if missing.

    Downloads all models to temporary directory, filters to extract only infrastructure
    models, then moves them to the package directory (which is mounted via volume).

    Returns:
        True if download successful, False if openwakeword unavailable or download fails
    """
    try:
        from openwakeword import utils as openwakeword_utils
    except ImportError:
        # Graceful degradation - openwakeword not available
        logger.warning(
            "discord.openwakeword_unavailable",
            message="openwakeword not available, cannot download infrastructure models",
        )
        return False

    infrastructure_models = [
        "melspectrogram.onnx",
        "embedding_model.onnx",
        "silero_vad.onnx",
    ]
    package_dir = _get_infrastructure_models_directory()

    # Create temporary directory for download
    temp_dir = Path(tempfile.mkdtemp(prefix="openwakeword_infrastructure_"))

    try:
        # Download all models to temporary directory
        # download_models with empty model_names downloads ALL models (wake + infrastructure)
        openwakeword_utils.download_models(
            model_names=[],  # Download all models
            target_directory=str(temp_dir),
        )

        # Ensure package directory exists
        package_dir.mkdir(parents=True, exist_ok=True)

        # Filter to extract only infrastructure models and move to package directory
        moved_count = 0
        for model_name in infrastructure_models:
            src = temp_dir / model_name
            if src.exists():
                dst = package_dir / model_name
                shutil.move(str(src), str(dst))
                moved_count += 1
                logger.info(
                    "discord.infrastructure_model_downloaded",
                    model_name=model_name,
                    destination=str(dst),
                )
            else:
                logger.warning(
                    "discord.infrastructure_model_not_found_in_download",
                    model_name=model_name,
                    temp_directory=str(temp_dir),
                )

        if moved_count < len(infrastructure_models):
            logger.warning(
                "discord.infrastructure_models_partial_download",
                moved_count=moved_count,
                expected_count=len(infrastructure_models),
                message="Some infrastructure models were not found in download",
            )
            return False

        logger.info(
            "discord.infrastructure_models_downloaded",
            count=moved_count,
            directory=str(package_dir),
        )
        return True

    except Exception as exc:
        logger.error(
            "discord.infrastructure_models_download_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return False
    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as cleanup_exc:
            logger.debug(
                "discord.temp_directory_cleanup_failed",
                error=str(cleanup_exc),
                temp_directory=str(temp_dir),
            )


async def _start_discord_bot(
    config: Any, observability_manager: Any, app_instance: Any
) -> None:
    """Start the Discord bot as a background task."""
    try:
        logger.info("discord.bot_starting")

        # Wait for wake models to be loaded before initializing WakeDetector
        wake_model_loader = getattr(app_instance.state, "wake_model_loader", None)
        if wake_model_loader:
            logger.info("discord.waiting_for_wake_models")
            models_loaded = await wake_model_loader.ensure_loaded(timeout=300.0)
            if not models_loaded:
                logger.warning(
                    "discord.wake_models_not_loaded",
                    message="Wake models failed to load, will fall back to transcript-based detection",
                )
            else:
                logger.info("discord.wake_models_loaded")

        # Check and download infrastructure models before initializing WakeDetector
        if not _check_infrastructure_models():
            logger.info(
                "discord.infrastructure_models_missing",
                message="Infrastructure models not found, downloading...",
            )
            download_success = _download_infrastructure_models()
            if not download_success:
                logger.warning(
                    "discord.infrastructure_models_download_failed",
                    message="Failed to download infrastructure models, will fall back to transcript-based detection",
                )
            else:
                logger.info("discord.infrastructure_models_ready")
        else:
            logger.info(
                "discord.infrastructure_models_found",
                message="Infrastructure models already present",
            )

        # Get metrics from app.state
        audio_metrics = getattr(app_instance.state, "audio_metrics", {})

        # Create bot components
        wake_detector = WakeDetector(config.wake)
        logger.info(
            "discord.wake_detector_initialized",
            model_loaded=wake_detector._model is not None,
            enabled=config.wake.enabled,
            threshold=config.wake.activation_threshold,
            target_sample_rate=config.wake.target_sample_rate_hz,
            model_paths=config.wake.model_paths,
        )
        audio_processor_wrapper = AudioProcessorWrapper(
            config.audio, config.telemetry, wake_detector=wake_detector
        )
        transcript_publisher = _create_transcript_publisher()

        # Create VoiceBot instance
        # Pass health check callbacks to use HealthManager pattern (aligned with all services)
        bot = VoiceBot(
            config,
            audio_processor_wrapper,
            wake_detector,
            transcript_publisher,
            metrics=audio_metrics,
            stt_health_check=_check_stt_health,
            orchestrator_health_check=_check_orchestrator_health,
        )

        # Share the observability manager with the bot's health manager
        # The bot has its own health manager for internal tracking, but we can
        # share observability for consistent metrics
        if observability_manager:
            bot._health_manager.set_observability_manager(observability_manager)

        # Store bot reference in app.state
        app_instance.state.bot = bot

        # Mark bot health manager startup as complete (bot is initialized)
        bot._health_manager.mark_startup_complete()

        # Wait for dependencies to be ready before connecting to Discord
        logger.info("discord.waiting_for_dependencies")
        timeout = 300.0  # 5 minutes - same as _segment_consumer
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            if await bot._health_manager.check_ready():
                logger.info("discord.dependencies_ready")
                break
            await asyncio.sleep(2.0)  # Same polling interval as _segment_consumer
        else:
            logger.error(
                "discord.dependency_timeout",
                timeout=timeout,
                message="Dependencies not ready within timeout, bot will not connect",
            )
            # Set bot to error state but don't raise - HTTP API can still work
            app_instance.state.bot = {
                "status": "error",
                "mode": "bot",
                "error": "Dependencies not ready within timeout",
            }
            return  # Exit early - don't start bot connection

        # Validate token before attempting connection
        token = config.discord.token
        # Check for placeholder/missing token values
        placeholder_values = {"changeme", ""}
        is_invalid_token = (
            not token or token.strip() in placeholder_values or len(token.strip()) < 10
        )
        if is_invalid_token:
            logger.error(
                "discord.bot_token_invalid",
                token_set=bool(token),
                token_length=len(token) if token else 0,
                message="Discord bot token is missing or set to placeholder value. "
                "Set DISCORD_BOT_TOKEN in services/discord/.env.secrets",
            )
            # Set bot to error state but don't raise - HTTP API can still work
            app_instance.state.bot = {
                "status": "error",
                "mode": "bot",
                "error": "Invalid bot token",
            }
            return

        # Start bot connection (non-blocking)
        # Wrap in error handler to catch connection failures
        async def _bot_start_with_error_handling() -> None:
            """Start bot with error handling and logging."""
            try:
                await bot.start(token)
            except Exception as exc:
                error_type = type(exc).__name__
                is_auth_error = "LoginFailure" in error_type or "401" in str(exc)

                logger.error(
                    "discord.bot_connection_failed",
                    error=str(exc),
                    error_type=error_type,
                    is_authentication_error=is_auth_error,
                    message="Discord bot failed to connect or crashed"
                    + (
                        ". Check DISCORD_BOT_TOKEN in services/discord/.env.secrets"
                        if is_auth_error
                        else ""
                    ),
                )
                import traceback

                logger.error(
                    "discord.bot_connection_traceback",
                    traceback=traceback.format_exc(),
                )
                # Set bot to error state
                app_instance.state.bot = {
                    "status": "error",
                    "mode": "bot",
                    "error": str(exc),
                }
                raise

        bot_task = asyncio.create_task(_bot_start_with_error_handling())
        app_instance.state.bot_task = bot_task

        logger.info("discord.bot_start_task_created")

        # Bot task runs forever, so we don't await it here
        # The on_ready event will fire when the bot connects
        # Errors from the task will be logged via _bot_start_with_error_handling

    except Exception as exc:
        logger.error(
            "discord.bot_initialization_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        import traceback

        logger.error("discord.bot_init_traceback", traceback=traceback.format_exc())
        # Set bot to error state but don't crash the HTTP API
        app_instance.state.bot = {"status": "error", "mode": "bot", "error": str(exc)}
        if hasattr(app_instance.state, "bot_task") and app_instance.state.bot_task:
            app_instance.state.bot_task.cancel()
            app_instance.state.bot_task = None


async def _startup() -> None:
    """Initialize Discord bot and HTTP API on startup."""
    logger.info("discord.startup_event_called")

    try:
        # Get observability manager (factory already setup observability)
        observability_manager = get_observability_manager("discord")

        # Register service-specific metrics using centralized helper
        from services.common.audio_metrics import MetricKind, register_service_metrics

        metrics = register_service_metrics(
            observability_manager,
            kinds=[MetricKind.STT, MetricKind.AUDIO, MetricKind.SYSTEM],
        )
        stt_metrics = metrics["stt"]
        audio_metrics = metrics["audio"]
        system_metrics = metrics["system"]

        # HTTP metrics already available from app_factory via app.state.http_metrics

        # Store metrics and observability in app.state
        app.state.stt_metrics = stt_metrics
        app.state.audio_metrics = audio_metrics
        app.state.system_metrics = system_metrics
        app.state.observability_manager = observability_manager

        # Set observability manager in health manager
        _health_manager.set_observability_manager(observability_manager)

        # Initialize bot and bot_task to None in app.state
        app.state.bot = None
        app.state.bot_task = None

        # Load configuration (critical component)
        try:
            config = load_config()
        except Exception as exc:
            _health_manager.record_startup_failure(
                error=exc, component="config", is_critical=True
            )
            raise  # Re-raise so app_factory also records it

        # Initialize resilient HTTP clients for health checks using factory
        # For dependency health checks, grace period is 0.0 by default for accurate readiness
        try:
            stt_url = os.getenv("STT_BASE_URL", "http://stt:9000")
            stt_health_client = create_dependency_health_client(
                service_name="stt",
                base_url=stt_url,
                env_prefix="STT",
            )
            app.state.stt_health_client = stt_health_client
        except Exception as exc:
            # Health client is optional - record as non-critical
            _health_manager.record_startup_failure(
                error=exc, component="stt_health_client", is_critical=False
            )
            logger.warning("discord.stt_health_client_init_failed", error=str(exc))
            app.state.stt_health_client = None

        try:
            orch_url = os.getenv("ORCHESTRATOR_BASE_URL", "http://orchestrator:8200")
            orchestrator_health_client = create_dependency_health_client(
                service_name="orchestrator",
                base_url=orch_url,
                env_prefix="ORCHESTRATOR",
            )
            app.state.orchestrator_health_client = orchestrator_health_client
        except Exception as exc:
            # Health client is optional - record as non-critical
            _health_manager.record_startup_failure(
                error=exc, component="orchestrator_health_client", is_critical=False
            )
            logger.warning(
                "discord.orchestrator_health_client_init_failed", error=str(exc)
            )
            app.state.orchestrator_health_client = None

        # Initialize wake model loader with cache-first + download fallback (critical component)
        try:
            wake_model_loader = BackgroundModelLoader(
                cache_loader_func=_load_wake_models_from_cache,
                download_loader_func=_download_wake_models,
                logger=logger,
                loader_name="wake_models",
                timeout_seconds=300.0,
                is_side_effect=True,
            )

            # Start background loading (non-blocking)
            await wake_model_loader.initialize()
            logger.info("discord.wake_model_loader_initialized")

            # Store in app.state
            app.state.wake_model_loader = wake_model_loader
        except Exception as exc:
            _health_manager.record_startup_failure(
                error=exc, component="wake_model_loader", is_critical=True
            )
            raise  # Re-raise so app_factory also records it

        # Register dependencies
        _health_manager.register_dependency("stt", _check_stt_health)
        _health_manager.register_dependency("orchestrator", _check_orchestrator_health)

        # Register wake model loader as dependency for health checks
        # Models must be loaded AND not currently loading for service to be ready
        _health_manager.register_dependency(
            "wake_models",
            lambda: (
                app.state.wake_model_loader.is_loaded()
                and not app.state.wake_model_loader.is_loading()
                if hasattr(app.state, "wake_model_loader")
                and app.state.wake_model_loader
                else False
            ),
        )

        # Start Discord bot as background task
        asyncio.create_task(_start_discord_bot(config, observability_manager, app))

        # Only mark startup complete if no critical failures occurred
        if not _health_manager.has_startup_failure():
            _health_manager.mark_startup_complete()
            logger.info("discord.http_api_started")
        else:
            logger.warning(
                "discord.http_api_not_started",
                reason="critical_failure_detected",
            )

    except Exception as exc:
        logger.error("discord.http_startup_failed", error=str(exc))
        import traceback

        logger.error("discord.startup_traceback", traceback=traceback.format_exc())
        # Failure already recorded above or will be recorded by app_factory
        # Re-raise so app_factory can also record it
        raise


async def _check_stt_health() -> bool:
    """Check STT service health via resilient HTTP client."""
    stt_health_client = getattr(app.state, "stt_health_client", None)
    if stt_health_client is None:
        return False
    try:
        result = await stt_health_client.check_health()
        return bool(result)
    except Exception as exc:
        logger.debug("health.stt_check_failed", error=str(exc))
        return False


async def _check_orchestrator_health() -> bool:
    """Check Orchestrator service health via resilient HTTP client."""
    orchestrator_health_client = getattr(app.state, "orchestrator_health_client", None)
    if orchestrator_health_client is None:
        return False
    try:
        result = await orchestrator_health_client.check_health()
        return bool(result)
    except Exception as exc:
        logger.debug("health.orchestrator_check_failed", error=str(exc))
        return False


async def _shutdown() -> None:
    """Shutdown HTTP API and Discord bot."""
    logger.info("discord.shutdown_event_called")

    # Get bot and bot_task from app.state
    bot = getattr(app.state, "bot", None)
    bot_task = getattr(app.state, "bot_task", None)

    # Close Discord bot if it's running
    if bot and isinstance(bot, VoiceBot):
        try:
            logger.info("discord.bot_shutting_down")
            await bot.close()
            logger.info("discord.bot_closed")
        except Exception as exc:
            logger.error(
                "discord.bot_shutdown_error",
                error=str(exc),
                error_type=type(exc).__name__,
            )

    # Cancel bot task if it exists
    if bot_task:
        try:
            if not bot_task.done():
                bot_task.cancel()
                with suppress(asyncio.CancelledError):
                    await bot_task
            logger.info("discord.bot_task_cancelled")
        except Exception as exc:
            logger.error(
                "discord.bot_task_cancel_error",
                error=str(exc),
                error_type=type(exc).__name__,
            )
        finally:
            app.state.bot_task = None

    app.state.bot = None
    logger.info("discord.http_api_shutdown")


# Create app using factory pattern (after all function definitions)
app = create_service_app(
    "discord",
    "1.0.0",
    title="Discord Voice Service",
    startup_callback=_startup,
    shutdown_callback=_shutdown,
    health_manager=_health_manager,
)


def _get_bot_status() -> dict[str, Any]:
    """Get bot connection status."""
    try:
        bot = getattr(app.state, "bot", None)
        if bot is None:
            return {"connected": False, "mode": "initializing"}
        elif isinstance(bot, VoiceBot):
            # VoiceBot inherits from discord.Client which has is_ready property
            return {
                "connected": bot.is_ready,
                "mode": "bot",
                "user": str(bot.user) if bot.user else None,
            }
        elif isinstance(bot, dict):
            return {
                "connected": False,
                "mode": bot.get("mode", "unknown"),
                "status": bot.get("status", "unknown"),
                "error": bot.get("error"),
            }
        else:
            return {"connected": False, "mode": "unknown"}
    except Exception:
        # Return safe default if anything fails
        return {"connected": False, "mode": "error"}


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="discord",
    health_manager=_health_manager,
    custom_components={
        "bot_connected": lambda: (
            isinstance(app.state.bot, VoiceBot) and app.state.bot.is_ready
            if hasattr(app.state, "bot") and app.state.bot
            else False
        ),
        "bot_status": lambda: _get_bot_status(),
    },
    custom_dependencies={
        "stt": _check_stt_health,
        "orchestrator": _check_orchestrator_health,
    },
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())


@app.post("/api/v1/messages", response_model=MessageSendResponse)  # type: ignore[misc]
async def send_message(request: MessageSendRequest) -> MessageSendResponse:
    """Send text message to Discord channel."""
    # Access bot from app.state (app is module-level)
    bot = getattr(app.state, "bot", None)
    if not bot or not isinstance(bot, VoiceBot):
        raise HTTPException(
            status_code=503,
            detail="Discord bot not ready or not connected",
        )

    try:
        # For HTTP mode, we'll simulate the message sending
        # In a real implementation, this would connect to Discord and send the message
        logger.info(
            "discord.send_message_requested",
            channel_id=request.channel_id,
            content=request.content,
            correlation_id=request.correlation_id,
        )

        # NOTE: HTTP mode uses simulated message sending for testing/development.
        # For production HTTP-based message sending, implement Discord REST API client here.

        return MessageSendResponse(
            success=True,
            message_id="simulated_message_id",
            correlation_id=request.correlation_id,
        )

    except Exception as exc:
        logger.error("discord.send_message_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post(
    "/api/v1/notifications/transcript", response_model=TranscriptNotificationResponse
)  # type: ignore[misc]
async def handle_transcript(
    notification: TranscriptNotificationRequest,
) -> TranscriptNotificationResponse:
    """Handle transcript notification from orchestrator."""
    # This endpoint can work even if bot isn't ready (it's a notification endpoint)
    # But we check if the service is at least initialized
    bot = getattr(app.state, "bot", None)
    if bot is None:
        raise HTTPException(status_code=503, detail="Discord service not initialized")

    try:
        # Process transcript (this would trigger the voice assistant flow)
        logger.info(
            "discord.transcript_received",
            channel_id=notification.channel_id,
            user_id=notification.user_id,
            transcript=notification.transcript,
            correlation_id=notification.correlation_id,
        )

        # NOTE: This endpoint receives transcript notifications from the orchestrator.
        # In the current architecture, the orchestrator initiates processing after receiving
        # transcripts from the STT service. This endpoint serves as a notification/webhook.
        # Full processing flow: Discord → STT → Orchestrator → [this endpoint for notifications]
        # If bidirectional communication is needed, implement orchestrator client call here.

        return TranscriptNotificationResponse(
            success=True,
            correlation_id=notification.correlation_id,
        )

    except Exception as exc:
        logger.error("discord.transcript_handling_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/capabilities", response_model=CapabilitiesResponse)  # type: ignore[misc]
async def list_capabilities() -> CapabilitiesResponse:
    """List available Discord service capabilities."""
    return CapabilitiesResponse(
        service="discord",
        version="1.0.0",
        capabilities=[
            CapabilityInfo(
                name="send_message",
                description="Send a text message to Discord channel",
                parameters={
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "Discord channel ID",
                        },
                        "content": {"type": "string", "description": "Message content"},
                        "correlation_id": {
                            "type": "string",
                            "description": "Correlation ID for tracing",
                        },
                    },
                    "required": ["channel_id", "content"],
                },
            ),
            CapabilityInfo(
                name="transcript_notification",
                description="Receive transcript notifications from orchestrator",
                parameters={
                    "type": "object",
                    "properties": {
                        "transcript": {
                            "type": "string",
                            "description": "Transcript text",
                        },
                        "user_id": {"type": "string", "description": "Discord user ID"},
                        "channel_id": {
                            "type": "string",
                            "description": "Discord channel ID",
                        },
                        "correlation_id": {
                            "type": "string",
                            "description": "Correlation ID for tracing",
                        },
                    },
                    "required": ["transcript", "user_id", "channel_id"],
                },
            ),
        ],
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
