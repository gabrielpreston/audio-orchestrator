"""Test suite for the configuration management library."""

import os
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from .config import (
    BaseConfig,
    ConfigBuilder,
    Environment,
    EnvironmentLoader,
    FieldDefinition,
    RequiredFieldError,
    ServiceConfig,
    ValidationError,
    create_field_definition,
    load_service_config,
    validate_non_negative,
    validate_port,
    validate_positive,
    validate_url,
)
from .service_configs import AudioConfig, DiscordConfig, HttpConfig, LoggingConfig


class TestFieldDefinition(TestCase):
    """Test FieldDefinition class."""

    def test_field_definition_creation(self):
        """Test creating field definitions."""
        field = FieldDefinition(
            name="test_field",
            field_type=str,
            default="default_value",
            required=False,
            description="Test field",
        )

        self.assertEqual(field.name, "test_field")
        self.assertEqual(field.field_type, str)
        self.assertEqual(field.default, "default_value")
        self.assertFalse(field.required)
        self.assertEqual(field.description, "Test field")

    def test_field_definition_validation(self):
        """Test field definition validation."""
        # Test required field with default (should fail)
        with self.assertRaises(ValueError):
            FieldDefinition(
                name="test_field",
                field_type=str,
                default="default_value",
                required=True,
            )

        # Test default not in choices (should fail)
        with self.assertRaises(ValueError):
            FieldDefinition(
                name="test_field",
                field_type=str,
                default="invalid",
                choices=["valid1", "valid2"],
            )


class TestValidators(TestCase):
    """Test validation functions."""

    def test_validate_url(self):
        """Test URL validation."""
        self.assertTrue(validate_url("http://example.com"))
        self.assertTrue(validate_url("https://example.com"))
        self.assertTrue(validate_url("http://localhost:8080"))
        self.assertTrue(validate_url("https://192.168.1.1:3000"))

        self.assertFalse(validate_url("not-a-url"))
        self.assertFalse(validate_url("ftp://example.com"))
        self.assertFalse(validate_url(""))

    def test_validate_port(self):
        """Test port validation."""
        self.assertTrue(validate_port(1))
        self.assertTrue(validate_port(8080))
        self.assertTrue(validate_port(65535))

        self.assertFalse(validate_port(0))
        self.assertFalse(validate_port(65536))
        self.assertFalse(validate_port(-1))

    def test_validate_positive(self):
        """Test positive number validation."""
        self.assertTrue(validate_positive(1))
        self.assertTrue(validate_positive(0.1))
        self.assertTrue(validate_positive(100))

        self.assertFalse(validate_positive(0))
        self.assertFalse(validate_positive(-1))
        self.assertFalse(validate_positive(-0.1))

    def test_validate_non_negative(self):
        """Test non-negative number validation."""
        self.assertTrue(validate_non_negative(0))
        self.assertTrue(validate_non_negative(1))
        self.assertTrue(validate_non_negative(0.1))

        self.assertFalse(validate_non_negative(-1))
        self.assertFalse(validate_non_negative(-0.1))


class TestBaseConfig(TestCase):
    """Test BaseConfig class."""

    def test_config_initialization(self):
        """Test configuration initialization."""

        class TestConfig(BaseConfig):
            def __init__(self, field1: str = "default", field2: int = 42, **kwargs):
                super().__init__(**kwargs)
                self.field1 = field1
                self.field2 = field2

            @classmethod
            def get_field_definitions(cls):
                return [
                    FieldDefinition("field1", str, "default"),
                    FieldDefinition("field2", int, 42),
                ]

        config = TestConfig()
        self.assertEqual(config.field1, "default")
        self.assertEqual(config.field2, 42)

        config = TestConfig(field1="custom", field2=100)
        self.assertEqual(config.field1, "custom")
        self.assertEqual(config.field2, 100)

    def test_config_validation(self):
        """Test configuration validation."""

        class TestConfig(BaseConfig):
            def __init__(
                self,
                required_field: str | None = None,
                optional_field: int | None = None,
                **kwargs,
            ):
                super().__init__(**kwargs)
                self.required_field = required_field
                self.optional_field = optional_field

            @classmethod
            def get_field_definitions(cls):
                return [
                    FieldDefinition("required_field", str, required=True),
                    FieldDefinition("optional_field", int, 42),
                ]

        # Test valid configuration
        config = TestConfig(required_field="test", optional_field=100)
        config.validate()  # Should not raise

        # Test missing required field
        config = TestConfig(optional_field=100)
        with self.assertRaises(RequiredFieldError):
            config.validate()

        # Test type validation
        config = TestConfig(required_field="test", optional_field="not_a_number")
        with self.assertRaises(ValidationError):
            config.validate()

    def test_config_to_dict(self):
        """Test converting configuration to dictionary."""

        class TestConfig(BaseConfig):
            def __init__(self, field1: str = "value1", field2: int = 42, **kwargs):
                super().__init__(**kwargs)
                self.field1 = field1
                self.field2 = field2

            @classmethod
            def get_field_definitions(cls):
                return [
                    FieldDefinition("field1", str, "value1"),
                    FieldDefinition("field2", int, 42),
                ]

        config = TestConfig()
        config_dict = config.to_dict()

        self.assertEqual(config_dict["field1"], "value1")
        self.assertEqual(config_dict["field2"], 42)


class TestEnvironmentLoader(TestCase):
    """Test EnvironmentLoader class."""

    def setUp(self):
        """Set up test environment."""
        self.loader = EnvironmentLoader("TEST")

    def test_load_field_with_default(self):
        """Test loading field with default value."""
        field_def = FieldDefinition(
            name="test_field",
            field_type=str,
            default="default_value",
        )

        # Test with no environment variable
        with mock.patch.dict(os.environ, {}, clear=True):
            value = self.loader.load_field(field_def)
            self.assertEqual(value, "default_value")

    def test_load_field_with_environment_variable(self):
        """Test loading field from environment variable."""
        field_def = FieldDefinition(
            name="test_field",
            field_type=str,
            default="default_value",
            env_var="TEST_TEST_FIELD",
        )

        # Test with environment variable set
        with mock.patch.dict(os.environ, {"TEST_TEST_FIELD": "env_value"}):
            value = self.loader.load_field(field_def)
            self.assertEqual(value, "env_value")

    def test_load_field_required_missing(self):
        """Test loading required field that's missing."""
        field_def = FieldDefinition(
            name="test_field",
            field_type=str,
            required=True,
        )

        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RequiredFieldError):
                self.loader.load_field(field_def)

    def test_convert_value(self):
        """Test value conversion."""
        # Test string conversion
        self.assertEqual(self.loader._convert_value("test", str), "test")

        # Test int conversion
        self.assertEqual(self.loader._convert_value("42", int), 42)

        # Test float conversion
        self.assertEqual(self.loader._convert_value("3.14", float), 3.14)

        # Test bool conversion
        self.assertTrue(self.loader._convert_value("true", bool))
        self.assertTrue(self.loader._convert_value("1", bool))
        self.assertFalse(self.loader._convert_value("false", bool))
        self.assertFalse(self.loader._convert_value("0", bool))

        # Test list conversion
        self.assertEqual(self.loader._convert_value("a,b,c", list), ["a", "b", "c"])

    def test_load_config(self):
        """Test loading complete configuration."""

        class TestConfig(BaseConfig):
            def __init__(self, field1: str = "default1", field2: int = 42, **kwargs):
                super().__init__(**kwargs)
                self.field1 = field1
                self.field2 = field2

            @classmethod
            def get_field_definitions(cls):
                return [
                    FieldDefinition("field1", str, "default1", env_var="TEST_FIELD1"),
                    FieldDefinition("field2", int, 42, env_var="TEST_FIELD2"),
                ]

        with mock.patch.dict(os.environ, {"TEST_FIELD1": "env_value1", "TEST_FIELD2": "100"}):
            config = self.loader.load_config(TestConfig)
            self.assertEqual(config.field1, "env_value1")
            self.assertEqual(config.field2, 100)


class TestConfigBuilder(TestCase):
    """Test ConfigBuilder class."""

    def test_builder_creation(self):
        """Test creating configuration builder."""
        builder = ConfigBuilder.for_service("test", Environment.DEVELOPMENT)
        self.assertEqual(builder.service_name, "test")
        self.assertEqual(builder.environment, Environment.DEVELOPMENT)

    def test_add_config(self):
        """Test adding configuration sections."""
        builder = ConfigBuilder.for_service("test", Environment.DEVELOPMENT)
        builder.add_config("logging", LoggingConfig)

        self.assertIn("logging", builder._configs)
        self.assertIsInstance(builder._configs["logging"], LoggingConfig)

    def test_load(self):
        """Test loading complete configuration."""
        builder = ConfigBuilder.for_service("test", Environment.DEVELOPMENT)
        config = builder.add_config("logging", LoggingConfig).load()

        self.assertIsInstance(config, ServiceConfig)
        self.assertEqual(config.service_name, "test")
        self.assertEqual(config.environment, Environment.DEVELOPMENT)
        self.assertIn("logging", config.configs)


class TestServiceConfig(TestCase):
    """Test ServiceConfig class."""

    def test_service_config_creation(self):
        """Test creating service configuration."""
        configs = {"logging": LoggingConfig()}
        service_config = ServiceConfig(
            service_name="test",
            environment=Environment.DEVELOPMENT,
            configs=configs,
        )

        self.assertEqual(service_config.service_name, "test")
        self.assertEqual(service_config.environment, Environment.DEVELOPMENT)
        self.assertEqual(service_config.configs, configs)

    def test_get_config(self):
        """Test getting configuration section."""
        configs = {"logging": LoggingConfig()}
        service_config = ServiceConfig(
            service_name="test",
            environment=Environment.DEVELOPMENT,
            configs=configs,
        )

        logging_config = service_config.get_config("logging")
        self.assertIsInstance(logging_config, LoggingConfig)

        with self.assertRaises(KeyError):
            service_config.get_config("nonexistent")

    def test_validate(self):
        """Test configuration validation."""
        configs = {"logging": LoggingConfig()}
        service_config = ServiceConfig(
            service_name="test",
            environment=Environment.DEVELOPMENT,
            configs=configs,
        )

        # Should not raise
        service_config.validate()

    def test_to_dict(self):
        """Test converting to dictionary."""
        configs = {"logging": LoggingConfig()}
        service_config = ServiceConfig(
            service_name="test",
            environment=Environment.DEVELOPMENT,
            configs=configs,
        )

        config_dict = service_config.to_dict()
        self.assertEqual(config_dict["service_name"], "test")
        self.assertEqual(config_dict["environment"], "development")
        self.assertIn("configs", config_dict)

    def test_save_and_load_file(self):
        """Test saving and loading configuration to/from file."""
        configs = {"logging": LoggingConfig()}
        service_config = ServiceConfig(
            service_name="test",
            environment=Environment.DEVELOPMENT,
            configs=configs,
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_file = Path(f.name)

        try:
            # Save configuration
            service_config.save_to_file(temp_file)
            self.assertTrue(temp_file.exists())

            # Load configuration
            loaded_config = ServiceConfig.load_from_file(temp_file)
            self.assertEqual(loaded_config.service_name, "test")
            self.assertEqual(loaded_config.environment.value, "development")
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def test_getattr(self):
        """Test direct access to configuration sections."""
        configs = {"logging": LoggingConfig()}
        service_config = ServiceConfig(
            service_name="test",
            environment=Environment.DEVELOPMENT,
            configs=configs,
        )

        logging_config = service_config.logging
        self.assertIsInstance(logging_config, LoggingConfig)


class TestServiceConfigs(TestCase):
    """Test service-specific configuration classes."""

    def test_discord_config(self):
        """Test Discord configuration."""
        config = DiscordConfig()
        self.assertEqual(config.token, "")
        self.assertEqual(config.guild_id, 0)
        self.assertEqual(config.voice_channel_id, 0)
        self.assertEqual(config.intents, ["guilds", "voice_states", "guild_messages"])
        self.assertFalse(config.auto_join)

    def test_audio_config(self):
        """Test Audio configuration."""
        config = AudioConfig()
        self.assertEqual(config.silence_timeout_seconds, 1.0)
        self.assertEqual(config.max_segment_duration_seconds, 15.0)
        self.assertEqual(config.input_sample_rate_hz, 48000)
        self.assertEqual(config.vad_sample_rate_hz, 16000)

    def test_http_config(self):
        """Test HTTP configuration."""
        config = HttpConfig()
        self.assertEqual(config.timeout, 30.0)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.retry_delay, 1.0)
        self.assertEqual(config.user_agent, "discord-voice-lab/1.0")

    def test_logging_config(self):
        """Test Logging configuration."""
        config = LoggingConfig()
        self.assertEqual(config.level, "INFO")
        self.assertTrue(config.json_logs)
        self.assertIsNone(config.service_name)


class TestConvenienceFunctions(TestCase):
    """Test convenience functions."""

    def test_create_field_definition(self):
        """Test create_field_definition function."""
        field = create_field_definition(
            name="test_field",
            field_type=str,
            default="test_value",
            description="Test field",
        )

        self.assertEqual(field.name, "test_field")
        self.assertEqual(field.field_type, str)
        self.assertEqual(field.default, "test_value")
        self.assertEqual(field.description, "Test field")

    def test_load_service_config(self):
        """Test load_service_config function."""
        config = load_service_config("test", Environment.DEVELOPMENT)

        self.assertIsInstance(config, ServiceConfig)
        self.assertEqual(config.service_name, "test")
        self.assertEqual(config.environment, Environment.DEVELOPMENT)
        self.assertIn("logging", config.configs)
        self.assertIn("http", config.configs)


if __name__ == "__main__":
    import unittest

    unittest.main()
