"""Test helper utilities for discord-voice-lab."""

import json
import random
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pytest


def create_mock_audio_data(
    duration: float = 1.0,
    sample_rate: int = 48000,
    channels: int = 1,
    dtype: np.dtype = np.float32,
) -> np.ndarray:
    """Create mock audio data for testing.

    Args:
        duration: Duration in seconds
        sample_rate: Sample rate in Hz
        channels: Number of audio channels
        dtype: NumPy data type

    Returns:
        Mock audio data as numpy array
    """
    samples = int(duration * sample_rate * channels)
    return np.random.randn(samples).astype(dtype)


def create_mock_wav_file(
    file_path: Path, duration: float = 1.0, sample_rate: int = 48000, channels: int = 1
) -> Path:
    """Create a mock WAV file for testing.

    Args:
        file_path: Path where to create the file
        duration: Duration in seconds
        sample_rate: Sample rate in Hz
        channels: Number of audio channels

    Returns:
        Path to the created file
    """
    import wave

    audio_data = create_mock_audio_data(duration, sample_rate, channels, np.int16)

    with wave.open(str(file_path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())

    return file_path


def create_mock_correlation_id(prefix: str = "test") -> str:
    """Create a mock correlation ID for testing.

    Args:
        prefix: Prefix for the correlation ID

    Returns:
        Mock correlation ID
    """
    timestamp = int(time.time() * 1000)
    random_part = random.randint(1000, 9999)
    return f"{prefix}-{timestamp}-{random_part}"


def create_mock_discord_message(
    content: str = "test message",
    author_id: int = 123456789,
    channel_id: int = 987654321,
    guild_id: int = 111222333,
) -> Dict[str, Any]:
    """Create mock Discord message data for testing.

    Args:
        content: Message content
        author_id: Author user ID
        channel_id: Channel ID
        guild_id: Guild ID

    Returns:
        Mock Discord message data
    """
    return {
        "id": random.randint(100000000000000000, 999999999999999999),
        "content": content,
        "author": {"id": author_id, "username": "testuser", "discriminator": "0001"},
        "channel_id": channel_id,
        "guild_id": guild_id,
        "timestamp": time.time(),
        "edited_timestamp": None,
        "tts": False,
        "mention_everyone": False,
        "mentions": [],
        "mention_roles": [],
        "attachments": [],
        "embeds": [],
        "reactions": [],
    }


def create_mock_voice_state(
    user_id: int = 123456789,
    channel_id: int = 987654321,
    guild_id: int = 111222333,
    deaf: bool = False,
    mute: bool = False,
    self_deaf: bool = False,
    self_mute: bool = False,
) -> Dict[str, Any]:
    """Create mock Discord voice state data for testing.

    Args:
        user_id: User ID
        channel_id: Voice channel ID
        guild_id: Guild ID
        deaf: Whether user is deafened
        mute: Whether user is muted
        self_deaf: Whether user is self-deafened
        self_mute: Whether user is self-muted

    Returns:
        Mock Discord voice state data
    """
    return {
        "user_id": user_id,
        "channel_id": channel_id,
        "guild_id": guild_id,
        "deaf": deaf,
        "mute": mute,
        "self_deaf": self_deaf,
        "self_mute": self_mute,
        "session_id": f"session_{random.randint(100000, 999999)}",
    }


def create_mock_transcription_result(
    text: str = "hey atlas, what's the weather",
    confidence: float = 0.95,
    language: str = "en",
    start_time: float = 0.0,
    end_time: float = 2.5,
) -> Dict[str, Any]:
    """Create mock transcription result for testing.

    Args:
        text: Transcribed text
        confidence: Confidence score
        language: Detected language
        start_time: Start time in seconds
        end_time: End time in seconds

    Returns:
        Mock transcription result
    """
    return {
        "text": text,
        "confidence": confidence,
        "language": language,
        "language_probability": 0.99,
        "start_time": start_time,
        "end_time": end_time,
        "no_speech_probability": 0.1,
        "segments": [
            {"text": text, "start": start_time, "end": end_time, "no_speech_prob": 0.1}
        ],
    }


def create_mock_llm_response(
    content: str = "The weather is sunny today with a temperature of 75°F.",
    model: str = "llama-2-7b",
    usage: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Create mock LLM response for testing.

    Args:
        content: Response content
        model: Model name
        usage: Token usage information

    Returns:
        Mock LLM response
    """
    if usage is None:
        usage = {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25}

    return {
        "choices": [
            {
                "message": {"content": content, "role": "assistant"},
                "finish_reason": "stop",
            }
        ],
        "usage": usage,
        "model": model,
    }


def create_mock_tts_response(
    audio_data: bytes = b"mock audio data",
    sample_rate: int = 22050,
    format: str = "wav",
    duration: float = 2.5,
) -> Dict[str, Any]:
    """Create mock TTS response for testing.

    Args:
        audio_data: Audio data bytes
        sample_rate: Sample rate in Hz
        format: Audio format
        duration: Duration in seconds

    Returns:
        Mock TTS response
    """
    return {
        "audio_data": audio_data,
        "sample_rate": sample_rate,
        "format": format,
        "duration": duration,
        "voice": "en_US-amy-medium",
    }


def create_mock_mcp_tool_call(
    tool: str = "weather_check",
    parameters: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create mock MCP tool call for testing.

    Args:
        tool: Tool name
        parameters: Tool parameters
        correlation_id: Correlation ID

    Returns:
        Mock MCP tool call
    """
    if parameters is None:
        parameters = {"location": "San Francisco", "date": "today"}

    if correlation_id is None:
        correlation_id = create_mock_correlation_id("mcp")

    return {"tool": tool, "parameters": parameters, "correlation_id": correlation_id}


def create_mock_mcp_tool_response(
    success: bool = True,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create mock MCP tool response for testing.

    Args:
        success: Whether the tool call was successful
        result: Tool result data
        error: Error message if unsuccessful
        correlation_id: Correlation ID

    Returns:
        Mock MCP tool response
    """
    if correlation_id is None:
        correlation_id = create_mock_correlation_id("mcp")

    response = {"success": success, "correlation_id": correlation_id}

    if success and result is not None:
        response["result"] = result
    elif not success and error is not None:
        response["error"] = error

    return response


def assert_audio_data_valid(
    audio_data: np.ndarray,
    expected_sample_rate: int = 48000,
    expected_channels: int = 1,
    expected_dtype: np.dtype = np.float32,
) -> None:
    """Assert that audio data is valid for testing.

    Args:
        audio_data: Audio data to validate
        expected_sample_rate: Expected sample rate
        expected_channels: Expected number of channels
        expected_dtype: Expected data type
    """
    assert isinstance(audio_data, np.ndarray), "Audio data must be a numpy array"
    assert (
        audio_data.dtype == expected_dtype
    ), f"Expected dtype {expected_dtype}, got {audio_data.dtype}"
    assert len(audio_data.shape) == 1, "Audio data must be 1D"
    assert len(audio_data) > 0, "Audio data cannot be empty"


def assert_correlation_id_valid(correlation_id: str) -> None:
    """Assert that a correlation ID is valid.

    Args:
        correlation_id: Correlation ID to validate
    """
    assert isinstance(correlation_id, str), "Correlation ID must be a string"
    assert len(correlation_id) > 0, "Correlation ID cannot be empty"
    assert "-" in correlation_id, "Correlation ID must contain hyphens"


def assert_http_response_valid(
    response: Any,
    expected_status: int = 200,
    expected_content_type: Optional[str] = None,
) -> None:
    """Assert that an HTTP response is valid.

    Args:
        response: HTTP response to validate
        expected_status: Expected status code
        expected_content_type: Expected content type
    """
    assert hasattr(response, "status_code"), "Response must have status_code attribute"
    assert (
        response.status_code == expected_status
    ), f"Expected status {expected_status}, got {response.status_code}"

    if expected_content_type is not None:
        assert hasattr(response, "headers"), "Response must have headers attribute"
        content_type = response.headers.get("Content-Type", "")
        assert (
            expected_content_type in content_type
        ), f"Expected content type {expected_content_type}, got {content_type}"


def load_test_fixture(fixture_name: str) -> Dict[str, Any]:
    """Load a test fixture from the fixtures directory.

    Args:
        fixture_name: Name of the fixture file (without extension)

    Returns:
        Loaded fixture data
    """
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    fixture_file = fixtures_dir / f"{fixture_name}.json"

    if not fixture_file.exists():
        pytest.skip(f"Fixture {fixture_name} not found")

    with open(fixture_file, "r") as f:
        return json.load(f)


def save_test_fixture(fixture_name: str, data: Dict[str, Any]) -> None:
    """Save test data as a fixture.

    Args:
        fixture_name: Name of the fixture file (without extension)
        data: Data to save
    """
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)

    fixture_file = fixtures_dir / f"{fixture_name}.json"
    with open(fixture_file, "w") as f:
        json.dump(data, f, indent=2)
