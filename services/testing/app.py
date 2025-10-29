"""
Testing UI service for Audio Orchestrator.

Provides a Gradio interface for testing the complete audio pipeline
including preprocessing, transcription, orchestration, and synthesis.
"""

from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from services.common.audio_metrics import create_http_metrics
from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints
from services.common.structured_logging import configure_logging, get_logger
from services.common.tracing import setup_service_observability

# Import gradio with error handling
try:
    import gradio as gr

    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False
    gr = None

# Configure logging
configure_logging("info", json_logs=True, service_name="testing")
logger = get_logger(__name__, service_name="testing")

# FastAPI app for health checks
app = FastAPI(title="Testing UI Service", version="1.0.0")

# Health manager and observability
health_manager = HealthManager("testing")
_observability_manager = None
_http_metrics = {}

# HTTP client for service communication
client = httpx.AsyncClient(timeout=30.0)

# Service URLs
AUDIO_PREPROCESSOR_URL = "http://audio:9100"
STT_URL = "http://stt:9000"
ORCHESTRATOR_URL = "http://orchestrator:8200"
BARK_URL = "http://bark:7100"


class TranscriptRequest(BaseModel):
    """Request model for transcript processing."""

    transcript: str


class TranscriptResponse(BaseModel):
    """Response model for transcript processing."""

    response: str
    metadata: dict[str, Any] | None = None


async def test_pipeline(
    audio: str | None, text_input: str, voice_preset: str
) -> tuple[str, str, str]:
    """
    Test the complete audio pipeline.

    Args:
        audio: Audio file path (if provided)
        text_input: Text input as fallback
        voice_preset: Voice preset for TTS

    Returns:
        Tuple of (transcript, response, audio_output_path)
    """
    try:
        transcript = ""
        response = ""
        audio_output_path = ""

        if audio:
            # Audio input path
            logger.info("Processing audio input", extra={"audio_path": audio})

            # 1. Preprocess with MetricGAN+
            try:
                with Path(audio).open("rb") as f:
                    enhanced_response = await client.post(
                        f"{AUDIO_PREPROCESSOR_URL}/denoise", files={"audio": f}
                    )
                enhanced_response.raise_for_status()
                logger.info("Audio preprocessing completed")
            except Exception as e:
                logger.warning(
                    "Audio preprocessing failed, using raw audio",
                    extra={"error": str(e)},
                )
                enhanced_response = None

            # 2. Transcribe
            try:
                if enhanced_response:
                    transcript_response = await client.post(
                        f"{STT_URL}/transcribe",
                        files={"audio": enhanced_response.content},
                    )
                else:
                    with Path(audio).open("rb") as f:
                        transcript_response = await client.post(
                            f"{STT_URL}/transcribe", files={"audio": f}
                        )
                transcript_response.raise_for_status()
                transcript_data = transcript_response.json()
                transcript = transcript_data.get("text", "")
                logger.info(
                    "Transcription completed",
                    extra={"transcript_length": len(transcript)},
                )
            except Exception as e:
                logger.error("Transcription failed", extra={"error": str(e)})
                transcript = "Transcription failed"
        else:
            # Use text input
            transcript = text_input
            logger.info("Using text input", extra={"text_length": len(transcript)})

        if not transcript.strip():
            return "No input provided", "No response generated", ""

        # 3. Process with orchestrator
        try:
            orchestrator_response = await client.post(
                f"{ORCHESTRATOR_URL}/api/v1/transcripts",
                json={
                    "transcript": transcript,
                    "user_id": "test_user",
                    "channel_id": "test_channel",
                    "correlation_id": "test_correlation",
                },
            )
            orchestrator_response.raise_for_status()
            orchestrator_data = orchestrator_response.json()
            response = orchestrator_data.get("response_text", "")
            logger.info(
                "Orchestration completed", extra={"response_length": len(response)}
            )
        except Exception as e:
            logger.error("Orchestration failed", extra={"error": str(e)})
            response = f"Orchestration failed: {str(e)}"

        # 4. Synthesize with Bark TTS
        if response and response != "No response generated":
            try:
                tts_response = await client.post(
                    f"{BARK_URL}/synthesize",
                    json={"text": response, "voice": voice_preset},
                )
                tts_response.raise_for_status()

                # Save audio output
                import os
                import tempfile

                temp_dir = tempfile.gettempdir()
                audio_output_path = os.path.join(
                    temp_dir, f"output_{hash(response)}.wav"
                )
                with Path(audio_output_path).open("wb") as f:
                    f.write(tts_response.content)
                logger.info(
                    "TTS synthesis completed", extra={"output_path": audio_output_path}
                )
            except Exception as e:
                logger.error("TTS synthesis failed", extra={"error": str(e)})
                audio_output_path = ""

        return transcript, response, audio_output_path

    except Exception as e:
        logger.error("Pipeline test failed", extra={"error": str(e)})
        return f"Error: {str(e)}", "", ""


def create_gradio_interface() -> Any:
    """Create the Gradio interface for testing."""

    if not GRADIO_AVAILABLE:
        raise ImportError("Gradio is not available")

    # Create interface
    demo = gr.Interface(
        fn=test_pipeline,
        inputs=[
            gr.Audio(
                source="microphone",
                type="filepath",
                label="Speak (or upload audio file)",
            ),
            gr.Textbox(
                label="Or type text input",
                placeholder="Enter text to test the pipeline...",
                lines=3,
            ),
            gr.Dropdown(
                choices=[
                    "v2/en_speaker_0",
                    "v2/en_speaker_1",
                    "v2/en_speaker_2",
                    "v2/en_speaker_3",
                ],
                value="v2/en_speaker_0",
                label="Voice Preset",
            ),
        ],
        outputs=[
            gr.Textbox(label="Transcript", lines=2),
            gr.Textbox(label="Response", lines=4),
            gr.Audio(label="Audio Output"),
        ],
        title="Audio Orchestrator Testing Interface",
        description="Test the complete audio pipeline: preprocessing → transcription → orchestration → synthesis",
        theme="default",
        allow_flagging="never",
    )

    return demo


async def _check_service_health(url: str) -> bool:
    """Check if a service is healthy."""
    try:
        response = await client.get(f"{url}/health/ready", timeout=5.0)
        return bool(response.status_code == 200)
    except Exception:
        return False


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="testing",
    health_manager=health_manager,
    custom_components={
        "gradio_available": lambda: GRADIO_AVAILABLE,
    },
    custom_dependencies={
        "audio_preprocessor": lambda: _check_service_health(AUDIO_PREPROCESSOR_URL),
        "stt": lambda: _check_service_health(STT_URL),
        "orchestrator": lambda: _check_service_health(ORCHESTRATOR_URL),
        "tts": lambda: _check_service_health(BARK_URL),
    },
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())


@app.on_event("startup")  # type: ignore[misc]
async def startup_event() -> None:
    """Service startup event handler."""
    global _observability_manager, _http_metrics

    try:
        # Setup observability (tracing + metrics)
        _observability_manager = setup_service_observability("testing", "1.0.0")
        _observability_manager.instrument_fastapi(app)

        # Create service-specific metrics
        _http_metrics = create_http_metrics(_observability_manager)

        # Set observability manager in health manager
        health_manager.set_observability_manager(_observability_manager)

        logger.info("Testing UI service starting up")
        health_manager.mark_startup_complete()
    except Exception as exc:
        logger.error("Testing UI service startup failed", error=str(exc))
        # Continue without crashing - service will report not_ready


@app.on_event("shutdown")  # type: ignore[misc]
async def shutdown_event() -> None:
    """Service shutdown event handler."""
    logger.info("Testing UI service shutting down")
    await client.aclose()
    # Health manager will handle shutdown automatically


if __name__ == "__main__":
    import uvicorn

    # Create and launch Gradio interface
    demo = create_gradio_interface()

    # Launch in a separate thread
    import threading

    gradio_thread = threading.Thread(
        target=lambda: demo.launch(
            server_name="0.0.0.0", server_port=8080, share=False, quiet=True
        )
    )
    gradio_thread.daemon = True
    gradio_thread.start()

    # Start FastAPI server for health checks
    uvicorn.run(app, host="127.0.0.1", port=8081)
