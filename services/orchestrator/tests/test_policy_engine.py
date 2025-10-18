"""
Tests for policy engine functionality.

This module validates that the policy engine makes correct decisions
for VAD, endpointing, barge-in, and wake phrase detection.
"""

from services.orchestrator.policy_config import (
    BargeInMode,
    EndpointingMode,
    PolicyConfig,
    VADMode,
)
from services.orchestrator.policy_engine import (
    BargeInAction,
    EndpointingState,
    PolicyEngine,
)


class TestPolicyConfig:
    """Test PolicyConfig data structure."""

    def test_policy_config_creation(self):
        """Test creating PolicyConfig with defaults."""
        config = PolicyConfig()

        assert config.vad.enabled is True
        assert config.endpointing.enabled is True
        assert config.barge_in.enabled is True
        assert config.wake.enabled is True
        assert config.debug_mode is False

    def test_policy_config_to_dict(self):
        """Test converting PolicyConfig to dictionary."""
        config = PolicyConfig()
        data = config.to_dict()

        assert "vad" in data
        assert "endpointing" in data
        assert "barge_in" in data
        assert "wake" in data
        assert "latency" in data
        assert data["debug_mode"] is False

    def test_policy_config_from_dict(self):
        """Test creating PolicyConfig from dictionary."""
        data = {
            "vad": {
                "enabled": False,
                "mode": "aggressive",
                "sensitivity": 0.8,
            },
            "endpointing": {
                "enabled": True,
                "mode": "fast",
                "max_speech_duration_ms": 15000.0,
            },
            "barge_in": {
                "enabled": True,
                "mode": "immediate",
                "detection_threshold": 0.9,
            },
            "wake": {
                "enabled": True,
                "confidence_threshold": 0.9,
                "cooldown_ms": 3000.0,
            },
            "latency": {
                "max_e2e_latency_ms": 300.0,
                "max_barge_in_delay_ms": 200.0,
            },
            "debug_mode": True,
        }

        config = PolicyConfig.from_dict(data)

        assert config.vad.enabled is False
        assert config.vad.mode == VADMode.AGGRESSIVE
        assert config.vad.sensitivity == 0.8
        assert config.endpointing.mode == EndpointingMode.FAST
        assert config.barge_in.mode == BargeInMode.IMMEDIATE
        assert config.wake.confidence_threshold == 0.9
        assert config.debug_mode is True

    def test_policy_config_validation(self):
        """Test PolicyConfig validation."""
        config = PolicyConfig()
        errors = config.validate()

        assert len(errors) == 0

    def test_policy_config_validation_errors(self):
        """Test PolicyConfig validation with errors."""
        config = PolicyConfig()
        config.vad.sensitivity = 1.5  # Invalid: > 1.0
        config.endpointing.confidence_threshold = 1.5  # Invalid: > 1.0
        config.barge_in.detection_threshold = -0.1  # Invalid: < 0.0
        config.latency.max_e2e_latency_ms = -100.0  # Invalid: < 0.0

        errors = config.validate()

        assert len(errors) > 0
        assert any("VAD sensitivity" in error for error in errors)
        assert any("Endpointing confidence threshold" in error for error in errors)
        assert any("Barge-in detection threshold" in error for error in errors)
        assert any("Max E2E latency" in error for error in errors)


class TestPolicyEngine:
    """Test PolicyEngine functionality."""

    def test_policy_engine_creation(self):
        """Test creating PolicyEngine with default config."""
        engine = PolicyEngine()

        assert engine.config is not None
        assert engine._current_state == EndpointingState.LISTENING
        assert engine._is_speaking is False

    def test_policy_engine_creation_custom_config(self):
        """Test creating PolicyEngine with custom config."""
        config = PolicyConfig()
        config.vad.enabled = False

        engine = PolicyEngine(config)

        assert engine.config.vad.enabled is False

    def test_evaluate_vad_speech_detected(self):
        """Test VAD evaluation with speech detected."""
        engine = PolicyEngine()

        # High RMS and confidence should trigger speech
        decision = engine.evaluate_vad(
            audio_data=b"\x00\x01\x02\x03" * 100,
            rms=5000.0,
            metadata={
                "confidence": 0.9,
                "sample_rate": 16000,
                "duration_ms": 250.0,
            },
        )

        assert decision.is_speech is True
        assert decision.confidence == 0.9
        assert "Speech detected" in decision.reason

    def test_evaluate_vad_no_speech(self):
        """Test VAD evaluation with no speech."""
        engine = PolicyEngine()

        # Low RMS and confidence should not trigger speech
        decision = engine.evaluate_vad(
            audio_data=b"\x00\x00\x00\x00" * 100,
            rms=100.0,
            metadata={
                "confidence": 0.2,
                "sample_rate": 16000,
                "duration_ms": 20.0,
            },
        )

        assert decision.is_speech is False
        assert decision.confidence == 0.2

    def test_evaluate_vad_disabled(self):
        """Test VAD evaluation when disabled."""
        config = PolicyConfig()
        config.vad.enabled = False
        engine = PolicyEngine(config)

        decision = engine.evaluate_vad(
            audio_data=b"\x00\x01\x02\x03" * 100,
            rms=5000.0,
            metadata={"confidence": 0.9},
        )

        assert decision.is_speech is False
        assert "VAD disabled" in decision.reason

    def test_evaluate_endpointing_speech_too_short(self):
        """Test endpointing evaluation with speech too short."""
        engine = PolicyEngine()

        decision = engine.evaluate_endpointing(
            is_speech=True,
            confidence=0.9,
            duration_ms=50.0,  # Below minimum threshold
            silence_duration_ms=0.0,
        )

        assert decision.should_endpoint is False
        assert "too short" in decision.reason

    def test_evaluate_endpointing_silence_timeout(self):
        """Test endpointing evaluation with silence timeout."""
        engine = PolicyEngine()

        decision = engine.evaluate_endpointing(
            is_speech=False,
            confidence=0.9,
            duration_ms=1000.0,
            silence_duration_ms=3000.0,  # Above timeout threshold
        )

        assert decision.should_endpoint is True
        assert "Silence timeout exceeded" in decision.reason

    def test_evaluate_endpointing_max_duration(self):
        """Test endpointing evaluation with max duration exceeded."""
        engine = PolicyEngine()

        decision = engine.evaluate_endpointing(
            is_speech=True,
            confidence=0.9,
            duration_ms=35000.0,  # Above max threshold
            silence_duration_ms=0.0,
        )

        assert decision.should_endpoint is True
        assert "Maximum speech duration exceeded" in decision.reason

    def test_evaluate_endpointing_disabled(self):
        """Test endpointing evaluation when disabled."""
        config = PolicyConfig()
        config.endpointing.enabled = False
        engine = PolicyEngine(config)

        decision = engine.evaluate_endpointing(
            is_speech=False,
            confidence=0.9,
            duration_ms=1000.0,
            silence_duration_ms=3000.0,
        )

        assert decision.should_endpoint is False
        assert "Endpointing disabled" in decision.reason

    def test_evaluate_barge_in_allowed(self):
        """Test barge-in evaluation when allowed."""
        engine = PolicyEngine()

        decision = engine.evaluate_barge_in(
            is_speech=True,
            confidence=0.9,
            current_playback=True,
            playback_duration_ms=1000.0,
        )

        assert decision.action == BargeInAction.ALLOW
        assert decision.confidence == 0.9

    def test_evaluate_barge_in_no_playback(self):
        """Test barge-in evaluation with no active playback."""
        engine = PolicyEngine()

        decision = engine.evaluate_barge_in(
            is_speech=True,
            confidence=0.9,
            current_playback=False,
            playback_duration_ms=0.0,
        )

        assert decision.action == BargeInAction.DENY
        assert "No active playback" in decision.reason

    def test_evaluate_barge_in_low_confidence(self):
        """Test barge-in evaluation with low confidence."""
        engine = PolicyEngine()

        decision = engine.evaluate_barge_in(
            is_speech=True,
            confidence=0.5,  # Below threshold
            current_playback=True,
            playback_duration_ms=1000.0,
        )

        assert decision.action == BargeInAction.DENY
        assert "Confidence too low" in decision.reason

    def test_evaluate_barge_in_disabled(self):
        """Test barge-in evaluation when disabled."""
        config = PolicyConfig()
        config.barge_in.enabled = False
        engine = PolicyEngine(config)

        decision = engine.evaluate_barge_in(
            is_speech=True,
            confidence=0.9,
            current_playback=True,
            playback_duration_ms=1000.0,
        )

        assert decision.action == BargeInAction.DENY
        assert "Barge-in disabled" in decision.reason

    def test_evaluate_wake_detected(self):
        """Test wake phrase evaluation when detected."""
        engine = PolicyEngine()

        decision = engine.evaluate_wake(
            is_wake=True,
            confidence=0.9,
            wake_phrase="hey assistant",
        )

        assert decision.is_wake is True
        assert decision.confidence == 0.9
        assert "Wake phrase detected" in decision.reason

    def test_evaluate_wake_not_detected(self):
        """Test wake phrase evaluation when not detected."""
        engine = PolicyEngine()

        decision = engine.evaluate_wake(
            is_wake=False,
            confidence=0.3,
            wake_phrase="",
        )

        assert decision.is_wake is False
        assert decision.confidence == 0.3
        assert "No wake phrase detected" in decision.reason

    def test_evaluate_wake_low_confidence(self):
        """Test wake phrase evaluation with low confidence."""
        engine = PolicyEngine()

        decision = engine.evaluate_wake(
            is_wake=True,
            confidence=0.5,  # Below threshold
            wake_phrase="hey assistant",
        )

        assert decision.is_wake is False
        assert "Confidence too low" in decision.reason

    def test_evaluate_wake_cooldown(self):
        """Test wake phrase evaluation during cooldown."""
        engine = PolicyEngine()

        # First wake detection
        decision1 = engine.evaluate_wake(
            is_wake=True,
            confidence=0.9,
            wake_phrase="hey assistant",
        )
        assert decision1.is_wake is True

        # Immediate second wake detection (should be blocked by cooldown)
        decision2 = engine.evaluate_wake(
            is_wake=True,
            confidence=0.9,
            wake_phrase="hey assistant",
        )
        assert decision2.is_wake is False
        assert "Cooldown active" in decision2.reason

    def test_evaluate_wake_disabled(self):
        """Test wake phrase evaluation when disabled."""
        config = PolicyConfig()
        config.wake.enabled = False
        engine = PolicyEngine(config)

        decision = engine.evaluate_wake(
            is_wake=True,
            confidence=0.9,
            wake_phrase="hey assistant",
        )

        assert decision.is_wake is False
        assert "Wake detection disabled" in decision.reason

    def test_state_management(self):
        """Test state management functionality."""
        engine = PolicyEngine()

        # Initial state
        assert engine.get_current_state() == EndpointingState.LISTENING

        # Change state
        engine.set_state(EndpointingState.PROCESSING)
        assert engine.get_current_state() == EndpointingState.PROCESSING

        # Reset state
        engine.reset_state()
        assert engine.get_current_state() == EndpointingState.LISTENING
        assert engine._is_speaking is False

    def test_performance_stats(self):
        """Test performance statistics."""
        engine = PolicyEngine()

        # Make some decisions to generate stats
        engine.evaluate_vad(b"test", 1000.0, {"confidence": 0.5})
        engine.evaluate_endpointing(True, 0.8, 1000.0, 0.0)

        stats = engine.get_performance_stats()

        assert "decision_count" in stats
        assert "total_decision_time" in stats
        assert "avg_decision_time_ms" in stats
        assert "current_state" in stats
        assert "is_speaking" in stats
        assert stats["decision_count"] >= 2

    def test_latency_validation(self):
        """Test latency validation."""
        engine = PolicyEngine()

        # Valid latencies
        assert engine.validate_latency(200.0, "e2e") is True
        assert engine.validate_latency(100.0, "barge_in") is True
        assert engine.validate_latency(500.0, "stt") is True
        assert engine.validate_latency(1000.0, "tts") is True

        # Invalid latencies
        assert engine.validate_latency(500.0, "e2e") is False
        assert engine.validate_latency(300.0, "barge_in") is False
        assert engine.validate_latency(1500.0, "stt") is False
        assert engine.validate_latency(3000.0, "tts") is False

    def test_config_update(self):
        """Test configuration update."""
        engine = PolicyEngine()

        # Update config
        new_config = PolicyConfig()
        new_config.vad.enabled = False
        engine.update_config(new_config)

        assert engine.config.vad.enabled is False
