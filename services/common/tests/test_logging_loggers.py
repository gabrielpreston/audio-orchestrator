"""Tests for logger creation and binding functionality."""

import json
import sys
from collections.abc import Generator
from io import StringIO

import pytest
import structlog

from services.common.logging import bind_correlation_id, configure_logging, get_logger


class TestLoggerCreation:
    """Test logger creation functionality."""

    @pytest.fixture
    def isolated_structlog(self) -> Generator[None, None, None]:
        """Reset structlog configuration between tests."""
        original_config = structlog.get_config()
        yield
        structlog.configure(**original_config)

    @pytest.mark.unit
    def test_get_logger_basic(self, isolated_structlog):
        """Test basic logger creation."""
        configure_logging(level="INFO", json_logs=True)

        logger = get_logger("test_logger")

        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    @pytest.mark.unit
    def test_get_logger_with_correlation_id(self, isolated_structlog):
        """Test logger creation with correlation ID."""
        configure_logging(level="INFO", json_logs=True)

        correlation_id = "test-correlation-1234567890abcdef"
        logger = get_logger("test_logger", correlation_id=correlation_id)

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            logger.info("test message")

            log_output = captured_output.getvalue()
            log_data = json.loads(log_output.strip())

            assert log_data["correlation_id"] == correlation_id

        finally:
            sys.stdout = old_stdout

    @pytest.mark.unit
    def test_get_logger_with_service_name(self, isolated_structlog):
        """Test logger creation with service name."""
        configure_logging(level="INFO", json_logs=True)

        service_name = "test_service"
        logger = get_logger("test_logger", service_name=service_name)

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            logger.info("test message")

            log_output = captured_output.getvalue()
            log_data = json.loads(log_output.strip())

            assert log_data["service"] == service_name

        finally:
            sys.stdout = old_stdout

    @pytest.mark.unit
    def test_get_logger_with_both(self, isolated_structlog):
        """Test logger creation with both correlation ID and service name."""
        configure_logging(level="INFO", json_logs=True)

        correlation_id = "test-correlation-1234567890abcdef"
        service_name = "test_service"
        logger = get_logger(
            "test_logger", correlation_id=correlation_id, service_name=service_name
        )

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            logger.info("test message")

            log_output = captured_output.getvalue()
            log_data = json.loads(log_output.strip())

            assert log_data["correlation_id"] == correlation_id
            assert log_data["service"] == service_name

        finally:
            sys.stdout = old_stdout

    @pytest.mark.unit
    def test_get_logger_with_none_values(self, isolated_structlog):
        """Test logger creation with None values."""
        configure_logging(level="INFO", json_logs=True)

        logger = get_logger("test_logger", correlation_id=None, service_name=None)

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            logger.info("test message")

            log_output = captured_output.getvalue()
            log_data = json.loads(log_output.strip())

            assert "correlation_id" not in log_data
            assert "service" not in log_data

        finally:
            sys.stdout = old_stdout


class TestLoggerBinding:
    """Test logger binding functionality."""

    @pytest.fixture
    def isolated_structlog(self) -> Generator[None, None, None]:
        """Reset structlog configuration between tests."""
        original_config = structlog.get_config()
        yield
        structlog.configure(**original_config)

    @pytest.mark.unit
    def test_bind_correlation_id_with_id(self, isolated_structlog):
        """Test binding correlation ID to logger."""
        configure_logging(level="INFO", json_logs=True)

        base_logger = get_logger("test_logger")
        correlation_id = "test-correlation-1234567890abcdef"
        bound_logger = bind_correlation_id(base_logger, correlation_id)

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            bound_logger.info("test message")

            log_output = captured_output.getvalue()
            log_data = json.loads(log_output.strip())

            assert log_data["correlation_id"] == correlation_id

        finally:
            sys.stdout = old_stdout

    @pytest.mark.unit
    def test_bind_correlation_id_with_none(self, isolated_structlog):
        """Test binding correlation ID with None value."""
        configure_logging(level="INFO", json_logs=True)

        base_logger = get_logger("test_logger")
        bound_logger = bind_correlation_id(base_logger, None)

        assert bound_logger is base_logger

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            bound_logger.info("test message")

            log_output = captured_output.getvalue()
            log_data = json.loads(log_output.strip())

            assert "correlation_id" not in log_data

        finally:
            sys.stdout = old_stdout

    @pytest.mark.unit
    def test_multiple_bindings(self, isolated_structlog):
        """Test multiple field bindings."""
        configure_logging(level="INFO", json_logs=True)

        base_logger = get_logger("test_logger")

        correlation_id = "test-correlation-1234567890abcdef"
        bound_logger = bind_correlation_id(base_logger, correlation_id)
        bound_logger = bound_logger.bind(additional_field="test_value")

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            bound_logger.info("test message")

            log_output = captured_output.getvalue()
            log_data = json.loads(log_output.strip())

            assert log_data["correlation_id"] == correlation_id
            assert log_data["additional_field"] == "test_value"

        finally:
            sys.stdout = old_stdout

    @pytest.mark.unit
    def test_rebinding_same_field(self, isolated_structlog):
        """Test rebinding the same field."""
        configure_logging(level="INFO", json_logs=True)

        base_logger = get_logger("test_logger")

        first_id = "first-correlation-1234567890abcdef"
        bound_logger = bind_correlation_id(base_logger, first_id)

        second_id = "second-correlation-1234567890abcdef"
        bound_logger = bind_correlation_id(bound_logger, second_id)

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            bound_logger.info("test message")

            log_output = captured_output.getvalue()
            log_data = json.loads(log_output.strip())

            assert log_data["correlation_id"] == second_id

        finally:
            sys.stdout = old_stdout
