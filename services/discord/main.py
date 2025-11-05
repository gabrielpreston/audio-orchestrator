"""Entrypoint for the Python Discord voice interface."""

from __future__ import annotations

from services.common.config import LoggingConfig, get_service_preset
from services.common.structured_logging import configure_logging

# Load logging configuration from preset
_config_preset = get_service_preset("discord")
_logging_config = LoggingConfig(**_config_preset["logging"])

# Configure logging BEFORE importing app to ensure structured JSON logging
# is set up before uvicorn initializes
configure_logging(
    _logging_config.level,
    json_logs=_logging_config.json_logs,
    service_name="discord",
)


def main() -> None:
    """Main entrypoint for the Discord service."""
    # Import app AFTER logging is configured
    import uvicorn

    from .app import app

    # Full config still loaded in app.py startup handler
    # This import is here to ensure app module is available
    # (app.py will load config independently in _startup())

    # Prevent uvicorn from resetting our logging configuration
    # We've already configured structured JSON logging in configure_logging()
    # Setting log_config=None tells uvicorn not to configure logging itself
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_config=None,  # Don't let uvicorn configure logging - we handle it ourselves
    )


if __name__ == "__main__":
    main()
