"""
Testing UI service for Audio Orchestrator.

Provides a Gradio interface for testing the complete audio pipeline
including preprocessing, transcription, orchestration, and synthesis.
"""

import tempfile
from pathlib import Path
from typing import Any

import httpx

from services.common.app_factory import create_service_app
from services.common.config import (
    LoggingConfig,
    get_service_preset,
)
from services.common.config.loader import get_env_with_default
from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints
from services.common.audio_enhancement import AudioEnhancer
from services.common.structured_logging import configure_logging, get_logger
from services.common.tracing import get_observability_manager

# Import gradio with strict fail-fast
try:
    import gradio as gr
except ImportError as exc:
    raise ImportError(
        f"Required UI framework not available: {exc}. "
        "Testing service requires Gradio. Use python-ml base image or "
        "explicitly install gradio."
    ) from exc

# Load configuration using standard config classes
_config_preset = get_service_preset("testing")
_logging_config = LoggingConfig(**_config_preset["logging"])

# Configure logging using config class
configure_logging(
    _logging_config.level,
    json_logs=_logging_config.json_logs,
    service_name="testing",
)
logger = get_logger(__name__, service_name="testing")

# Health manager and observability
health_manager = HealthManager("testing")
_observability_manager = None


async def _startup() -> None:
    """Service startup event handler."""
    global _observability_manager

    try:
        # Get observability manager (factory already setup observability)
        _observability_manager = get_observability_manager("testing")

        # HTTP metrics already available from app_factory via app.state.http_metrics
        # No service-specific metrics needed for testing service

        # Set observability manager in health manager
        health_manager.set_observability_manager(_observability_manager)

        # Initialize audio enhancer for denoising (optional component)
        try:
            import os

            enable_enhancement = os.getenv(
                "TESTING_ENABLE_AUDIO_ENHANCEMENT", "true"
            ).lower() in (
                "true",
                "1",
                "yes",
            )
            audio_enhancer = AudioEnhancer(
                enable_metricgan=enable_enhancement,
                device=os.getenv("TESTING_ENHANCEMENT_DEVICE", "cpu"),
            )
            app.state.audio_enhancer = audio_enhancer
            logger.info(
                "testing.audio_enhancer_initialized",
                enable_metricgan=enable_enhancement,
            )
        except Exception as exc:
            logger.warning("testing.audio_enhancer_init_failed", error=str(exc))
            app.state.audio_enhancer = None

        logger.info("Testing UI service starting up")
        health_manager.mark_startup_complete()
    except Exception as exc:
        logger.error("Testing UI service startup failed", error=str(exc))
        # Continue without crashing - service will report not_ready


async def _shutdown() -> None:
    """Service shutdown event handler."""
    logger.info("Testing UI service shutting down")
    await client.aclose()
    # Health manager will handle shutdown automatically


# Create app using factory pattern
app = create_service_app(
    "testing",
    "1.0.0",
    title="Testing UI Service",
    startup_callback=_startup,
    shutdown_callback=_shutdown,
)


# HTTP client for service communication
client = httpx.AsyncClient(timeout=30.0)

# Service URLs (loaded from environment with defaults)
STT_BASE_URL = get_env_with_default("STT_BASE_URL", "http://stt:9000", str)
ORCHESTRATOR_BASE_URL = get_env_with_default(
    "ORCHESTRATOR_BASE_URL", "http://orchestrator:8200", str
)
TTS_BASE_URL = get_env_with_default("TTS_BASE_URL", "http://bark:7100", str)


async def run_pipeline(
    audio: str | None, text_input: str, voice_preset: str
) -> tuple[str, str, str | None]:
    """
    Run the complete audio pipeline.

    Args:
        audio: Audio file path (if provided)
        text_input: Text input as fallback
        voice_preset: Voice preset for TTS

    Returns:
        Tuple of (transcript, response, audio_output_path)
            audio_output_path: Temporary file path for Gradio Audio component.
            Uses tempfile.NamedTemporaryFile(delete=False) because Gradio reads
            files asynchronously after function returns. OS will clean up temp files
            automatically (standard behavior).

    Note:
        Audio output is saved to temporary files using Python's tempfile API.
        Files use delete=False because Gradio requires async file access, so
        cleanup relies on OS-level temporary file management rather than immediate
        deletion.
    """
    try:
        transcript = ""
        response = ""
        audio_output_path: str | None = None

        if audio:
            # Audio input path
            logger.info("Processing audio input", extra={"audio_path": audio})

            # 1. Preprocess with MetricGAN+
            try:
                # Read bytes before sending (file closes automatically after read)
                with Path(audio).open("rb") as f:
                    audio_bytes = f.read()

                # Use AudioEnhancer library directly
                audio_enhancer = getattr(app.state, "audio_enhancer", None)
                if audio_enhancer is not None:
                    enhanced_audio_bytes = await audio_enhancer.enhance_audio_bytes(
                        audio_bytes
                    )
                    logger.info("Audio preprocessing completed")
                    enhanced_response_content = enhanced_audio_bytes
                else:
                    logger.warning("Audio enhancer not available, using raw audio")
                    enhanced_response_content = None
            except Exception as e:
                logger.warning(
                    "Audio preprocessing failed, using raw audio",
                    extra={"error": str(e)},
                )
                enhanced_response_content = None

            # 2. Transcribe
            try:
                if enhanced_response_content:
                    transcript_response = await client.post(
                        f"{STT_BASE_URL}/transcribe",
                        files={
                            "file": (
                                "audio.wav",
                                enhanced_response_content,
                                "audio/wav",
                            )
                        },
                    )
                else:
                    with Path(audio).open("rb") as f:
                        audio_bytes = f.read()
                    transcript_response = await client.post(
                        f"{STT_BASE_URL}/transcribe",
                        files={"file": ("audio.wav", audio_bytes, "audio/wav")},
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
            return "No input provided", "No response generated", None

        # 3. Process with orchestrator
        try:
            orchestrator_response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/api/v1/transcripts",
                json={
                    "transcript": transcript,
                    "user_id": "test_user",
                    "channel_id": "test_channel",
                    "correlation_id": "test_correlation",
                },
            )
            orchestrator_response.raise_for_status()
            orchestrator_data = orchestrator_response.json()

            # Check for actual error in response (success field)
            if orchestrator_data.get("success") is False:
                error_msg = orchestrator_data.get("error", "Unknown error")
                correlation_id = orchestrator_data.get("correlation_id", "unknown")
                logger.error(
                    "Orchestration failed",
                    extra={
                        "error": error_msg,
                        "correlation_id": correlation_id,
                    },
                )
                response = f"Orchestration failed: {error_msg}"
                audio_data_b64 = None
                audio_format = None
            else:
                # Success - extract response text and audio
                response = orchestrator_data.get("response_text", "")

                # Check if orchestrator provided audio data (from TTS integration)
                audio_data_b64 = orchestrator_data.get("audio_data")
                audio_format = orchestrator_data.get("audio_format", "wav")

                logger.info(
                    "Orchestration completed",
                    extra={
                        "response_length": len(response),
                        "has_audio": audio_data_b64 is not None,
                        "correlation_id": orchestrator_data.get("correlation_id"),
                    },
                )
        except httpx.HTTPStatusError as e:
            logger.error(
                "Orchestration HTTP error",
                extra={
                    "status": e.response.status_code,
                    "error": str(e),
                },
            )
            response = f"Orchestration HTTP error: {e.response.status_code}"
            audio_data_b64 = None
            audio_format = None
        except Exception as e:
            logger.error(
                "Orchestration request failed",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            response = f"Orchestration request failed: {str(e)}"
            audio_data_b64 = None
            audio_format = None

        # 4. Handle audio output (use orchestrator's audio or fallback to direct TTS)
        # audio_output_path already declared above

        if response and response != "No response generated":
            # Prefer audio from orchestrator response (already synthesized)
            if audio_data_b64:
                try:
                    import base64

                    # Decode base64 audio data
                    audio_bytes = base64.b64decode(audio_data_b64)

                    # Save audio output using tempfile API
                    # Use delete=False because Gradio reads files asynchronously after function returns
                    # OS will clean up temp files automatically (standard behavior)
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=f".{audio_format}"
                    ) as tmp:
                        tmp.write(audio_bytes)
                        audio_file_path = tmp.name

                    # Convert to string for Gradio
                    audio_output_path = str(audio_file_path)

                    logger.info(
                        "Audio from orchestrator saved to temporary file",
                        extra={
                            "output_path": audio_output_path,
                            "format": audio_format,
                        },
                    )
                except Exception as e:
                    logger.error(
                        "Failed to save orchestrator audio",
                        extra={"error": str(e)},
                    )
                    # Fall through to TTS fallback
                    audio_output_path = None

            # Fallback: Call TTS directly if orchestrator didn't provide audio
            if not audio_output_path:
                try:
                    tts_response = await client.post(
                        f"{TTS_BASE_URL}/synthesize",
                        json={"text": response, "voice": voice_preset},
                    )
                    tts_response.raise_for_status()

                    # Parse Bark response (it returns JSON with audio as base64)
                    tts_data = tts_response.json()
                    tts_audio = tts_data.get("audio")

                    if isinstance(tts_audio, str):
                        # Decode base64 string
                        import base64

                        audio_bytes = base64.b64decode(tts_audio)
                    elif isinstance(tts_audio, bytes):
                        audio_bytes = tts_audio
                    else:
                        # Try to read as raw bytes if not JSON
                        audio_bytes = tts_response.content

                    # Save audio output using tempfile API
                    # Use delete=False because Gradio reads files asynchronously after function returns
                    # OS will clean up temp files automatically (standard behavior)
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".wav"
                    ) as tmp:
                        tmp.write(audio_bytes)
                        audio_file_path = tmp.name

                    # Convert to string for Gradio
                    audio_output_path = str(audio_file_path)

                    logger.info(
                        "TTS synthesis completed (fallback) - saved to temporary file",
                        extra={"output_path": audio_output_path},
                    )
                except Exception as e:
                    logger.error("TTS synthesis failed", extra={"error": str(e)})
                    audio_output_path = None

        return transcript, response, audio_output_path

    except Exception as e:
        logger.error("Pipeline test failed", extra={"error": str(e)})
        return f"Error: {str(e)}", "", None


def create_gradio_interface() -> Any:
    """Create the Gradio interface for testing."""

    # Create interface
    demo = gr.Interface(
        fn=run_pipeline,
        inputs=[
            gr.Audio(
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


# Create async wrapper functions for dependency checks
async def _check_audio_preprocessor_health() -> bool:
    """Check if the audio enhancer is available."""
    audio_enhancer = getattr(app.state, "audio_enhancer", None)
    return audio_enhancer is not None


async def _check_stt_health() -> bool:
    """Check STT service health."""
    return await _check_service_health(STT_BASE_URL)


async def _check_orchestrator_health() -> bool:
    """Check orchestrator service health."""
    return await _check_service_health(ORCHESTRATOR_BASE_URL)


async def _check_tts_health() -> bool:
    """Check TTS service health."""
    return await _check_service_health(TTS_BASE_URL)


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="testing",
    health_manager=health_manager,
    custom_components={},
    custom_dependencies={
        "audio_preprocessor": _check_audio_preprocessor_health,
        "stt": _check_stt_health,
        "orchestrator": _check_orchestrator_health,
        "tts": _check_tts_health,
    },
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())


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
