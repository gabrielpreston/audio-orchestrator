"""Tests for audio metrics registration and creation."""

from unittest.mock import Mock

import pytest

from services.common.audio_metrics import MetricKind, register_service_metrics


@pytest.fixture
def mock_observability_manager():
    """Create a mock ObservabilityManager."""
    manager = Mock()
    manager.service_name = "test_service"
    manager.service_version = "1.0.0"

    # Mock meter
    mock_meter = Mock()
    manager.get_meter = Mock(return_value=mock_meter)

    return manager


@pytest.fixture
def mock_observability_manager_no_meter():
    """Create a mock ObservabilityManager without meter (metrics disabled)."""
    manager = Mock()
    manager.service_name = "test_service"
    manager.service_version = "1.0.0"
    manager.get_meter = Mock(return_value=None)

    return manager


@pytest.mark.unit
def test_register_service_metrics_single_kind(mock_observability_manager):
    """Test registering a single metric kind."""
    metrics = register_service_metrics(
        mock_observability_manager, kinds=[MetricKind.AUDIO]
    )

    assert "audio" in metrics
    assert isinstance(metrics["audio"], dict)
    # Audio metrics should have specific keys
    assert "audio_processing_duration" in metrics["audio"]
    assert "audio_quality_score" in metrics["audio"]


@pytest.mark.unit
def test_register_service_metrics_multiple_kinds(mock_observability_manager):
    """Test registering multiple metric kinds."""
    metrics = register_service_metrics(
        mock_observability_manager, kinds=[MetricKind.AUDIO, MetricKind.SYSTEM]
    )

    assert "audio" in metrics
    assert "system" in metrics
    assert isinstance(metrics["audio"], dict)
    assert isinstance(metrics["system"], dict)


@pytest.mark.unit
def test_register_service_metrics_all_kinds(mock_observability_manager):
    """Test registering all metric kinds."""
    all_kinds = [
        MetricKind.AUDIO,
        MetricKind.STT,
        MetricKind.TTS,
        MetricKind.LLM,
        MetricKind.HTTP,
        MetricKind.SYSTEM,
        MetricKind.GUARDRAILS,
    ]

    metrics = register_service_metrics(mock_observability_manager, kinds=all_kinds)

    # All metric groups should be present
    assert "audio" in metrics
    assert "stt" in metrics
    assert "tts" in metrics
    assert "llm" in metrics
    assert "http" in metrics
    assert "system" in metrics
    assert "guardrails" in metrics


@pytest.mark.unit
def test_register_service_metrics_duplicate_kinds(mock_observability_manager):
    """Test that duplicate metric kinds are deduplicated."""
    metrics = register_service_metrics(
        mock_observability_manager,
        kinds=[MetricKind.AUDIO, MetricKind.AUDIO, MetricKind.SYSTEM],
    )

    # Should only create metrics once
    assert "audio" in metrics
    assert "system" in metrics
    assert len(metrics) == 2


@pytest.mark.unit
def test_register_service_metrics_invalid_kind(mock_observability_manager):
    """Test that invalid metric kinds raise ValueError."""

    # Create an invalid metric kind (not an enum member)
    class InvalidKind:
        value = "invalid"

    with pytest.raises(ValueError, match="Invalid metric kinds"):
        register_service_metrics(
            mock_observability_manager,
            kinds=[MetricKind.AUDIO, InvalidKind()],  # type: ignore[list-item]
        )


@pytest.mark.unit
def test_register_service_metrics_empty_kinds(mock_observability_manager):
    """Test registering with empty kinds list."""
    metrics = register_service_metrics(mock_observability_manager, kinds=[])

    assert metrics == {}


@pytest.mark.unit
def test_register_service_metrics_no_meter(mock_observability_manager_no_meter):
    """Test that metrics return empty dict when meter is not available."""
    metrics = register_service_metrics(
        mock_observability_manager_no_meter, kinds=[MetricKind.AUDIO, MetricKind.SYSTEM]
    )

    # Should still return dict structure, but metrics will be empty
    assert "audio" in metrics
    assert "system" in metrics
    assert metrics["audio"] == {}
    assert metrics["system"] == {}


@pytest.mark.unit
def test_register_service_metrics_return_structure(mock_observability_manager):
    """Test that return structure matches expected format."""
    metrics = register_service_metrics(
        mock_observability_manager, kinds=[MetricKind.STT, MetricKind.LLM]
    )

    # Should be dict[str, dict[str, Any]]
    assert isinstance(metrics, dict)
    assert "stt" in metrics
    assert "llm" in metrics
    assert isinstance(metrics["stt"], dict)
    assert isinstance(metrics["llm"], dict)


@pytest.mark.unit
def test_register_service_metrics_stt_has_expected_keys(mock_observability_manager):
    """Test that STT metrics have expected keys."""
    metrics = register_service_metrics(
        mock_observability_manager, kinds=[MetricKind.STT]
    )

    stt_metrics = metrics["stt"]
    assert "stt_requests" in stt_metrics
    assert "stt_latency" in stt_metrics
    assert "pre_stt_encode" in stt_metrics
    assert "stt_audio_duration" in stt_metrics


@pytest.mark.unit
def test_register_service_metrics_llm_has_expected_keys(mock_observability_manager):
    """Test that LLM metrics have expected keys."""
    metrics = register_service_metrics(
        mock_observability_manager, kinds=[MetricKind.LLM]
    )

    llm_metrics = metrics["llm"]
    assert "llm_requests" in llm_metrics
    assert "llm_latency" in llm_metrics
    assert "llm_tokens" in llm_metrics


@pytest.mark.unit
def test_register_service_metrics_tts_has_expected_keys(mock_observability_manager):
    """Test that TTS metrics have expected keys."""
    metrics = register_service_metrics(
        mock_observability_manager, kinds=[MetricKind.TTS]
    )

    tts_metrics = metrics["tts"]
    assert "tts_requests" in tts_metrics
    assert "tts_synthesis_duration" in tts_metrics
    assert "tts_text_length" in tts_metrics


@pytest.mark.unit
def test_register_service_metrics_guardrails_has_expected_keys(
    mock_observability_manager,
):
    """Test that guardrails metrics have expected keys."""
    metrics = register_service_metrics(
        mock_observability_manager, kinds=[MetricKind.GUARDRAILS]
    )

    guardrails_metrics = metrics["guardrails"]
    assert "validation_requests" in guardrails_metrics
    assert "validation_duration" in guardrails_metrics
    assert "toxicity_checks" in guardrails_metrics
    assert "pii_detections" in guardrails_metrics
    assert "rate_limit_hits" in guardrails_metrics
    assert "escalations" in guardrails_metrics


@pytest.mark.unit
def test_register_service_metrics_http_has_expected_keys(mock_observability_manager):
    """Test that HTTP metrics have expected keys."""
    metrics = register_service_metrics(
        mock_observability_manager, kinds=[MetricKind.HTTP]
    )

    http_metrics = metrics["http"]
    assert "http_requests" in http_metrics
    assert "http_request_duration" in http_metrics


@pytest.mark.unit
def test_register_service_metrics_system_empty_dict(mock_observability_manager):
    """Test that system metrics return empty dict (callbacks registered independently)."""
    metrics = register_service_metrics(
        mock_observability_manager, kinds=[MetricKind.SYSTEM]
    )

    # System metrics use ObservableGauge callbacks, so dict is empty
    # but callbacks are registered at creation time
    assert "system" in metrics
    assert isinstance(metrics["system"], dict)


@pytest.mark.unit
def test_metric_kind_enum_values():
    """Test that MetricKind enum has correct values."""
    assert MetricKind.AUDIO.value == "audio"
    assert MetricKind.STT.value == "stt"
    assert MetricKind.TTS.value == "tts"
    assert MetricKind.LLM.value == "llm"
    assert MetricKind.HTTP.value == "http"
    assert MetricKind.SYSTEM.value == "system"
    assert MetricKind.GUARDRAILS.value == "guardrails"
