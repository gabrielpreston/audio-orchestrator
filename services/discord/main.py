"""Entrypoint for the Python Discord voice interface."""

from __future__ import annotations


from services.common.structured_logging import configure_logging

from .config import load_config


def main() -> None:
    config = load_config()
    configure_logging(
        config.telemetry.log_level,
        json_logs=config.telemetry.log_json,
        service_name="discord",
    )

    # Run as HTTP API server
    import uvicorn

    from .app import app

    uvicorn.run(app, host="0.0.0.0", port=8001)


if __name__ == "__main__":
    main()
