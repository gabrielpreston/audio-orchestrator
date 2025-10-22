"""Test voice pipeline configuration."""

from services.common.service_configs import (
    STTConfig,
    FasterWhisperConfig,
    WakeConfig,
)


def test_stt_config_vad_filter():
    """Test STTConfig vad_filter field."""
    config = STTConfig(base_url="http://test", vad_filter=True)
    assert config.vad_filter is True

    config_default = STTConfig(base_url="http://test")
    assert config_default.vad_filter is False


def test_faster_whisper_config_enhancement():
    """Test FasterWhisperConfig enable_enhancement field."""
    config = FasterWhisperConfig(enable_enhancement=True)
    assert config.enable_enhancement is True

    config_default = FasterWhisperConfig()
    assert config_default.enable_enhancement is False


def test_wake_config_expanded_phrases():
    """Test WakeConfig expanded phrases and lower threshold."""
    config = WakeConfig()
    assert "atlas" in config.wake_phrases
    assert "hey assistant" in config.wake_phrases
    assert config.activation_threshold == 0.3
    assert len(config.wake_phrases) == 5
