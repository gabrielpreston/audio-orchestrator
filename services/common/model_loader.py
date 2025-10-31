"""Unified background model loader with cache-first + download fallback.

This module provides a standardized pattern for model loading across all services:
- Cache-first: Try loading from local cache/storage first
- Download fallback: If cache miss, download from source
- Background loading: Non-blocking startup
- Graceful API handling: Services can check state and respond appropriately
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any


def _get_force_download_from_env(loader_name: str, explicit_value: bool | None) -> bool:
    """Get force_download value from env vars or explicit parameter.

    Checks FORCE_MODEL_DOWNLOAD_{LOADER_NAME_UPPERCASE} first, then falls back to
    FORCE_MODEL_DOWNLOAD global env var.

    Args:
        loader_name: Name of the loader (e.g., "whisper_model", "flan_t5")
        explicit_value: Explicit boolean value (None to check env vars)

    Returns:
        True if force download is enabled, False otherwise
    """
    if explicit_value is not None:
        return explicit_value
    # Check service-specific first (e.g., FORCE_MODEL_DOWNLOAD_WHISPER_MODEL)
    service_key = f"FORCE_MODEL_DOWNLOAD_{loader_name.upper()}"
    global_key = "FORCE_MODEL_DOWNLOAD"
    service_val = os.getenv(service_key, "").lower()
    global_val = os.getenv(global_key, "false").lower()
    return service_val in ("true", "1", "yes") or global_val in ("true", "1", "yes")


class BackgroundModelLoader:
    """Unified background model loader with cache-first + download fallback.

    Standardizes model loading pattern across all services:
    - Cache-first: Try loading from local cache/storage first
    - Download fallback: If cache miss, download from source
    - Background loading: Non-blocking startup
    - Graceful API handling: Services can check state and respond appropriately

    Supports multiple patterns:
    - Functions that return model object (most common)
    - Side-effect functions that load into memory (Bark's preload_models())
    - Functions that return tuples/dicts (FLAN's model + tokenizer)
    """

    def __init__(
        self,
        cache_loader_func: Callable[[], Any] | Callable[[], Awaitable[Any]] | None,
        download_loader_func: Callable[[], Any] | Callable[[], Awaitable[Any]],
        logger: Any,
        *,
        loader_name: str = "model",
        timeout_seconds: float | None = None,
        enable_background_load: bool = True,
        return_model_key: str | None = None,  # For dict returns, key to extract model
        is_side_effect: bool = False,  # For functions that don't return model
        force_download: bool | None = None,  # Force download, None = check env vars
    ) -> None:
        """Initialize model loader with cache-first + download fallback.

        Args:
            cache_loader_func: Function to load from cache (returns model or None)
                               If None, skip cache step
            download_loader_func: Function to download/load model (fallback)
                                 For side-effect functions, returns success indicator
            logger: Structured logger instance
            loader_name: Name for logging (e.g., "bark_models", "whisper_model")
            timeout_seconds: Optional timeout for lazy loading (None = no timeout)
            enable_background_load: If True, start loading in background at initialize()
            return_model_key: If loader returns dict, key to extract model from
            is_side_effect: If True, loader function doesn't return model (e.g., Bark)
            force_download: Force download flag. If None, checks environment variables.
            heartbeat_interval: Seconds between heartbeat logs during downloads (default 10.0)
        """
        self._cache_loader_func = cache_loader_func
        self._download_loader_func = download_loader_func
        self._logger = logger
        self._loader_name = loader_name
        self._timeout = timeout_seconds
        self._enable_background_load = enable_background_load
        self._return_model_key = return_model_key
        self._is_side_effect = is_side_effect

        # Determine force_download value from explicit parameter or env vars
        self._force_download = _get_force_download_from_env(loader_name, force_download)

        # State management
        self._model: Any | None = None
        self._is_loading = False
        self._loading_event = asyncio.Event()
        self._loading_lock = asyncio.Lock()
        self._loading_task: asyncio.Task[None] | None = None
        self._load_error: Exception | None = None
        self._load_start_time: float | None = None
        self._load_duration: float | None = None
        self._load_method: str | None = None  # "cache" or "download"
        self._heartbeat_interval: float = (
            10.0  # Log heartbeat every N seconds during downloads
        )
        self._heartbeat_task: asyncio.Task[None] | None = None

        self._logger.debug(
            "model_loader.initialized",
            loader_name=loader_name,
            enable_background_load=enable_background_load,
            is_side_effect=is_side_effect,
            force_download=self._force_download,
        )

        if self._force_download:
            self._logger.info(
                "model_loader.force_download_enabled",
                loader_name=loader_name,
            )

    async def initialize(self) -> None:
        """Start background loading (non-blocking).

        Attempts cache-first load, then download fallback if cache fails.
        """
        if not self._enable_background_load:
            self._logger.debug(
                "model_loader.background_disabled", loader_name=self._loader_name
            )
            return

        # Prevent multiple initializations
        if self._loading_task is not None:
            self._logger.warning(
                "model_loader.already_initialized", loader_name=self._loader_name
            )
            return

        # Start background loading task
        self._is_loading = True
        self._loading_task = asyncio.create_task(self._background_load())
        self._logger.info(
            "model_loader.background_load_started", loader_name=self._loader_name
        )

    async def _background_load(self) -> None:
        """Background loading task (cache-first + download fallback)."""
        self._load_start_time = time.time()
        heartbeat_started = False

        try:
            # Skip cache if force_download is enabled
            if self._force_download:
                self._logger.info(
                    "model_loader.force_download_skipping_cache",
                    loader_name=self._loader_name,
                    message="Force download enabled, skipping cache check",
                )
                # Start heartbeat for force download (will download)
                self._heartbeat_task = asyncio.create_task(self._heartbeat_logger())
                heartbeat_started = True
            elif self._cache_loader_func is not None:
                # Try cache-first load if available
                cache_start = time.time()
                self._logger.info(
                    "model_loader.cache_load_attempt",
                    loader_name=self._loader_name,
                    phase="cache_check",
                )
                cache_result = await self._execute_loader(self._cache_loader_func)
                cache_duration = time.time() - cache_start

                if cache_result is not None:
                    # Cache hit - no heartbeat needed for quick cache loads
                    if heartbeat_started and self._heartbeat_task:
                        self._heartbeat_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await self._heartbeat_task

                    self._model = cache_result
                    self._load_method = "cache"
                    self._load_duration = time.time() - self._load_start_time
                    self._is_loading = False
                    self._loading_event.set()
                    self._logger.info(
                        "model_loader.cache_load_success",
                        loader_name=self._loader_name,
                        cache_check_duration_ms=round(cache_duration * 1000, 2),
                        total_duration_ms=round(self._load_duration * 1000, 2),
                        phase="cache_load_complete",
                    )
                    return

                self._logger.info(
                    "model_loader.cache_miss",
                    loader_name=self._loader_name,
                    cache_check_duration_ms=round(cache_duration * 1000, 2),
                    phase="cache_miss",
                )

            # Cache miss, no cache function, or force_download - try download
            download_start = time.time()

            # Build enhanced download message based on loader name
            download_message = f"Starting download for {self._loader_name}"
            if self._loader_name == "bark_models":
                download_message = (
                    "Starting download for Bark models (text, coarse, fine, codec)"
                )
            elif self._loader_name == "whisper_model":
                download_message = "Starting download for Whisper STT model"
            elif self._loader_name == "flan_t5":
                download_message = "Starting download for FLAN-T5 model and tokenizer"
            elif self._loader_name == "toxicity_model":
                download_message = "Starting download for toxicity detection model"
            elif self._loader_name == "metricgan":
                download_message = (
                    "Starting download for MetricGAN+ audio enhancement model"
                )

            # Try to determine download directory from common environment variables
            # This helps users understand where models are being stored
            download_directory: str | None = None
            if self._loader_name == "bark_models":
                # Bark uses HF_HOME or HOME/.cache for its models
                download_directory = os.getenv("HF_HOME") or (
                    os.getenv("HOME", "/app") + "/.cache"
                )
            elif self._loader_name in ("flan_t5", "toxicity_model"):
                # Transformers models use HF_HOME or TRANSFORMERS_CACHE
                download_directory = (
                    os.getenv("HF_HOME")
                    or os.getenv("TRANSFORMERS_CACHE")
                    or "/app/models"
                )
            elif self._loader_name == "whisper_model":
                # faster-whisper uses model_path from config, fallback to /app/models
                # Note: We can't access config here, so use environment or default
                download_directory = (
                    os.getenv("FASTER_WHISPER_MODEL_PATH") or "/app/models"
                )
            elif self._loader_name == "metricgan":
                download_directory = (
                    os.getenv("METRICGAN_MODEL_SAVEDIR") or "/app/models/metricgan-plus"
                )

            log_data: dict[str, Any] = {
                "loader_name": self._loader_name,
                "phase": "download_start",
                "message": download_message,
            }
            if download_directory:
                log_data["download_directory"] = download_directory

            self._logger.info("model_loader.download_load_attempt", **log_data)

            # Start heartbeat for download if not already started
            if not heartbeat_started:
                self._heartbeat_task = asyncio.create_task(self._heartbeat_logger())

            download_result = await self._execute_loader(self._download_loader_func)
            download_duration = time.time() - download_start

            # Cancel heartbeat now that download is complete
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._heartbeat_task

            self._model = download_result
            self._load_method = "download"
            self._load_duration = time.time() - self._load_start_time
            self._is_loading = False
            self._loading_event.set()
            self._logger.info(
                "model_loader.download_load_success",
                loader_name=self._loader_name,
                download_duration_ms=round(download_duration * 1000, 2),
                total_duration_ms=round(self._load_duration * 1000, 2),
                phase="download_complete",
            )

        except Exception as exc:
            # Cancel heartbeat on error
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._heartbeat_task

            self._load_error = exc
            self._is_loading = False
            self._loading_event.set()
            self._model = None
            self._load_duration = (
                time.time() - self._load_start_time if self._load_start_time else None
            )
            self._logger.exception(
                "model_loader.background_load_failed",
                loader_name=self._loader_name,
                error=str(exc),
                error_type=type(exc).__name__,
                duration_ms=round(self._load_duration * 1000, 2)
                if self._load_duration
                else None,
                phase="background_load_failed",
            )

    async def _heartbeat_logger(self) -> None:
        """Periodic heartbeat logging during model loading.

        Logs progress updates every heartbeat_interval seconds while loading is in progress.
        Only runs during downloads (not cache loads) to avoid noise for quick cache hits.
        """
        while self._is_loading:
            if self._load_start_time:
                elapsed = time.time() - self._load_start_time
                elapsed_minutes = int(elapsed // 60)
                elapsed_seconds = int(elapsed % 60)

                self._logger.info(
                    "model_loader.loading_heartbeat",
                    loader_name=self._loader_name,
                    elapsed_seconds=round(elapsed, 1),
                    elapsed_display=f"{elapsed_minutes}m {elapsed_seconds}s",
                    phase="download_in_progress",
                )

            try:
                await asyncio.sleep(self._heartbeat_interval)
            except asyncio.CancelledError:
                break

    async def _execute_loader(
        self, loader_func: Callable[[], Any] | Callable[[], Awaitable[Any]]
    ) -> Any:
        """Execute loader function (sync or async)."""
        if asyncio.iscoroutinefunction(loader_func):
            return await loader_func()
        else:
            return await asyncio.to_thread(loader_func)

    def is_loaded(self) -> bool:
        """Check if models are currently loaded."""
        if self._is_side_effect:
            # For side-effect functions, check if model was set (success indicator)
            return self._model is not None
        return self._model is not None

    def is_loading(self) -> bool:
        """Check if models are currently loading.

        Returns True if background or lazy loading is in progress.
        """
        return self._is_loading

    def get_status(self) -> dict[str, Any]:
        """Get detailed loading status for API responses.

        Returns dict with: loaded, loading, error, method, duration_ms fields.
        """
        status: dict[str, Any] = {
            "loaded": self.is_loaded(),
            "loading": self.is_loading(),
        }
        if self._load_error:
            status["error"] = str(self._load_error)
            status["error_type"] = type(self._load_error).__name__
        if self._load_method:
            status["method"] = self._load_method
        if self._load_duration:
            status["duration_ms"] = round(self._load_duration * 1000, 2)
        if self._load_start_time and self._is_loading:
            elapsed = time.time() - self._load_start_time
            status["elapsed_ms"] = round(elapsed * 1000, 2)
        return status

    def get_model(self) -> Any | None:
        """Get loaded model instance.

        Returns model if loaded, None otherwise.
        For tuple/dict returns, extracts appropriately based on return_model_key.
        """
        if self._return_model_key and isinstance(self._model, dict):
            return self._model.get(self._return_model_key)
        return self._model

    def is_force_download(self) -> bool:
        """Check if force download is enabled.

        Returns True if force download is enabled, False otherwise.
        """
        return self._force_download

    async def ensure_loaded(self, timeout: float | None = None) -> bool:
        """Ensure models are loaded (wait if loading, load if not started).

        Implements cache-first + download fallback pattern.
        Returns True if models loaded successfully, False otherwise.

        Args:
            timeout: Optional timeout for lazy loading (uses instance timeout if None)
        """
        # Use instance timeout if not provided
        if timeout is None:
            timeout = self._timeout

        # If already loaded, return immediately
        if self.is_loaded():
            return True

        # If currently loading, wait for completion
        if self.is_loading():
            try:
                if timeout:
                    await asyncio.wait_for(self._loading_event.wait(), timeout=timeout)
                else:
                    await self._loading_event.wait()
                return self.is_loaded()
            except TimeoutError:
                self._logger.warning(
                    "model_loader.lazy_load_timeout",
                    loader_name=self._loader_name,
                    timeout=timeout,
                )
                return False

        # Not loading and not loaded - trigger lazy load
        async with self._loading_lock:
            # Double-check after acquiring lock
            if self.is_loaded():
                return True
            if self.is_loading():
                # Another request started loading, wait for it
                try:
                    if timeout:
                        await asyncio.wait_for(
                            self._loading_event.wait(), timeout=timeout
                        )
                    else:
                        await self._loading_event.wait()
                    return self.is_loaded()
                except TimeoutError:
                    return False

            # Start lazy load with cache-first + download pattern
            self._is_loading = True
            self._loading_event.clear()
            self._load_start_time = time.time()
            heartbeat_started = False

            try:
                # Skip cache if force_download is enabled
                if self._force_download:
                    self._logger.info(
                        "model_loader.lazy_force_download_skipping_cache",
                        loader_name=self._loader_name,
                        phase="lazy_force_download",
                    )
                    # Start heartbeat for force download
                    self._heartbeat_task = asyncio.create_task(self._heartbeat_logger())
                    heartbeat_started = True
                elif self._cache_loader_func is not None:
                    # Try cache-first
                    cache_start = time.time()
                    self._logger.info(
                        "model_loader.lazy_cache_attempt",
                        loader_name=self._loader_name,
                        phase="lazy_cache_check",
                    )
                    cache_result = await self._execute_loader(self._cache_loader_func)
                    cache_duration = time.time() - cache_start

                    if cache_result is not None:
                        # Cache hit - cancel heartbeat if started (shouldn't have)
                        if heartbeat_started and self._heartbeat_task:
                            self._heartbeat_task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await self._heartbeat_task

                        self._model = cache_result
                        self._load_method = "cache"
                        self._load_duration = time.time() - self._load_start_time
                        self._is_loading = False
                        self._loading_event.set()
                        self._logger.info(
                            "model_loader.lazy_cache_success",
                            loader_name=self._loader_name,
                            cache_check_duration_ms=round(cache_duration * 1000, 2),
                            total_duration_ms=round(self._load_duration * 1000, 2),
                            phase="lazy_cache_complete",
                        )
                        return True

                # Cache miss, no cache function, or force_download - try download
                download_start = time.time()
                self._logger.info(
                    "model_loader.lazy_download_attempt",
                    loader_name=self._loader_name,
                    phase="lazy_download_start",
                )

                # Start heartbeat for download if not already started
                if not heartbeat_started:
                    self._heartbeat_task = asyncio.create_task(self._heartbeat_logger())

                download_result = await self._execute_loader(self._download_loader_func)
                download_duration = time.time() - download_start

                # Cancel heartbeat now that download is complete
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await self._heartbeat_task

                self._model = download_result
                self._load_method = "download"
                self._load_duration = time.time() - self._load_start_time
                self._is_loading = False
                self._loading_event.set()
                self._logger.info(
                    "model_loader.lazy_download_success",
                    loader_name=self._loader_name,
                    download_duration_ms=round(download_duration * 1000, 2),
                    total_duration_ms=round(self._load_duration * 1000, 2),
                    phase="lazy_download_complete",
                )
                return True

            except Exception as exc:
                # Cancel heartbeat on error
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await self._heartbeat_task

                self._load_error = exc
                self._is_loading = False
                self._loading_event.set()
                self._model = None
                self._load_duration = (
                    time.time() - self._load_start_time
                    if self._load_start_time
                    else None
                )
                self._logger.exception(
                    "model_loader.lazy_load_failed",
                    loader_name=self._loader_name,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    duration_ms=round(self._load_duration * 1000, 2)
                    if self._load_duration
                    else None,
                    phase="lazy_load_failed",
                )
                return False

    async def cleanup(self) -> None:
        """Cleanup resources and cancel background tasks."""
        # Cancel heartbeat if running
        if self._heartbeat_task is not None:
            if not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._heartbeat_task
            self._heartbeat_task = None

        if self._loading_task is not None:
            if not self._loading_task.done():
                self._loading_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._loading_task
            self._loading_task = None

        self._is_loading = False
        self._loading_event.set()
        self._logger.debug(
            "model_loader.cleanup_completed", loader_name=self._loader_name
        )


__all__ = ["BackgroundModelLoader"]
