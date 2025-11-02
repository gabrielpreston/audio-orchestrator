"""Entrypoint for the Python Discord voice interface."""

from __future__ import annotations


from services.common.structured_logging import configure_logging

from .config import load_config


def main() -> None:
    config = load_config()
    configure_logging(
        config.logging.level,
        json_logs=config.logging.json_logs,
        service_name="discord",
    )

    # Run as HTTP API server
    import uvicorn

    from .app import app

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
