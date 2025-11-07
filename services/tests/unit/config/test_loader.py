"""Unit tests for configuration loader environment variable parsing."""

import os
from unittest.mock import patch

import pytest

from services.common.config.loader import _get_env_overrides


class TestWakeConfigParsing:
    """Test wake configuration environment variable parsing."""

    @pytest.mark.unit
    def test_wake_phrases_parsing(self):
        """Test WAKE_PHRASES environment variable parsing."""
        with patch.dict(os.environ, {"WAKE_PHRASES": "hey atlas,ok atlas,atlas"}):
            overrides = _get_env_overrides()
            assert overrides["wake"]["wake_phrases"] == [
                "hey atlas",
                "ok atlas",
                "atlas",
            ]

    @pytest.mark.unit
    def test_wake_phrases_empty_string(self):
        """Test WAKE_PHRASES with empty string results in empty list."""
        with patch.dict(os.environ, {"WAKE_PHRASES": ""}):
            overrides = _get_env_overrides()
            assert overrides["wake"]["wake_phrases"] == []

    @pytest.mark.unit
    def test_wake_phrases_with_spaces(self):
        """Test WAKE_PHRASES with spaces around commas."""
        with patch.dict(os.environ, {"WAKE_PHRASES": "hey atlas , ok atlas , atlas"}):
            overrides = _get_env_overrides()
            assert overrides["wake"]["wake_phrases"] == [
                "hey atlas",
                "ok atlas",
                "atlas",
            ]

    @pytest.mark.unit
    def test_wake_threshold_valid(self):
        """Test WAKE_THRESHOLD with valid float value."""
        with patch.dict(os.environ, {"WAKE_THRESHOLD": "0.7"}):
            overrides = _get_env_overrides()
            assert overrides["wake"]["activation_threshold"] == 0.7

    @pytest.mark.unit
    def test_wake_threshold_boundary_min(self):
        """Test WAKE_THRESHOLD with minimum valid value."""
        with patch.dict(os.environ, {"WAKE_THRESHOLD": "0.0"}):
            overrides = _get_env_overrides()
            assert overrides["wake"]["activation_threshold"] == 0.0

    @pytest.mark.unit
    def test_wake_threshold_boundary_max(self):
        """Test WAKE_THRESHOLD with maximum valid value."""
        with patch.dict(os.environ, {"WAKE_THRESHOLD": "1.0"}):
            overrides = _get_env_overrides()
            assert overrides["wake"]["activation_threshold"] == 1.0

    @pytest.mark.unit
    def test_wake_threshold_out_of_range_low(self):
        """Test WAKE_THRESHOLD with value below 0.0."""
        with patch.dict(os.environ, {"WAKE_THRESHOLD": "-0.1"}):
            overrides = _get_env_overrides()
            # Should not be set in overrides (invalid value logged but not set)
            assert "activation_threshold" not in overrides.get("wake", {})

    @pytest.mark.unit
    def test_wake_threshold_out_of_range_high(self):
        """Test WAKE_THRESHOLD with value above 1.0."""
        with patch.dict(os.environ, {"WAKE_THRESHOLD": "1.5"}):
            overrides = _get_env_overrides()
            # Should not be set in overrides (invalid value logged but not set)
            assert "activation_threshold" not in overrides.get("wake", {})

    @pytest.mark.unit
    def test_wake_threshold_invalid_string(self):
        """Test WAKE_THRESHOLD with invalid string value."""
        with patch.dict(os.environ, {"WAKE_THRESHOLD": "not-a-number"}):
            overrides = _get_env_overrides()
            # Should not be set in overrides (invalid value logged but not set)
            assert "activation_threshold" not in overrides.get("wake", {})

    @pytest.mark.unit
    def test_wake_sample_rate_valid(self):
        """Test WAKE_SAMPLE_RATE with valid integer value."""
        with patch.dict(os.environ, {"WAKE_SAMPLE_RATE": "22050"}):
            overrides = _get_env_overrides()
            assert overrides["wake"]["target_sample_rate_hz"] == 22050

    @pytest.mark.unit
    def test_wake_sample_rate_invalid(self):
        """Test WAKE_SAMPLE_RATE with invalid value."""
        with patch.dict(os.environ, {"WAKE_SAMPLE_RATE": "not-a-number"}):
            overrides = _get_env_overrides()
            # Should not be set in overrides (invalid value logged but not set)
            assert "target_sample_rate_hz" not in overrides.get("wake", {})

    @pytest.mark.unit
    def test_wake_model_paths_parsing(self):
        """Test WAKE_MODEL_PATHS with valid paths."""
        with patch.dict(
            os.environ,
            {"WAKE_MODEL_PATHS": "/path/to/model1.onnx,/path/to/model2.onnx"},
        ):
            overrides = _get_env_overrides()
            assert overrides["wake"]["model_paths"] == [
                "/path/to/model1.onnx",
                "/path/to/model2.onnx",
            ]

    @pytest.mark.unit
    def test_wake_model_paths_empty_string(self):
        """Test WAKE_MODEL_PATHS with empty string results in empty list."""
        with patch.dict(os.environ, {"WAKE_MODEL_PATHS": ""}):
            overrides = _get_env_overrides()
            assert overrides["wake"]["model_paths"] == []

    @pytest.mark.unit
    def test_wake_model_paths_with_spaces(self):
        """Test WAKE_MODEL_PATHS with spaces around commas."""
        with patch.dict(
            os.environ,
            {"WAKE_MODEL_PATHS": "/path/to/model1.onnx , /path/to/model2.onnx"},
        ):
            overrides = _get_env_overrides()
            assert overrides["wake"]["model_paths"] == [
                "/path/to/model1.onnx",
                "/path/to/model2.onnx",
            ]

    @pytest.mark.unit
    def test_wake_config_not_set(self):
        """Test that wake config defaults are used when env vars not set."""
        # Remove any wake-related env vars
        env_vars_to_remove = [
            "WAKE_PHRASES",
            "WAKE_THRESHOLD",
            "WAKE_SAMPLE_RATE",
            "WAKE_MODEL_PATHS",
            "WAKE_DETECTION_ENABLED",
        ]
        # Remove the keys if they exist
        for var in env_vars_to_remove:
            os.environ.pop(var, None)
        overrides = _get_env_overrides()
        # Should not have wake config if no env vars set
        assert "wake" not in overrides or not overrides.get("wake")

    @pytest.mark.unit
    def test_wake_config_multiple_vars(self):
        """Test parsing multiple wake config environment variables together."""
        with patch.dict(
            os.environ,
            {
                "WAKE_PHRASES": "hey atlas,ok atlas",
                "WAKE_THRESHOLD": "0.7",
                "WAKE_SAMPLE_RATE": "22050",
                "WAKE_MODEL_PATHS": "/path/to/model.onnx",
            },
        ):
            overrides = _get_env_overrides()
            assert overrides["wake"]["wake_phrases"] == ["hey atlas", "ok atlas"]
            assert overrides["wake"]["activation_threshold"] == 0.7
            assert overrides["wake"]["target_sample_rate_hz"] == 22050
            assert overrides["wake"]["model_paths"] == ["/path/to/model.onnx"]
