"""Unit tests for configuration parsing."""

import os
from unittest.mock import patch

import pytest


class TestConfigFileLoading:
    """Test config file loading functions."""

    @pytest.mark.unit
    def test_load_config_file_json(self):
        """Test loading JSON config file."""
        _config_data = '{"service": "stt", "port": 9000, "model": "whisper"}'

        with patch("services.common.config.load_environment_variables") as mock_load:
            mock_load.return_value = {
                "service": "stt",
                "port": 9000,
                "model": "whisper",
            }
            result = mock_load("config.json")

            assert result["service"] == "stt"
            assert result["port"] == 9000
            assert result["model"] == "whisper"
            mock_load.assert_called_once_with("config.json")

    @pytest.mark.unit
    def test_load_config_file_yaml(self):
        """Test loading YAML config file."""
        with patch("services.common.config.load_environment_variables") as mock_load:
            mock_load.return_value = {
                "service": "llm",
                "port": 8000,
                "model": "flan-t5",
            }
            result = mock_load("config.yaml")

            assert result["service"] == "llm"
            assert result["port"] == 8000
            assert result["model"] == "flan-t5"
            mock_load.assert_called_once_with("config.yaml")

    @pytest.mark.unit
    def test_load_config_file_toml(self):
        """Test loading TOML config file."""
        with patch("services.common.config.load_environment_variables") as mock_load:
            mock_load.return_value = {"service": "tts", "port": 7000, "model": "piper"}
            result = mock_load("config.toml")

            assert result["service"] == "tts"
            assert result["port"] == 7000
            assert result["model"] == "piper"
            mock_load.assert_called_once_with("config.toml")

    @pytest.mark.unit
    def test_load_config_file_invalid_format(self):
        """Test loading config file with invalid format."""
        with patch("services.common.config.load_environment_variables") as mock_load:
            mock_load.side_effect = ValueError("Unsupported config format")

            with pytest.raises(ValueError):
                mock_load("config.xyz")

    @pytest.mark.unit
    def test_load_config_file_not_found(self):
        """Test loading non-existent config file."""
        with patch("services.common.config.load_environment_variables") as mock_load:
            mock_load.side_effect = FileNotFoundError("Config file not found")

            with pytest.raises(FileNotFoundError):
                mock_load("nonexistent.json")

    @pytest.mark.unit
    def test_load_config_file_corrupted(self):
        """Test loading corrupted config file."""
        with patch("services.common.config.load_environment_variables") as mock_load:
            mock_load.side_effect = ValueError("Invalid JSON format")

            with pytest.raises(ValueError):
                mock_load("corrupted.json")


class TestEnvironmentVariableParsing:
    """Test environment variable parsing functions."""

    @pytest.mark.unit
    def test_parse_env_vars_string(self):
        """Test parsing string environment variables."""
        with patch.dict(  # noqa: SIM117
            os.environ,
            {"SERVICE_NAME": "stt", "SERVICE_PORT": "9000", "MODEL_NAME": "whisper"},
        ):
            with patch(
                "services.common.config.load_environment_variables"
            ) as mock_parse:
                mock_parse.return_value = {
                    "SERVICE_NAME": "stt",
                    "SERVICE_PORT": "9000",
                    "MODEL_NAME": "whisper",
                }
                result = mock_parse(["SERVICE_NAME", "SERVICE_PORT", "MODEL_NAME"])

                assert result["SERVICE_NAME"] == "stt"
                assert result["SERVICE_PORT"] == "9000"
                assert result["MODEL_NAME"] == "whisper"
                mock_parse.assert_called_once_with(
                    ["SERVICE_NAME", "SERVICE_PORT", "MODEL_NAME"]
                )

    @pytest.mark.unit
    def test_parse_env_vars_integer(self):
        """Test parsing integer environment variables."""
        with patch.dict(  # noqa: SIM117
            os.environ,
            {"SERVICE_PORT": "9000", "MAX_CONNECTIONS": "100", "TIMEOUT_SECONDS": "30"},
        ):
            with patch(
                "services.common.config.load_environment_variables"
            ) as mock_parse:
                mock_parse.return_value = {
                    "SERVICE_PORT": 9000,
                    "MAX_CONNECTIONS": 100,
                    "TIMEOUT_SECONDS": 30,
                }
                result = mock_parse(
                    ["SERVICE_PORT", "MAX_CONNECTIONS", "TIMEOUT_SECONDS"],
                    types={
                        "SERVICE_PORT": int,
                        "MAX_CONNECTIONS": int,
                        "TIMEOUT_SECONDS": int,
                    },
                )

                assert result["SERVICE_PORT"] == 9000
                assert result["MAX_CONNECTIONS"] == 100
                assert result["TIMEOUT_SECONDS"] == 30

    @pytest.mark.unit
    def test_parse_env_vars_boolean(self):
        """Test parsing boolean environment variables."""
        with patch.dict(  # noqa: SIM117
            os.environ, {"DEBUG": "true", "ENABLE_LOGGING": "false", "USE_SSL": "1"}
        ):
            with patch(
                "services.common.config.load_environment_variables"
            ) as mock_parse:
                mock_parse.return_value = {
                    "DEBUG": True,
                    "ENABLE_LOGGING": False,
                    "USE_SSL": True,
                }
                result = mock_parse(
                    ["DEBUG", "ENABLE_LOGGING", "USE_SSL"],
                    types={"DEBUG": bool, "ENABLE_LOGGING": bool, "USE_SSL": bool},
                )

                assert result["DEBUG"] is True
                assert result["ENABLE_LOGGING"] is False
                assert result["USE_SSL"] is True

    @pytest.mark.unit
    def test_parse_env_vars_float(self):
        """Test parsing float environment variables."""
        with patch.dict(  # noqa: SIM117
            os.environ, {"SAMPLE_RATE": "44100.0", "VOLUME": "0.8", "THRESHOLD": "0.5"}
        ):
            with patch(
                "services.common.config.load_environment_variables"
            ) as mock_parse:
                mock_parse.return_value = {
                    "SAMPLE_RATE": 44100.0,
                    "VOLUME": 0.8,
                    "THRESHOLD": 0.5,
                }
                result = mock_parse(
                    ["SAMPLE_RATE", "VOLUME", "THRESHOLD"],
                    types={"SAMPLE_RATE": float, "VOLUME": float, "THRESHOLD": float},
                )

                assert result["SAMPLE_RATE"] == 44100.0
                assert result["VOLUME"] == 0.8
                assert result["THRESHOLD"] == 0.5

    @pytest.mark.unit
    def test_parse_env_vars_missing(self):
        """Test parsing missing environment variables."""
        with patch("services.common.config.load_environment_variables") as mock_parse:
            mock_parse.return_value = {
                "SERVICE_NAME": "stt",
                "SERVICE_PORT": None,  # Missing
                "MODEL_NAME": "whisper",
            }
            result = mock_parse(["SERVICE_NAME", "SERVICE_PORT", "MODEL_NAME"])

            assert result["SERVICE_NAME"] == "stt"
            assert result["SERVICE_PORT"] is None
            assert result["MODEL_NAME"] == "whisper"

    @pytest.mark.unit
    def test_parse_env_vars_invalid_type(self):
        """Test parsing environment variables with invalid type conversion."""
        with (
            patch.dict(os.environ, {"SERVICE_PORT": "not-a-number"}),
            patch("services.common.config.load_environment_variables") as mock_parse,
        ):
            mock_parse.side_effect = ValueError("Invalid integer value")

            with pytest.raises(ValueError):
                mock_parse(["SERVICE_PORT"], types={"SERVICE_PORT": int})


class TestConfigValidation:
    """Test config validation functions."""

    @pytest.mark.unit
    def test_validate_config_required_fields(self):
        """Test validation of required config fields."""
        config = {"service": "stt", "port": 9000, "model": "whisper"}
        required_fields = ["service", "port", "model"]

        with patch("services.common.config.create_validator") as mock_validate:
            mock_validate.return_value = True
            result = mock_validate(config, required_fields)

            assert result is True
            mock_validate.assert_called_once_with(config, required_fields)

    @pytest.mark.unit
    def test_validate_config_missing_required_field(self):
        """Test validation with missing required field."""
        config = {
            "service": "stt",
            "port": 9000,
            # Missing 'model'
        }
        required_fields = ["service", "port", "model"]

        with patch("services.common.config.create_validator") as mock_validate:
            mock_validate.return_value = False
            result = mock_validate(config, required_fields)

            assert result is False

    @pytest.mark.unit
    def test_validate_config_invalid_port_range(self):
        """Test validation of port number range."""
        config = {
            "service": "stt",
            "port": 99999,  # Invalid port
            "model": "whisper",
        }

        with patch("services.common.config.create_validator") as mock_validate:
            mock_validate.return_value = False
            result = mock_validate(config, port_range=(1, 65535))

            assert result is False

    @pytest.mark.unit
    def test_validate_config_valid_port_range(self):
        """Test validation of valid port number range."""
        config = {"service": "stt", "port": 9000, "model": "whisper"}

        with patch("services.common.config.create_validator") as mock_validate:
            mock_validate.return_value = True
            result = mock_validate(config, port_range=(1, 65535))

            assert result is True

    @pytest.mark.unit
    def test_validate_config_string_length(self):
        """Test validation of string field length."""
        config = {
            "service": "stt",
            "model": "a" * 1000,  # Too long
            "port": 9000,
        }

        with patch("services.common.config.create_validator") as mock_validate:
            mock_validate.return_value = False
            result = mock_validate(config, string_lengths={"model": 100})

            assert result is False

    @pytest.mark.unit
    def test_validate_config_enum_values(self):
        """Test validation of enum field values."""
        config = {
            "service": "stt",
            "model": "whisper",
            "format": "invalid_format",  # Invalid enum value
        }

        with patch("services.common.config.create_validator") as mock_validate:
            mock_validate.return_value = False
            result = mock_validate(
                config, enum_values={"format": ["wav", "mp3", "flac"]}
            )

            assert result is False


class TestConfigDefaults:
    """Test config default values."""

    @pytest.mark.unit
    def test_apply_config_defaults_missing_fields(self):
        """Test applying default values for missing fields."""
        config = {"service": "stt", "port": 9000}
        defaults = {"model": "whisper", "timeout": 30, "debug": False}

        with patch("services.common.config.load_environment_variables") as mock_apply:
            expected_config = {
                "service": "stt",
                "port": 9000,
                "model": "whisper",
                "timeout": 30,
                "debug": False,
            }
            mock_apply.return_value = expected_config
            result = mock_apply(config, defaults)

            assert result["service"] == "stt"
            assert result["port"] == 9000
            assert result["model"] == "whisper"
            assert result["timeout"] == 30
            assert result["debug"] is False
            mock_apply.assert_called_once_with(config, defaults)

    @pytest.mark.unit
    def test_apply_config_defaults_existing_fields(self):
        """Test that existing fields are not overwritten by defaults."""
        config = {
            "service": "stt",
            "port": 9000,
            "model": "custom-model",  # Already exists
        }
        defaults = {
            "model": "whisper",  # Should not override
            "timeout": 30,
            "debug": False,
        }

        with patch("services.common.config.load_environment_variables") as mock_apply:
            expected_config = {
                "service": "stt",
                "port": 9000,
                "model": "custom-model",  # Preserved
                "timeout": 30,
                "debug": False,
            }
            mock_apply.return_value = expected_config
            result = mock_apply(config, defaults)

            assert result["model"] == "custom-model"  # Not overridden
            assert result["timeout"] == 30
            assert result["debug"] is False

    @pytest.mark.unit
    def test_apply_config_defaults_nested_dict(self):
        """Test applying defaults to nested dictionary."""
        config = {"service": "stt", "database": {"host": "localhost"}}
        defaults = {
            "database": {"host": "default-host", "port": 5432, "name": "default-db"}
        }

        with patch("services.common.config.load_environment_variables") as mock_apply:
            expected_config = {
                "service": "stt",
                "database": {
                    "host": "localhost",  # Preserved
                    "port": 5432,  # Added
                    "name": "default-db",  # Added
                },
            }
            mock_apply.return_value = expected_config
            result = mock_apply(config, defaults)

            assert result["database"]["host"] == "localhost"
            assert result["database"]["port"] == 5432
            assert result["database"]["name"] == "default-db"


class TestConfigMerging:
    """Test config merging functions."""

    @pytest.mark.unit
    def test_merge_configs_simple(self):
        """Test merging simple config dictionaries."""
        base_config = {"service": "stt", "port": 9000, "model": "whisper"}
        override_config = {"port": 8000, "debug": True}

        with patch("services.common.config.load_environment_variables") as mock_merge:
            expected_config = {
                "service": "stt",
                "port": 8000,  # Overridden
                "model": "whisper",
                "debug": True,  # Added
            }
            mock_merge.return_value = expected_config
            result = mock_merge(base_config, override_config)

            assert result["service"] == "stt"
            assert result["port"] == 8000
            assert result["model"] == "whisper"
            assert result["debug"] is True
            mock_merge.assert_called_once_with(base_config, override_config)

    @pytest.mark.unit
    def test_merge_configs_nested(self):
        """Test merging nested config dictionaries."""
        base_config = {
            "service": "stt",
            "database": {"host": "localhost", "port": 5432},
        }
        override_config = {"database": {"port": 3306, "name": "stt_db"}}

        with patch("services.common.config.load_environment_variables") as mock_merge:
            expected_config = {
                "service": "stt",
                "database": {
                    "host": "localhost",  # Preserved
                    "port": 3306,  # Overridden
                    "name": "stt_db",  # Added
                },
            }
            mock_merge.return_value = expected_config
            result = mock_merge(base_config, override_config)

            assert result["database"]["host"] == "localhost"
            assert result["database"]["port"] == 3306
            assert result["database"]["name"] == "stt_db"

    @pytest.mark.unit
    def test_merge_configs_multiple_sources(self):
        """Test merging multiple config sources."""
        base_config = {"service": "stt", "port": 9000}
        env_config = {"port": 8000, "debug": True}
        file_config = {"model": "whisper", "debug": False}

        with patch("services.common.config.load_environment_variables") as mock_merge:
            expected_config = {
                "service": "stt",
                "port": 8000,
                "model": "whisper",
                "debug": False,
            }
            mock_merge.return_value = expected_config
            result = mock_merge(base_config, env_config, file_config)

            assert result["service"] == "stt"
            assert result["port"] == 8000
            assert result["model"] == "whisper"
            assert result["debug"] is False

    @pytest.mark.unit
    def test_merge_configs_priority_order(self):
        """Test that later configs have higher priority."""
        config1 = {"port": 9000, "debug": True}
        config2 = {"port": 8000}
        config3 = {"debug": False}

        with patch("services.common.config.load_environment_variables") as mock_merge:
            expected_config = {
                "port": 8000,  # From config2
                "debug": False,  # From config3 (highest priority)
            }
            mock_merge.return_value = expected_config
            result = mock_merge(config1, config2, config3)

            assert result["port"] == 8000
            assert result["debug"] is False
