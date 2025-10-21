"""Test suite for the configuration management library."""

import os
from unittest import TestCase, mock


try:
    import pytest
except ImportError:  # pragma: no cover - fallback for static analysis environments

    class _PytestDummy:
        def __getattr__(self, name):
            return lambda x: x

    pytest = _PytestDummy()

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
from .service_configs import (
    AudioConfig,
    DiscordConfig,
    DiscordRuntimeConfig,
    HttpConfig,
    LLMClientConfig,
    LLMServiceConfig,
    LoggingConfig,
    OrchestratorClientConfig,
    TelemetryConfig,
    TTSClientConfig,
)


class TestFieldDefinition(TestCase):
    """Test FieldDefinition class."""

    @pytest.mark.unit
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

    @pytest.mark.unit
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

    @pytest.mark.unit
    def test_validate_url(self):
        """Test URL validation."""
        self.assertTrue(validate_url("http://example.com"))
        self.assertTrue(validate_url("https://example.com"))
        self.assertTrue(validate_url("http://localhost:8080"))
        self.assertTrue(validate_url("https://192.168.1.1:3000"))

        self.assertFalse(validate_url("not-a-url"))
        self.assertFalse(validate_url("ftp://example.com"))
        self.assertFalse(validate_url(""))

    @pytest.mark.unit
    def test_validate_port(self):
        """Test port validation."""
        self.assertTrue(validate_port(1))
        self.assertTrue(validate_port(8080))
        self.assertTrue(validate_port(65535))

        self.assertFalse(validate_port(0))
        self.assertFalse(validate_port(65536))
        self.assertFalse(validate_port(-1))

    @pytest.mark.unit
    def test_validate_positive(self):
        """Test positive number validation."""
        self.assertTrue(validate_positive(1))
        self.assertTrue(validate_positive(0.1))
        self.assertTrue(validate_positive(100))

        self.assertFalse(validate_positive(0))
        self.assertFalse(validate_positive(-1))
        self.assertFalse(validate_positive(-0.1))

    @pytest.mark.unit
    def test_validate_non_negative(self):
        """Test non-negative number validation."""
        self.assertTrue(validate_non_negative(0))
        self.assertTrue(validate_non_negative(1))
        self.assertTrue(validate_non_negative(0.1))

        self.assertFalse(validate_non_negative(-1))
        self.assertFalse(validate_non_negative(-0.1))


class TestBaseConfig(TestCase):
    """Test BaseConfig class."""

    @pytest.mark.unit
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

    @pytest.mark.unit
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
        config = TestConfig(required_field="test", optional_field="not_a_number")  # type: ignore
        with self.assertRaises(ValidationError):
            config.validate()

    @pytest.mark.unit
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

    @pytest.mark.unit
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

    @pytest.mark.unit
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

    @pytest.mark.unit
    def test_load_field_required_missing(self):
        """Test loading required field that's missing."""
        field_def = FieldDefinition(
            name="test_field",
            field_type=str,
            required=True,
        )

        with (
            mock.patch.dict(os.environ, {}, clear=True),
            self.assertRaises(RequiredFieldError),
        ):
            self.loader.load_field(field_def)

    @pytest.mark.unit
    def test_convert_value(self):
        """Test value conversion via load_field (public API)."""
        # string
        field = FieldDefinition(name="str_f", field_type=str, default="test")
        self.assertEqual(self.loader.load_field(field), "test")
        # int
        with mock.patch.dict(os.environ, {"TEST_INT": "42"}):
            field = FieldDefinition(
                name="int", field_type=int, default=0, env_var="TEST_INT"
            )
            self.assertEqual(self.loader.load_field(field), 42)
        # float
        with mock.patch.dict(os.environ, {"TEST_FLOAT": "3.14"}):
            field = FieldDefinition(
                name="flt", field_type=float, default=0.0, env_var="TEST_FLOAT"
            )
            self.assertEqual(self.loader.load_field(field), 3.14)
        # bool
        with mock.patch.dict(os.environ, {"TEST_BOOL": "true"}):
            field = FieldDefinition(
                name="b", field_type=bool, default=False, env_var="TEST_BOOL"
            )
            self.assertTrue(self.loader.load_field(field))
        with mock.patch.dict(os.environ, {"TEST_BOOL": "0"}):
            field = FieldDefinition(
                name="b", field_type=bool, default=True, env_var="TEST_BOOL"
            )
            self.assertFalse(self.loader.load_field(field))
        # list
        with mock.patch.dict(os.environ, {"TEST_LIST": "a,b,c"}):
            field = FieldDefinition(
                name="l", field_type=list, default=[], env_var="TEST_LIST"
            )
            self.assertEqual(self.loader.load_field(field), ["a", "b", "c"])

    @pytest.mark.unit
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

        with mock.patch.dict(
            os.environ, {"TEST_FIELD1": "env_value1", "TEST_FIELD2": "100"}
        ):
            config = self.loader.load_config(TestConfig)
            self.assertEqual(config.field1, "env_value1")
            self.assertEqual(config.field2, 100)


class TestConfigBuilder(TestCase):
    """Test ConfigBuilder class."""

    @pytest.mark.unit
    def test_builder_creation(self):
        """Test creating configuration builder."""
        builder = ConfigBuilder.for_service("test", Environment.DEVELOPMENT)
        self.assertEqual(builder.service_name, "test")
        self.assertEqual(builder.environment, Environment.DEVELOPMENT)

    @pytest.mark.unit
    def test_add_config(self):
        """Test adding configuration sections."""
        builder = ConfigBuilder.for_service("test", Environment.DEVELOPMENT)
        builder.add_config("logging", LoggingConfig)

        self.assertIn("logging", builder.load().configs)
        self.assertIsInstance(builder.load().configs["logging"], LoggingConfig)

    @pytest.mark.unit
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

    @pytest.mark.unit
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

    @pytest.mark.unit
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

    @pytest.mark.unit
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

    @pytest.mark.unit
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

    @pytest.mark.unit
    def test_config_creation(self):
        """Test basic configuration creation."""
        configs = {"logging": LoggingConfig()}
        service_config = ServiceConfig(
            service_name="test",
            environment=Environment.DEVELOPMENT,
            configs=configs,
        )

        self.assertEqual(service_config.service_name, "test")
        self.assertEqual(service_config.environment.value, "development")

    @pytest.mark.unit
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

    @pytest.mark.unit
    def test_discord_config(self):
        """Test Discord configuration."""
        config = DiscordConfig()
        self.assertEqual(config.token, "")
        self.assertEqual(config.guild_id, 0)
        self.assertEqual(config.voice_channel_id, 0)
        self.assertEqual(config.intents, ["guilds", "voice_states", "guild_messages"])
        self.assertFalse(config.auto_join)

    @pytest.mark.unit
    def test_audio_config(self):
        """Test Audio configuration."""
        config = AudioConfig()
        self.assertEqual(config.silence_timeout_seconds, 1.0)
        self.assertEqual(config.max_segment_duration_seconds, 15.0)
        self.assertEqual(config.input_sample_rate_hz, 48000)
        self.assertEqual(config.vad_sample_rate_hz, 16000)

    @pytest.mark.unit
    def test_http_config(self):
        """Test HTTP configuration."""
        config = HttpConfig()
        self.assertEqual(config.timeout, 30.0)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.retry_delay, 1.0)
        self.assertEqual(config.user_agent, "audio-orchestrator/1.0")

    @pytest.mark.unit
    def test_logging_config(self):
        """Test Logging configuration."""
        config = LoggingConfig()
        self.assertEqual(config.level, "INFO")
        self.assertTrue(config.json_logs)
        self.assertIsNone(config.service_name)

    @pytest.mark.unit
    def test_telemetry_config_extended_fields(self):
        """Test TelemetryConfig with sampling and warmup fields."""
        with mock.patch.dict(
            os.environ,
            {
                "LOG_LEVEL": "DEBUG",
                "LOG_JSON": "false",
                "LOG_SAMPLE_VAD_N": "25",
                "LOG_SAMPLE_UNKNOWN_USER_N": "100",
                "LOG_RATE_LIMIT_PACKET_WARN_S": "10",
                "LOG_SAMPLE_SEGMENT_READY_RATE": "0.5",
                "LOG_SAMPLE_SEGMENT_READY_N": "200",
                "DISCORD_WARMUP_AUDIO": "true",
                "STT_WARMUP": "false",
            },
        ):
            loader = EnvironmentLoader()
            cfg = loader.load_config(TelemetryConfig)
            self.assertEqual(cfg.log_level, "DEBUG")
            self.assertFalse(cfg.log_json)
            self.assertEqual(cfg.log_sample_vad_n, 25)
            self.assertEqual(cfg.log_sample_unknown_user_n, 100)
            self.assertEqual(cfg.log_rate_limit_packet_warn_s, 10)
            self.assertAlmostEqual(cfg.log_sample_segment_ready_rate or 0.0, 0.5)
            self.assertEqual(cfg.log_sample_segment_ready_n, 200)
            self.assertTrue(cfg.discord_warmup_audio)
            self.assertFalse(cfg.stt_warmup)

    @pytest.mark.unit
    def test_llm_service_config(self):
        """Test LLMServiceConfig env mapping."""
        with mock.patch.dict(os.environ, {"PORT": "8080", "LLM_AUTH_TOKEN": "abc"}):
            loader = EnvironmentLoader()
            cfg = loader.load_config(LLMServiceConfig)
            self.assertEqual(cfg.port, 8080)
            self.assertEqual(cfg.auth_token, "abc")

    @pytest.mark.unit
    def test_llm_client_config(self):
        """Test LLMClientConfig env mapping."""
        with mock.patch.dict(
            os.environ, {"LLM_BASE_URL": "http://llm:8000", "LLM_AUTH_TOKEN": "xyz"}
        ):
            loader = EnvironmentLoader()
            cfg = loader.load_config(LLMClientConfig)
            self.assertEqual(cfg.base_url, "http://llm:8000")
            self.assertEqual(cfg.auth_token, "xyz")

    @pytest.mark.unit
    def test_tts_client_config(self):
        """Test TTSClientConfig env mapping."""
        with mock.patch.dict(
            os.environ,
            {
                "TTS_BASE_URL": "http://tts:7000",
                "TTS_VOICE": "default",
                "TTS_TIMEOUT": "45",
                "TTS_AUTH_TOKEN": "tok",
            },
        ):
            loader = EnvironmentLoader()
            cfg = loader.load_config(TTSClientConfig)
            self.assertEqual(cfg.base_url, "http://tts:7000")
            self.assertEqual(cfg.voice, "default")
            self.assertEqual(cfg.timeout, 45.0)
            self.assertEqual(cfg.auth_token, "tok")

    @pytest.mark.unit
    def test_orchestrator_client_config(self):
        """Test OrchestratorClientConfig env mapping."""
        with mock.patch.dict(
            os.environ,
            {"ORCHESTRATOR_URL": "http://orchestrator:8000", "ORCH_TIMEOUT": "15"},
        ):
            loader = EnvironmentLoader()
            cfg = loader.load_config(OrchestratorClientConfig)
            self.assertEqual(cfg.base_url, "http://orchestrator:8000")
            self.assertEqual(cfg.timeout, 15.0)

    @pytest.mark.unit
    def test_discord_runtime_config(self):
        """Test DiscordRuntimeConfig env mapping."""
        with mock.patch.dict(
            os.environ,
            {
                "DISCORD_FULL_BOT": "true",
                "DISCORD_HTTP_MODE": "false",
                "DISCORD_MCP_MODE": "true",
            },
        ):
            loader = EnvironmentLoader()
            cfg = loader.load_config(DiscordRuntimeConfig)
            self.assertTrue(cfg.full_bot)
            self.assertFalse(cfg.http_mode)
            self.assertTrue(cfg.mcp_mode)


class TestConvenienceFunctions(TestCase):
    """Test convenience functions."""

    @pytest.mark.unit
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

    @pytest.mark.unit
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
