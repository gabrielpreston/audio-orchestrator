"""Tests for correlation ID performance and concurrency."""

import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from services.common.correlation import (
    generate_discord_correlation_id,
    parse_correlation_id,
    validate_correlation_id,
)


class TestCorrelationIDPerformance:
    """Test correlation ID performance and concurrency."""

    @pytest.mark.performance
    def test_id_generation_speed(self):
        """Test correlation ID generation speed."""
        start_time = time.time()

        for _ in range(10000):
            generate_discord_correlation_id(123456)

        end_time = time.time()
        duration = end_time - start_time

        assert duration < 5.0
        print(f"Generated 10,000 IDs in {duration:.3f} seconds")

    @pytest.mark.performance
    def test_validation_speed(self):
        """Test correlation ID validation speed."""
        correlation_ids = [
            "discord-123456-1704067200000-12345678",
            "stt-1704067200000-12345678",
            "tts-1704067200000-12345678",
        ]

        start_time = time.time()

        for _ in range(10000):
            for correlation_id in correlation_ids:
                is_valid, _ = validate_correlation_id(correlation_id)
                assert is_valid

        end_time = time.time()
        duration = end_time - start_time

        assert duration < 3.0
        print(f"Validated 10,000 IDs in {duration:.3f} seconds")

    @pytest.mark.performance
    def test_parsing_speed(self):
        """Test correlation ID parsing speed."""
        correlation_ids = [
            "discord-123456-1704067200000-12345678",
            "stt-1704067200000-12345678",
            "tts-1704067200000-12345678",
            "orchestrator-123456-1704067200000-12345678",
            "mcp-client-tool-source",
            "manual-service-1704067200000-12345678",
        ]

        start_time = time.time()

        for _ in range(10000):
            for correlation_id in correlation_ids:
                parsed = parse_correlation_id(correlation_id)
                assert parsed["service"] != "unknown"

        end_time = time.time()
        duration = end_time - start_time

        assert duration < 3.0
        print(f"Parsed 10,000 IDs in {duration:.3f} seconds")

    @pytest.mark.performance
    def test_uuid_collision_rate(self):
        """Test UUID collision rate with large number of IDs."""
        ids = set()
        collision_count = 0

        for _ in range(1000000):
            id_ = generate_discord_correlation_id(123456)
            if id_ in ids:
                collision_count += 1
            ids.add(id_)

        assert collision_count == 0, f"Found {collision_count} collisions in 1M IDs"
        assert len(ids) == 1000000

    @pytest.mark.concurrent
    def test_concurrent_generation(self):
        """Test concurrent correlation ID generation."""

        def generate_ids():
            ids = []
            for _ in range(100):
                ids.append(generate_discord_correlation_id(123456))
            return ids

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(generate_ids) for _ in range(100)]
            all_ids = []
            for future in futures:
                all_ids.extend(future.result())

        assert len(set(all_ids)) == len(all_ids)
        assert len(all_ids) == 10000

    @pytest.mark.concurrent
    def test_concurrent_validation(self):
        """Test concurrent correlation ID validation."""
        correlation_ids = [
            "discord-123456-1704067200000-12345678",
            "stt-1704067200000-12345678",
            "tts-1704067200000-12345678",
        ]

        def validate_ids():
            results = []
            for correlation_id in correlation_ids:
                is_valid, _ = validate_correlation_id(correlation_id)
                results.append(is_valid)
            return results

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(validate_ids) for _ in range(100)]
            all_results = []
            for future in futures:
                all_results.extend(future.result())

        assert all(all_results)
        assert len(all_results) == 300

    @pytest.mark.concurrent
    def test_concurrent_parsing(self):
        """Test concurrent correlation ID parsing."""
        correlation_ids = [
            "discord-123456-1704067200000-12345678",
            "stt-1704067200000-12345678",
            "tts-1704067200000-12345678",
            "orchestrator-123456-1704067200000-12345678",
            "mcp-client-tool-source",
            "manual-service-1704067200000-12345678",
        ]

        def parse_ids():
            results = []
            for correlation_id in correlation_ids:
                parsed = parse_correlation_id(correlation_id)
                results.append(parsed["service"])
            return results

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(parse_ids) for _ in range(100)]
            all_results = []
            for future in futures:
                all_results.extend(future.result())

        expected_services = ["discord", "stt", "tts", "orchestrator", "mcp", "manual"]
        for i in range(0, len(all_results), 6):
            thread_results = all_results[i : i + 6]
            assert thread_results == expected_services
