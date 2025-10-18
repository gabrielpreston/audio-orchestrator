"""Tests for sampling and rate limit helpers in services.common.logging."""

from __future__ import annotations

import pytest

from services.common import logging as clog


@pytest.mark.unit
def test_should_sample_every_n() -> None:
    # Reset counters for isolation
    clog._SAMPLE_COUNTERS.clear()

    key = "unit.sample"
    every = 3
    results = [clog.should_sample(key, every) for _ in range(6)]
    # True on 3rd and 6th calls
    assert results == [False, False, True, False, False, True]


@pytest.mark.unit
def test_should_sample_always_when_n_le_1() -> None:
    clog._SAMPLE_COUNTERS.clear()
    assert clog.should_sample("k", 1) is True
    assert clog.should_sample("k", 0) is True


@pytest.mark.unit
def test_should_rate_limit_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    # Reset state
    clog._RATE_LIMIT_LAST.clear()

    now = 1_000_000.0

    def fake_time() -> float:
        return nonlocal_time[0]

    nonlocal_time = [now]
    monkeypatch.setattr(clog, "time", type("T", (), {"time": staticmethod(fake_time)}))

    key = "unit.rate"
    interval = 1.0

    # First call should pass
    assert clog.should_rate_limit(key, interval) is True
    # Immediate second call should be blocked
    assert clog.should_rate_limit(key, interval) is False
    # Advance time beyond interval
    nonlocal_time[0] = now + 1.01
    assert clog.should_rate_limit(key, interval) is True
