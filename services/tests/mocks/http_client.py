"""Mock HTTP client for testing."""

import json
from typing import Any
from unittest import mock

import httpx


class MockHttpResponse:
    """Mock HTTP response for testing."""

    def __init__(
        self,
        status_code: int = 200,
        content: bytes | str = b"",
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        text: str | None = None,
    ):
        self.status_code = status_code
        self.content = content if isinstance(content, bytes) else content.encode()
        self.text = text or content if isinstance(content, str) else content.decode()
        self.headers = headers or {}
        self._json_data = json_data
        self._json_called = False

    def json(self) -> dict[str, Any]:
        """Return JSON data."""
        self._json_called = True
        if self._json_data is not None:
            return self._json_data
        try:
            return json.loads(self.text)
        except json.JSONDecodeError:
            return {}

    def raise_for_status(self) -> None:
        """Raise an exception for bad status codes."""
        if 400 <= self.status_code < 600:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=mock.Mock(), response=self
            )


class MockHttpClient:
    """Mock HTTP client for testing."""

    def __init__(self):
        self._responses = {}
        self._requests = []
        self._default_response = MockHttpResponse()

    def set_response(self, method: str, url: str, response: MockHttpResponse) -> None:
        """Set a response for a specific method and URL."""
        key = (method.upper(), url)
        self._responses[key] = response

    def set_default_response(self, response: MockHttpResponse) -> None:
        """Set the default response for unmatched requests."""
        self._default_response = response

    def get_requests(self) -> list[dict[str, Any]]:
        """Get all recorded requests."""
        return self._requests.copy()

    def clear_requests(self) -> None:
        """Clear recorded requests."""
        self._requests.clear()

    async def request(self, method: str, url: str, **kwargs) -> MockHttpResponse:
        """Mock request method."""
        # Record the request
        request_data = {"method": method.upper(), "url": url, "kwargs": kwargs}
        self._requests.append(request_data)

        # Return the appropriate response
        key = (method.upper(), url)
        if key in self._responses:
            return self._responses[key]

        return self._default_response

    async def get(self, url: str, **kwargs) -> MockHttpResponse:
        """Mock GET method."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> MockHttpResponse:
        """Mock POST method."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs) -> MockHttpResponse:
        """Mock PUT method."""
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> MockHttpResponse:
        """Mock DELETE method."""
        return await self.request("DELETE", url, **kwargs)

    async def patch(self, url: str, **kwargs) -> MockHttpResponse:
        """Mock PATCH method."""
        return await self.request("PATCH", url, **kwargs)

    async def aclose(self) -> None:
        """Mock close method."""
        pass


def create_mock_http_client() -> MockHttpClient:
    """Create a mock HTTP client for testing.

    Returns:
        Mock HTTP client
    """
    return MockHttpClient()


def create_mock_response(
    status_code: int = 200,
    content: bytes | str = b"",
    json_data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> MockHttpResponse:
    """Create a mock HTTP response for testing.

    Args:
        status_code: HTTP status code
        content: Response content
        json_data: JSON data to return
        headers: Response headers

    Returns:
        Mock HTTP response
    """
    return MockHttpResponse(
        status_code=status_code, content=content, json_data=json_data, headers=headers
    )


def create_mock_stt_response(
    transcript: str = "hey atlas, what's the weather",
    confidence: float = 0.95,
    language: str = "en",
) -> MockHttpResponse:
    """Create a mock STT response for testing.

    Args:
        transcript: Transcribed text
        confidence: Confidence score
        language: Detected language

    Returns:
        Mock STT response
    """
    json_data = {
        "transcript": transcript,
        "confidence": confidence,
        "language": language,
        "language_probability": 0.99,
        "start_time": 0.0,
        "end_time": 2.5,
        "no_speech_probability": 0.1,
    }

    return MockHttpResponse(
        status_code=200,
        json_data=json_data,
        headers={"Content-Type": "application/json"},
    )


def create_mock_llm_response(
    content: str = "The weather is sunny today with a temperature of 75°F.",
    model: str = "flan-t5-large",
) -> MockHttpResponse:
    """Create a mock LLM response for testing.

    Args:
        content: Response content
        model: Model name

    Returns:
        Mock LLM response
    """
    json_data = {
        "choices": [
            {
                "message": {"content": content, "role": "assistant"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
        "model": model,
    }

    return MockHttpResponse(
        status_code=200,
        json_data=json_data,
        headers={"Content-Type": "application/json"},
    )


def create_mock_tts_response(
    audio_data: bytes = b"mock audio data", content_type: str = "audio/wav"
) -> MockHttpResponse:
    """Create a mock TTS response for testing.

    Args:
        audio_data: Audio data bytes
        content_type: Content type

    Returns:
        Mock TTS response
    """
    return MockHttpResponse(
        status_code=200, content=audio_data, headers={"Content-Type": content_type}
    )


def create_mock_error_response(
    status_code: int = 500, error_message: str = "Internal Server Error"
) -> MockHttpResponse:
    """Create a mock error response for testing.

    Args:
        status_code: HTTP status code
        error_message: Error message

    Returns:
        Mock error response
    """
    json_data = {
        "error": {"message": error_message, "type": "server_error", "code": status_code}
    }

    return MockHttpResponse(
        status_code=status_code,
        json_data=json_data,
        headers={"Content-Type": "application/json"},
    )


def create_mock_timeout_response() -> MockHttpResponse:
    """Create a mock timeout response for testing.

    Returns:
        Mock timeout response
    """
    return MockHttpResponse(
        status_code=408,
        content="Request Timeout",
        headers={"Content-Type": "text/plain"},
    )
