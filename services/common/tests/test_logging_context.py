"""Tests for correlation context manager functionality."""

import asyncio
import json
import threading
from collections.abc import Generator
from io import StringIO

import pytest
import structlog

from services.common.structured_logging import (
    configure_logging,
    correlation_context,
    get_logger,
)


class TestContextManager:
    """Test correlation context manager functionality."""

    @pytest.fixture
    def isolated_structlog(self) -> Generator[None, None, None]:
        """Reset structlog configuration between tests."""
        original_config = structlog.get_config()
        yield
        structlog.configure(**original_config)

    @pytest.mark.unit
    def test_context_manager_basic(self, isolated_structlog):
        """Test basic context manager functionality."""
        correlation_id = "test-correlation-1234567890abcdef"
        captured_output = StringIO()
        configure_logging(level="INFO", json_logs=True, stream=captured_output)

        with correlation_context(correlation_id) as logger:
            logger.info("test message")

        log_output = captured_output.getvalue()
        log_data = json.loads(log_output.strip())

        assert log_data["correlation_id"] == correlation_id

    @pytest.mark.unit
    def test_context_manager_none_correlation_id(self, isolated_structlog):
        """Test context manager with None correlation ID."""
        captured_output = StringIO()
        configure_logging(level="INFO", json_logs=True, stream=captured_output)

        with correlation_context(None) as logger:
            logger.info("test message")

        log_output = captured_output.getvalue()
        log_data = json.loads(log_output.strip())

        assert "correlation_id" not in log_data

    @pytest.mark.unit
    def test_context_manager_cleanup(self, isolated_structlog):
        """Test context manager cleanup after exit."""
        correlation_id = "test-correlation-1234567890abcdef"
        captured_output = StringIO()
        configure_logging(level="INFO", json_logs=True, stream=captured_output)

        with correlation_context(correlation_id) as logger:
            logger.info("inside context")

        logger = get_logger("test_logger")
        logger.info("outside context")

        log_output = captured_output.getvalue()
        log_lines = [
            line.strip() for line in log_output.strip().split("\n") if line.strip()
        ]

        # Parse each log line
        log_data_1 = json.loads(log_lines[0])
        log_data_2 = json.loads(log_lines[1])

        assert log_data_1["correlation_id"] == correlation_id
        assert "correlation_id" not in log_data_2

    @pytest.mark.unit
    def test_context_manager_exception_handling(self, isolated_structlog):
        """Test context manager cleanup on exception."""
        correlation_id = "test-correlation-1234567890abcdef"
        captured_output = StringIO()
        configure_logging(level="INFO", json_logs=True, stream=captured_output)

        with (
            pytest.raises(ValueError),
            correlation_context(correlation_id) as logger,
        ):
            logger.info("inside context")
            raise ValueError("test exception")

        logger = get_logger("test_logger")
        logger.info("outside context")

        log_output = captured_output.getvalue()
        log_lines = [
            line.strip() for line in log_output.strip().split("\n") if line.strip()
        ]

        # Parse each log line
        log_data_1 = json.loads(log_lines[0])
        log_data_2 = json.loads(log_lines[1])

        assert log_data_1["correlation_id"] == correlation_id
        assert "correlation_id" not in log_data_2

    @pytest.mark.unit
    def test_nested_contexts(self, isolated_structlog):
        """Test nested context managers."""
        outer_id = "outer-correlation-1234567890abcdef"
        inner_id = "inner-correlation-1234567890abcdef"
        captured_output = StringIO()
        configure_logging(level="INFO", json_logs=True, stream=captured_output)

        with correlation_context(outer_id) as outer_logger:
            outer_logger.info("outer context")

            with correlation_context(inner_id) as inner_logger:
                inner_logger.info("inner context")

            outer_logger.info("back to outer context")

        log_output = captured_output.getvalue()
        log_lines = [
            line.strip() for line in log_output.strip().split("\n") if line.strip()
        ]

        # Parse each log line
        log_data_1 = json.loads(log_lines[0])
        log_data_2 = json.loads(log_lines[1])
        log_data_3 = json.loads(log_lines[2])

        assert log_data_1["correlation_id"] == outer_id
        assert log_data_2["correlation_id"] == inner_id
        assert log_data_3["correlation_id"] == outer_id

    @pytest.mark.unit
    def test_concurrent_contexts(self, isolated_structlog):
        """Test concurrent context managers."""
        configure_logging(level="INFO", json_logs=True)

        def log_with_context(correlation_id: str, thread_id: int):
            with correlation_context(correlation_id) as logger:
                logger.info("thread %s message", thread_id)

        threads = []
        correlation_ids = [
            f"thread-{i}-correlation-1234567890abcdef" for i in range(10)
        ]

        for i, correlation_id in enumerate(correlation_ids):
            thread = threading.Thread(target=log_with_context, args=(correlation_id, i))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

    @pytest.mark.unit
    def test_async_context_manager(self, isolated_structlog):
        """Test context manager with asyncio."""
        correlation_id = "async-correlation-1234567890abcdef"
        captured_output = StringIO()
        configure_logging(level="INFO", json_logs=True, stream=captured_output)

        async def async_log_with_context(correlation_id: str):
            with correlation_context(correlation_id) as logger:
                logger.info("async message")
                await asyncio.sleep(0.01)
                logger.info("async message after sleep")

        async def run_async_test():
            await async_log_with_context(correlation_id)

            log_output = captured_output.getvalue()
            log_lines = [
                line.strip() for line in log_output.strip().split("\n") if line.strip()
            ]

            assert len(log_lines) == 2
            log_data_1 = json.loads(log_lines[0])
            log_data_2 = json.loads(log_lines[1])
            assert log_data_1["correlation_id"] == correlation_id
            assert log_data_2["correlation_id"] == correlation_id

        asyncio.run(run_async_test())

    @pytest.mark.unit
    def test_context_manager_log_output(self, isolated_structlog):
        """Test that logs inside context have correlation ID."""
        correlation_id = "test-correlation-1234567890abcdef"
        captured_output = StringIO()
        configure_logging(level="INFO", json_logs=True, stream=captured_output)

        with correlation_context(correlation_id) as logger:
            logger.info("first message")
            logger.warning("second message")
            logger.error("third message")

        log_output = captured_output.getvalue()
        log_lines = [
            line.strip() for line in log_output.strip().split("\n") if line.strip()
        ]

        assert len(log_lines) == 3
        for line in log_lines:
            log_data = json.loads(line)
            assert log_data["correlation_id"] == correlation_id

    @pytest.mark.unit
    def test_context_manager_multiple_log_calls(self, isolated_structlog):
        """Test multiple log calls within context."""
        correlation_id = "test-correlation-1234567890abcdef"
        captured_output = StringIO()
        configure_logging(level="INFO", json_logs=True, stream=captured_output)

        with correlation_context(correlation_id) as logger:
            for i in range(10):
                logger.info("message %s", i)

        log_output = captured_output.getvalue()
        log_lines = [
            line.strip() for line in log_output.strip().split("\n") if line.strip()
        ]

        assert len(log_lines) == 10
        for line in log_lines:
            log_data = json.loads(line)
            assert log_data["correlation_id"] == correlation_id
