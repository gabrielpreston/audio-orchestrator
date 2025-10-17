"""Tests for logging configuration functionality."""

import json
import logging
from collections.abc import Generator
from io import StringIO

import pytest
import structlog

from services.common.logging import configure_logging, get_logger


class TestLoggingConfiguration:
    """Test logging configuration functionality."""

    @pytest.fixture
    def isolated_structlog(self) -> Generator[None, None, None]:
        """Reset structlog configuration between tests."""
        original_config = structlog.get_config()
        yield
        structlog.configure(**original_config)

    @pytest.mark.unit
    def test_configure_logging_basic(self, isolated_structlog):
        """Test basic logging configuration."""
        captured_output = StringIO()
        configure_logging(
            level="INFO",
            json_logs=True,
            service_name="test_service",
            stream=captured_output,
        )

        logger = get_logger("test_logger")
        logger.info("test message", extra_field="test_value")

        log_output = captured_output.getvalue()
        log_data = json.loads(log_output.strip())

        assert log_data["event"] == "test message"
        assert log_data["extra_field"] == "test_value"
        assert log_data["service"] == "test_service"
        assert "timestamp" in log_data
        assert "level" in log_data

    @pytest.mark.unit
    def test_configure_logging_console_output(self, isolated_structlog):
        """Test console output configuration."""
        captured_output = StringIO()
        configure_logging(
            level="INFO",
            json_logs=False,
            service_name="test_service",
            stream=captured_output,
        )

        logger = get_logger("test_logger")
        logger.info("test message", extra_field="test_value")

        log_output = captured_output.getvalue()

        assert "test message" in log_output
        assert "test_service" in log_output
        assert "test_value" in log_output

        with pytest.raises(json.JSONDecodeError):
            json.loads(log_output.strip())

    @pytest.mark.unit
    def test_configure_logging_log_levels(self, isolated_structlog):
        """Test different log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            captured_output = StringIO()
            configure_logging(level=level, json_logs=True, stream=captured_output)

            logger = get_logger("test_logger")
            logger.debug("debug message")
            logger.info("info message")
            logger.warning("warning message")
            logger.error("error message")

            log_output = captured_output.getvalue()
            log_lines = [line for line in log_output.strip().split("\n") if line]

            if level == "DEBUG":
                assert len(log_lines) == 4
            elif level == "INFO":
                assert len(log_lines) == 3
            elif level == "WARNING":
                assert len(log_lines) == 2
            elif level == "ERROR":
                assert len(log_lines) == 1

    @pytest.mark.unit
    def test_configure_logging_service_name_injection(self, isolated_structlog):
        """Test service name injection in logs."""
        captured_output = StringIO()
        configure_logging(
            level="INFO",
            json_logs=True,
            service_name="test_service",
            stream=captured_output,
        )

        logger = get_logger("test_logger")
        logger.info("test message")

        log_output = captured_output.getvalue()
        log_data = json.loads(log_output.strip())

        assert log_data["service"] == "test_service"

    @pytest.mark.unit
    def test_configure_logging_no_service_name(self, isolated_structlog):
        """Test logging without service name."""
        captured_output = StringIO()
        configure_logging(
            level="INFO", json_logs=True, service_name=None, stream=captured_output
        )

        logger = get_logger("test_logger")
        logger.info("test message")

        log_output = captured_output.getvalue()
        log_data = json.loads(log_output.strip())

        assert "service" not in log_data

    @pytest.mark.unit
    def test_configure_logging_structlog_processors(self, isolated_structlog):
        """Test that all structlog processors are configured."""
        configure_logging(level="INFO", json_logs=True, service_name="test_service")

        config = structlog.get_config()

        assert "processors" in config
        processors = config["processors"]
        assert len(processors) > 0

        assert "wrapper_class" in config
        assert config["wrapper_class"] is not None

    @pytest.mark.unit
    def test_configure_logging_stdlib_integration(self, isolated_structlog):
        """Test stdlib logging integration."""
        configure_logging(level="INFO", json_logs=True, service_name="test_service")

        stdlib_logger = logging.getLogger("test_stdlib")
        stdlib_logger.info("stdlib message")

        assert stdlib_logger.isEnabledFor(logging.INFO)
