"""
Policy engine for voice assistant behavior control.

This module implements the policy engine that makes decisions about
VAD, endpointing, barge-in, and other voice interaction behaviors.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from services.common.logging import get_logger

from .policy_config import PolicyConfig

logger = get_logger(__name__)


class EndpointingState(Enum):
    """Endpointing state machine."""

    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"


class BargeInAction(Enum):
    """Barge-in action types."""

    ALLOW = "allow"
    DENY = "deny"
    GRACEFUL = "graceful"


@dataclass
class VADDecision:
    """VAD decision result."""

    is_speech: bool
    confidence: float
    reason: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class EndpointingDecision:
    """Endpointing decision result."""

    should_endpoint: bool
    reason: str
    confidence: float
    duration_ms: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class BargeInDecision:
    """Barge-in decision result."""

    action: BargeInAction
    reason: str
    confidence: float
    response_delay_ms: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class WakeDecision:
    """Wake phrase decision result."""

    is_wake: bool
    confidence: float
    reason: str
    timestamp: float = field(default_factory=time.time)


class PolicyEngine:
    """Policy engine for voice assistant behavior control."""

    def __init__(self, config: PolicyConfig | None = None) -> None:
        self.config = config or PolicyConfig()
        self._logger = get_logger(__name__)

        # State tracking
        self._current_state = EndpointingState.LISTENING
        self._last_wake_time = 0.0
        self._last_speech_time = 0.0
        self._speech_start_time = 0.0
        self._silence_start_time = 0.0
        self._is_speaking = False

        # Performance tracking
        self._decision_count = 0
        self._total_decision_time = 0.0

    def evaluate_vad(
        self, audio_data: bytes, rms: float, metadata: dict[str, Any]
    ) -> VADDecision:
        """Evaluate voice activity detection."""
        start_time = time.time()

        try:
            # Extract metadata
            confidence = metadata.get("confidence", 0.5)
            duration_ms = metadata.get("duration_ms", 20.0)

            # Apply VAD policy
            if not self.config.vad.enabled:
                return VADDecision(
                    is_speech=False,
                    confidence=0.0,
                    reason="VAD disabled",
                )

            # Calculate speech probability based on RMS and confidence
            speech_probability = self._calculate_speech_probability(rms, confidence)

            # Apply sensitivity threshold
            threshold = 1.0 - self.config.vad.sensitivity
            is_speech = speech_probability > threshold

            # Apply minimum speech duration
            if is_speech and not self._is_speaking:
                if duration_ms < self.config.vad.speech_threshold_ms:
                    is_speech = False
                    reason = f"Speech duration {duration_ms}ms below threshold {self.config.vad.speech_threshold_ms}ms"
                else:
                    self._is_speaking = True
                    self._speech_start_time = time.time()
                    reason = "Speech detected"
            elif not is_speech and self._is_speaking:
                # Check silence duration
                silence_duration = time.time() - self._last_speech_time
                if silence_duration * 1000 < self.config.vad.silence_threshold_ms:
                    is_speech = True  # Still in speech
                    reason = f"Silence duration {silence_duration*1000:.1f}ms below threshold {self.config.vad.silence_threshold_ms}ms"
                else:
                    self._is_speaking = False
                    self._silence_start_time = time.time()
                    reason = "Speech ended"
            else:
                reason = "No change in speech state"

            # Track performance
            decision_time = time.time() - start_time
            self._decision_count += 1
            self._total_decision_time += decision_time

            if self._is_speaking:
                self._last_speech_time = time.time()

            self._logger.debug(
                "policy_engine.vad_decision",
                is_speech=is_speech,
                confidence=confidence,
                speech_probability=speech_probability,
                threshold=threshold,
                reason=reason,
                decision_time_ms=decision_time * 1000,
            )

            return VADDecision(
                is_speech=is_speech,
                confidence=confidence,
                reason=reason,
            )

        except Exception as e:
            self._logger.error("policy_engine.vad_evaluation_failed", error=str(e))
            return VADDecision(
                is_speech=False,
                confidence=0.0,
                reason=f"VAD evaluation failed: {str(e)}",
            )

    def evaluate_endpointing(
        self,
        is_speech: bool,
        confidence: float,
        duration_ms: float,
        silence_duration_ms: float,
    ) -> EndpointingDecision:
        """Evaluate endpointing decision."""
        start_time = time.time()

        try:
            if not self.config.endpointing.enabled:
                return EndpointingDecision(
                    should_endpoint=False,
                    reason="Endpointing disabled",
                    confidence=confidence,
                    duration_ms=duration_ms,
                )

            should_endpoint = False
            reason = ""

            # Check maximum speech duration
            if duration_ms > self.config.endpointing.max_speech_duration_ms:
                should_endpoint = True
                reason = f"Maximum speech duration exceeded: {duration_ms}ms > {self.config.endpointing.max_speech_duration_ms}ms"

            # Check minimum speech duration
            elif duration_ms < self.config.endpointing.min_speech_duration_ms:
                should_endpoint = False
                reason = f"Speech duration too short: {duration_ms}ms < {self.config.endpointing.min_speech_duration_ms}ms"

            # Check silence timeout
            elif (
                not is_speech
                and silence_duration_ms > self.config.endpointing.silence_timeout_ms
            ):
                should_endpoint = True
                reason = f"Silence timeout exceeded: {silence_duration_ms}ms > {self.config.endpointing.silence_timeout_ms}ms"

            # Check confidence threshold
            elif confidence < self.config.endpointing.confidence_threshold:
                should_endpoint = False
                reason = f"Confidence too low: {confidence} < {self.config.endpointing.confidence_threshold}"

            # Update state
            if should_endpoint:
                if self._current_state == EndpointingState.LISTENING:
                    self._current_state = EndpointingState.PROCESSING
                elif self._current_state == EndpointingState.PROCESSING:
                    self._current_state = EndpointingState.RESPONDING

            # Track performance
            decision_time = time.time() - start_time
            self._decision_count += 1
            self._total_decision_time += decision_time

            self._logger.debug(
                "policy_engine.endpointing_decision",
                should_endpoint=should_endpoint,
                confidence=confidence,
                duration_ms=duration_ms,
                silence_duration_ms=silence_duration_ms,
                current_state=self._current_state.value,
                reason=reason,
                decision_time_ms=decision_time * 1000,
            )

            return EndpointingDecision(
                should_endpoint=should_endpoint,
                reason=reason,
                confidence=confidence,
                duration_ms=duration_ms,
            )

        except Exception as e:
            self._logger.error(
                "policy_engine.endpointing_evaluation_failed", error=str(e)
            )
            return EndpointingDecision(
                should_endpoint=False,
                reason=f"Endpointing evaluation failed: {str(e)}",
                confidence=confidence,
                duration_ms=duration_ms,
            )

    def evaluate_barge_in(
        self,
        is_speech: bool,
        confidence: float,
        current_playback: bool,
        playback_duration_ms: float,
    ) -> BargeInDecision:
        """Evaluate barge-in decision."""
        start_time = time.time()

        try:
            if not self.config.barge_in.enabled:
                return BargeInDecision(
                    action=BargeInAction.DENY,
                    reason="Barge-in disabled",
                    confidence=confidence,
                    response_delay_ms=0.0,
                )

            if not current_playback:
                return BargeInDecision(
                    action=BargeInAction.DENY,
                    reason="No active playback",
                    confidence=confidence,
                    response_delay_ms=0.0,
                )

            if not is_speech:
                return BargeInDecision(
                    action=BargeInAction.DENY,
                    reason="No speech detected",
                    confidence=confidence,
                    response_delay_ms=0.0,
                )

            # Check confidence threshold
            if confidence < self.config.barge_in.detection_threshold:
                return BargeInDecision(
                    action=BargeInAction.DENY,
                    reason=f"Confidence too low: {confidence} < {self.config.barge_in.detection_threshold}",
                    confidence=confidence,
                    response_delay_ms=0.0,
                )

            # Check maximum interruption duration
            if playback_duration_ms > self.config.barge_in.max_interruption_duration_ms:
                return BargeInDecision(
                    action=BargeInAction.DENY,
                    reason=f"Playback too long: {playback_duration_ms}ms > {self.config.barge_in.max_interruption_duration_ms}ms",
                    confidence=confidence,
                    response_delay_ms=0.0,
                )

            # Determine barge-in mode
            if self.config.barge_in.mode.value == "immediate":
                action = BargeInAction.ALLOW
                reason = "Immediate barge-in allowed"
                response_delay_ms = 0.0
            elif self.config.barge_in.mode.value == "graceful":
                action = BargeInAction.GRACEFUL
                reason = "Graceful barge-in allowed"
                response_delay_ms = self.config.barge_in.response_delay_ms
            else:
                action = BargeInAction.DENY
                reason = "Barge-in mode disabled"
                response_delay_ms = 0.0

            # Track performance
            decision_time = time.time() - start_time
            self._decision_count += 1
            self._total_decision_time += decision_time

            self._logger.debug(
                "policy_engine.barge_in_decision",
                action=action.value,
                confidence=confidence,
                current_playback=current_playback,
                playback_duration_ms=playback_duration_ms,
                reason=reason,
                response_delay_ms=response_delay_ms,
                decision_time_ms=decision_time * 1000,
            )

            return BargeInDecision(
                action=action,
                reason=reason,
                confidence=confidence,
                response_delay_ms=response_delay_ms,
            )

        except Exception as e:
            self._logger.error("policy_engine.barge_in_evaluation_failed", error=str(e))
            return BargeInDecision(
                action=BargeInAction.DENY,
                reason=f"Barge-in evaluation failed: {str(e)}",
                confidence=confidence,
                response_delay_ms=0.0,
            )

    def evaluate_wake(
        self,
        is_wake: bool,
        confidence: float,
        wake_phrase: str,
    ) -> WakeDecision:
        """Evaluate wake phrase decision."""
        start_time = time.time()

        try:
            if not self.config.wake.enabled:
                return WakeDecision(
                    is_wake=False,
                    confidence=confidence,
                    reason="Wake detection disabled",
                )

            current_time = time.time()

            # Check confidence threshold
            if confidence < self.config.wake.confidence_threshold:
                return WakeDecision(
                    is_wake=False,
                    confidence=confidence,
                    reason=f"Confidence too low: {confidence} < {self.config.wake.confidence_threshold}",
                )

            # Check cooldown
            time_since_last_wake = (current_time - self._last_wake_time) * 1000.0
            if time_since_last_wake < self.config.wake.cooldown_ms:
                return WakeDecision(
                    is_wake=False,
                    confidence=confidence,
                    reason=f"Cooldown active: {time_since_last_wake:.1f}ms < {self.config.wake.cooldown_ms}ms",
                )

            # Check timeout
            if is_wake:
                self._last_wake_time = current_time
                reason = f"Wake phrase detected: '{wake_phrase}'"
            else:
                reason = "No wake phrase detected"

            # Track performance
            decision_time = time.time() - start_time
            self._decision_count += 1
            self._total_decision_time += decision_time

            self._logger.debug(
                "policy_engine.wake_decision",
                is_wake=is_wake,
                confidence=confidence,
                wake_phrase=wake_phrase,
                time_since_last_wake=time_since_last_wake,
                reason=reason,
                decision_time_ms=decision_time * 1000,
            )

            return WakeDecision(
                is_wake=is_wake,
                confidence=confidence,
                reason=reason,
            )

        except Exception as e:
            self._logger.error("policy_engine.wake_evaluation_failed", error=str(e))
            return WakeDecision(
                is_wake=False,
                confidence=confidence,
                reason=f"Wake evaluation failed: {str(e)}",
            )

    def _calculate_speech_probability(self, rms: float, confidence: float) -> float:
        """Calculate speech probability from RMS and confidence."""
        # Normalize RMS to 0-1 range (assuming typical range of 0-10000)
        normalized_rms = min(rms / 10000.0, 1.0)

        # Combine RMS and confidence with weights
        speech_probability = (normalized_rms * 0.7) + (confidence * 0.3)

        return min(max(speech_probability, 0.0), 1.0)

    def get_current_state(self) -> EndpointingState:
        """Get current endpointing state."""
        return self._current_state

    def set_state(self, state: EndpointingState) -> None:
        """Set current endpointing state."""
        self._current_state = state
        self._logger.debug("policy_engine.state_changed", new_state=state.value)

    def reset_state(self) -> None:
        """Reset to listening state."""
        self._current_state = EndpointingState.LISTENING
        self._is_speaking = False
        self._speech_start_time = 0.0
        self._silence_start_time = 0.0
        self._logger.debug("policy_engine.state_reset")

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        avg_decision_time = (
            self._total_decision_time / self._decision_count
            if self._decision_count > 0
            else 0.0
        )

        return {
            "decision_count": self._decision_count,
            "total_decision_time": self._total_decision_time,
            "avg_decision_time_ms": avg_decision_time * 1000,
            "current_state": self._current_state.value,
            "is_speaking": self._is_speaking,
        }

    def update_config(self, config: PolicyConfig) -> None:
        """Update policy configuration."""
        self.config = config
        self._logger.info("policy_engine.config_updated")

    def validate_latency(self, latency_ms: float, operation: str) -> bool:
        """Validate latency against policy limits."""
        if operation == "e2e" and latency_ms > self.config.latency.max_e2e_latency_ms:
            self._logger.warning(
                "policy_engine.latency_exceeded",
                operation=operation,
                latency_ms=latency_ms,
                limit_ms=self.config.latency.max_e2e_latency_ms,
            )
            return False
        elif (
            operation == "barge_in"
            and latency_ms > self.config.latency.max_barge_in_delay_ms
        ):
            self._logger.warning(
                "policy_engine.latency_exceeded",
                operation=operation,
                latency_ms=latency_ms,
                limit_ms=self.config.latency.max_barge_in_delay_ms,
            )
            return False
        elif operation == "stt" and latency_ms > self.config.latency.max_stt_latency_ms:
            self._logger.warning(
                "policy_engine.latency_exceeded",
                operation=operation,
                latency_ms=latency_ms,
                limit_ms=self.config.latency.max_stt_latency_ms,
            )
            return False
        elif operation == "tts" and latency_ms > self.config.latency.max_tts_latency_ms:
            self._logger.warning(
                "policy_engine.latency_exceeded",
                operation=operation,
                latency_ms=latency_ms,
                limit_ms=self.config.latency.max_tts_latency_ms,
            )
            return False

        return True
