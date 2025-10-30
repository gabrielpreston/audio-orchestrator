"""
JSON schema validation for control channel events.

This module provides schema validation for all control channel events
to ensure consistent wire protocol across all surface adapters.
"""

from __future__ import annotations

import json
from typing import Any

from services.common.structured_logging import get_logger


logger = get_logger(__name__)


# JSON Schema definitions for all control events
WAKE_DETECTED_SCHEMA = {
    "type": "object",
    "properties": {
        "event_type": {"type": "string", "const": "wake.detected"},
        "timestamp": {"type": "number"},
        "correlation_id": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "ts_device": {"type": "number"},
        "metadata": {"type": "object"},
    },
    "required": ["event_type", "timestamp", "confidence", "ts_device"],
    "additionalProperties": False,
}

VAD_START_SPEECH_SCHEMA = {
    "type": "object",
    "properties": {
        "event_type": {"type": "string", "const": "vad.start_speech"},
        "timestamp": {"type": "number"},
        "correlation_id": {"type": "string"},
        "ts_device": {"type": "number"},
        "metadata": {"type": "object"},
    },
    "required": ["event_type", "timestamp", "ts_device"],
    "additionalProperties": False,
}

VAD_END_SPEECH_SCHEMA = {
    "type": "object",
    "properties": {
        "event_type": {"type": "string", "const": "vad.end_speech"},
        "timestamp": {"type": "number"},
        "correlation_id": {"type": "string"},
        "ts_device": {"type": "number"},
        "duration_ms": {"type": "number", "minimum": 0.0},
        "metadata": {"type": "object"},
    },
    "required": ["event_type", "timestamp", "ts_device", "duration_ms"],
    "additionalProperties": False,
}

BARGE_IN_REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "event_type": {"type": "string", "const": "barge_in.request"},
        "timestamp": {"type": "number"},
        "correlation_id": {"type": "string"},
        "reason": {"type": "string"},
        "ts_device": {"type": "number"},
        "metadata": {"type": "object"},
    },
    "required": ["event_type", "timestamp", "reason", "ts_device"],
    "additionalProperties": False,
}

SESSION_STATE_SCHEMA = {
    "type": "object",
    "properties": {
        "event_type": {"type": "string", "const": "session.state"},
        "timestamp": {"type": "number"},
        "correlation_id": {"type": "string"},
        "action": {"type": "string", "enum": ["join", "leave", "mute", "unmute"]},
        "metadata": {"type": "object"},
    },
    "required": ["event_type", "timestamp", "action"],
    "additionalProperties": False,
}

ROUTE_CHANGE_SCHEMA = {
    "type": "object",
    "properties": {
        "event_type": {"type": "string", "const": "route.change"},
        "timestamp": {"type": "number"},
        "correlation_id": {"type": "string"},
        "input": {"type": "string"},
        "output": {"type": "string"},
        "metadata": {"type": "object"},
    },
    "required": ["event_type", "timestamp", "input", "output"],
    "additionalProperties": False,
}

PLAYBACK_CONTROL_SCHEMA = {
    "type": "object",
    "properties": {
        "event_type": {"type": "string", "const": "playback.control"},
        "timestamp": {"type": "number"},
        "correlation_id": {"type": "string"},
        "action": {"type": "string", "enum": ["start", "pause", "resume", "stop"]},
        "reason": {"type": "string"},
        "metadata": {"type": "object"},
    },
    "required": ["event_type", "timestamp", "action"],
    "additionalProperties": False,
}

ENDPOINTING_SCHEMA = {
    "type": "object",
    "properties": {
        "event_type": {"type": "string", "const": "endpointing"},
        "timestamp": {"type": "number"},
        "correlation_id": {"type": "string"},
        "state": {"type": "string", "enum": ["listening", "processing", "responding"]},
        "metadata": {"type": "object"},
    },
    "required": ["event_type", "timestamp", "state"],
    "additionalProperties": False,
}

TRANSCRIPT_PARTIAL_SCHEMA = {
    "type": "object",
    "properties": {
        "event_type": {"type": "string", "const": "transcript.partial"},
        "timestamp": {"type": "number"},
        "correlation_id": {"type": "string"},
        "text": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "ts_server": {"type": "number"},
        "metadata": {"type": "object"},
    },
    "required": ["event_type", "timestamp", "text", "confidence", "ts_server"],
    "additionalProperties": False,
}

WORD_TIMESTAMP_SCHEMA = {
    "type": "object",
    "properties": {
        "word": {"type": "string"},
        "start": {"type": "number", "minimum": 0.0},
        "end": {"type": "number", "minimum": 0.0},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "required": ["word", "start", "end"],
    "additionalProperties": False,
}

TRANSCRIPT_FINAL_SCHEMA = {
    "type": "object",
    "properties": {
        "event_type": {"type": "string", "const": "transcript.final"},
        "timestamp": {"type": "number"},
        "correlation_id": {"type": "string"},
        "text": {"type": "string"},
        "words": {
            "type": "array",
            "items": WORD_TIMESTAMP_SCHEMA,
        },
        "metadata": {"type": "object"},
    },
    "required": ["event_type", "timestamp", "text", "words"],
    "additionalProperties": False,
}

TELEMETRY_SNAPSHOT_SCHEMA = {
    "type": "object",
    "properties": {
        "event_type": {"type": "string", "const": "telemetry.snapshot"},
        "timestamp": {"type": "number"},
        "correlation_id": {"type": "string"},
        "rtt_ms": {"type": "number", "minimum": 0.0},
        "packet_loss_percent": {"type": "number", "minimum": 0.0, "maximum": 100.0},
        "jitter_ms": {"type": "number", "minimum": 0.0},
        "battery_temp": {"type": "number"},
        "e2e_latency_ms": {"type": "number", "minimum": 0.0},
        "barge_in_delay_ms": {"type": "number", "minimum": 0.0},
        "stt_partial_time_ms": {"type": "number", "minimum": 0.0},
        "tts_first_byte_ms": {"type": "number", "minimum": 0.0},
        "metadata": {"type": "object"},
    },
    "required": [
        "event_type",
        "timestamp",
        "rtt_ms",
        "packet_loss_percent",
        "jitter_ms",
    ],
    "additionalProperties": False,
}

ERROR_SCHEMA = {
    "type": "object",
    "properties": {
        "event_type": {"type": "string", "const": "error"},
        "timestamp": {"type": "number"},
        "correlation_id": {"type": "string"},
        "code": {"type": "string"},
        "message": {"type": "string"},
        "recoverable": {"type": "boolean"},
        "metadata": {"type": "object"},
    },
    "required": ["event_type", "timestamp", "code", "message", "recoverable"],
    "additionalProperties": False,
}

# Schema registry
EVENT_SCHEMAS = {
    "wake.detected": WAKE_DETECTED_SCHEMA,
    "vad.start_speech": VAD_START_SPEECH_SCHEMA,
    "vad.end_speech": VAD_END_SPEECH_SCHEMA,
    "barge_in.request": BARGE_IN_REQUEST_SCHEMA,
    "session.state": SESSION_STATE_SCHEMA,
    "route.change": ROUTE_CHANGE_SCHEMA,
    "playback.control": PLAYBACK_CONTROL_SCHEMA,
    "endpointing": ENDPOINTING_SCHEMA,
    "transcript.partial": TRANSCRIPT_PARTIAL_SCHEMA,
    "transcript.final": TRANSCRIPT_FINAL_SCHEMA,
    "telemetry.snapshot": TELEMETRY_SNAPSHOT_SCHEMA,
    "error": ERROR_SCHEMA,
}


class SchemaValidator:
    """Validates control channel events against JSON schemas."""

    def __init__(self) -> None:
        self.schemas = EVENT_SCHEMAS
        self._logger = get_logger(__name__)

    def validate_event(self, event_data: dict[str, Any]) -> bool:
        """Validate event data against its schema."""
        try:
            event_type = event_data.get("event_type")
            if not event_type:
                self._logger.warning("schema_validation.missing_event_type")
                return False

            if event_type not in self.schemas:
                self._logger.warning(
                    "schema_validation.unknown_event_type",
                    event_type=event_type,
                )
                return False

            schema = self.schemas[event_type]
            return self._validate_against_schema(event_data, schema)

        except Exception as e:
            self._logger.error("schema_validation.error", error=str(e))
            return False

    def _validate_against_schema(
        self, data: dict[str, Any], schema: dict[str, Any]
    ) -> bool:
        """Validate data against a JSON schema."""
        try:
            # Basic validation - check required fields
            required_fields = schema.get("required", [])
            for field in required_fields:
                if field not in data:
                    self._logger.warning(
                        "schema_validation.missing_required_field",
                        field=field,
                        event_type=data.get("event_type"),
                    )
                    return False

            # Check field types
            properties = schema.get("properties", {})
            for field, value in data.items():
                if field in properties:
                    field_schema = properties[field]
                    if not self._validate_field_type(value, field_schema):
                        self._logger.warning(
                            "schema_validation.invalid_field_type",
                            field=field,
                            value=value,
                            expected_type=field_schema.get("type"),
                        )
                        return False

            # Check enum values
            for field, value in data.items():
                if field in properties:
                    field_schema = properties[field]
                    if "enum" in field_schema and value not in field_schema["enum"]:
                        self._logger.warning(
                            "schema_validation.invalid_enum_value",
                            field=field,
                            value=value,
                            allowed_values=field_schema["enum"],
                        )
                        return False

            # Check numeric constraints
            for field, value in data.items():
                if field in properties:
                    field_schema = properties[field]
                    if isinstance(value, (int, float)):
                        if (
                            "minimum" in field_schema
                            and value < field_schema["minimum"]
                        ):
                            self._logger.warning(
                                "schema_validation.value_below_minimum",
                                field=field,
                                value=value,
                                minimum=field_schema["minimum"],
                            )
                            return False
                        if (
                            "maximum" in field_schema
                            and value > field_schema["maximum"]
                        ):
                            self._logger.warning(
                                "schema_validation.value_above_maximum",
                                field=field,
                                value=value,
                                maximum=field_schema["maximum"],
                            )
                            return False

            return True

        except Exception as e:
            self._logger.error("schema_validation.field_validation_error", error=str(e))
            return False

    def _validate_field_type(self, value: Any, field_schema: dict[str, Any]) -> bool:
        """Validate a field value against its type schema."""
        expected_type = field_schema.get("type")
        if not expected_type:
            return True

        if (
            (expected_type == "string" and not isinstance(value, str))
            or (expected_type == "number" and not isinstance(value, (int, float)))
            or (
                (expected_type == "boolean" and not isinstance(value, bool))
                or (expected_type == "array" and not isinstance(value, list))
            )
            or (expected_type == "object" and not isinstance(value, dict))
        ):
            return False

        return True

    def get_schema(self, event_type: str) -> dict[str, Any] | None:
        """Get schema for a specific event type."""
        return self.schemas.get(event_type)

    def get_supported_event_types(self) -> list[str]:
        """Get list of supported event types."""
        return list(self.schemas.keys())

    def validate_event_json(self, event_json: str) -> bool:
        """Validate event from JSON string."""
        try:
            event_data = json.loads(event_json)
            return self.validate_event(event_data)
        except json.JSONDecodeError as e:
            self._logger.warning("schema_validation.invalid_json", error=str(e))
            return False


# Global validator instance
validator = SchemaValidator()


def validate_control_event(event_data: dict[str, Any]) -> bool:
    """Validate a control event against its schema."""
    return validator.validate_event(event_data)


def validate_control_event_json(event_json: str) -> bool:
    """Validate a control event from JSON string."""
    return validator.validate_event_json(event_json)


def get_event_schema(event_type: str) -> dict[str, Any] | None:
    """Get schema for a specific event type."""
    return validator.get_schema(event_type)


def get_supported_event_types() -> list[str]:
    """Get list of supported event types."""
    return validator.get_supported_event_types()
