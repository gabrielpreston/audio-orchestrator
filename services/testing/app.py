"""
Testing UI service for Audio Orchestrator.

Provides a Gradio interface for testing the complete audio pipeline
including preprocessing, transcription, orchestration, and synthesis.
"""

import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np

from services.common.app_factory import create_service_app
from services.common.audio import AudioProcessor
from services.common.audio_quality import AudioQualityMetrics
from services.common.config import (
    LoggingConfig,
    get_service_preset,
)
from services.common.config.loader import get_env_with_default
from services.common.config.presets import WakeConfig
from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints
from services.common.audio_enhancement import AudioEnhancer
from services.common.structured_logging import configure_logging, get_logger
from services.common.surfaces.types import AudioSegment
from services.common.tracing import get_observability_manager
from services.common.wake_detection import WakeDetector

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

# WAV file storage directory
WAV_STORAGE_DIR = Path("/app/wavs/approved")
try:
    WAV_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
except (PermissionError, OSError):
    # In test environments, directory creation may fail
    # Use a temporary directory as fallback
    import tempfile

    WAV_STORAGE_DIR = Path(tempfile.gettempdir()) / "wavs" / "approved"
    WAV_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


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


def _get_wake_scores_for_debugging(
    wake_detector: WakeDetector,
    pcm: bytes,
    sample_rate: int,
) -> dict[str, float] | None:
    """
    Get detection scores for debugging (testing service only).

    Duplicates audio processing from detect_audio() but returns scores dict
    instead of WakeDetectionResult. This is testing-service-specific and
    doesn't modify the common library.

    Note: Accesses private attributes (_model, _target_sample_rate) for debugging.
    This is acceptable for testing-service-specific debugging code.

    Returns:
        Scores dict with phrase -> score mapping, or None if processing fails
    """
    import audioop

    if not pcm or wake_detector._model is None:
        return None

    # Resample if needed (duplicate logic from _resample method)
    target_rate = wake_detector._target_sample_rate
    if sample_rate != target_rate:
        try:
            converted, _ = audioop.ratecv(pcm, 2, 1, sample_rate, target_rate, None)
        except Exception:
            return None
    else:
        converted = pcm

    if not converted:
        return None

    # Normalize to float32
    normalized = np.frombuffer(converted, dtype=np.int16).astype(np.float32) / 32768.0

    # Pad/truncate to expected length (same as detect_audio)
    expected_samples = 16 * 320  # 5120 samples at 16kHz
    if len(normalized) < expected_samples:
        normalized = np.pad(
            normalized,
            (0, expected_samples - len(normalized)),
            mode="constant",
        )
    elif len(normalized) > expected_samples:
        normalized = normalized[-expected_samples:]

    # Convert to int16
    normalized_clamped = np.clip(normalized, -1.0, 1.0)
    audio_float = normalized_clamped * 32768.0
    audio_int16 = np.clip(audio_float, -32768.0, 32767.0).astype(np.int16)

    # Get scores from model (accessing private _model attribute)
    try:
        scores = wake_detector._model.predict(audio_int16)
    except TypeError:
        scores = wake_detector._model.predict(
            audio_int16,
            sample_rate=wake_detector._target_sample_rate,
        )
    except Exception:
        return None

    if not isinstance(scores, dict) or not scores:
        return None

    return scores


async def test_wake_word_detection(
    audio: str | None,
    threshold: float = 0.5,
) -> tuple[str, str]:
    """
    Test wake word detection with detailed debugging output.

    Args:
        audio: Audio file path
        threshold: Detection threshold (0.0-1.0)

    Returns:
        Tuple of (detection_result_json, audio_metrics_json)
    """
    try:
        if not audio:
            return json.dumps({"error": "No audio file provided"}), json.dumps({})

        # Load audio file
        with Path(audio).open("rb") as f:
            wav_bytes = f.read()

        # Convert WAV to PCM
        audio_processor = AudioProcessor()
        pcm_bytes, metadata = audio_processor.wav_to_pcm(wav_bytes)

        # Create AudioSegment for quality metrics
        start_time = time.time()
        segment = AudioSegment(
            user_id="test_user",
            pcm=pcm_bytes,
            start_timestamp=start_time,
            end_timestamp=start_time + metadata.duration,
            correlation_id="test_correlation",
            frame_count=metadata.frames,
            sample_rate=metadata.sample_rate,
            channels=metadata.channels,
            sample_width=metadata.sample_width,
        )

        # Initialize WakeDetector
        wake_model_paths_env = os.getenv("WAKE_MODEL_PATHS")
        if wake_model_paths_env:
            # Parse comma-separated list
            model_paths = [
                path.strip() for path in wake_model_paths_env.split(",") if path.strip()
            ]
        else:
            # Default to Discord's model path
            model_paths = ["/app/.local/share/openwakeword/models/hey_ao/hey_ao.onnx"]

        wake_config = WakeConfig(
            model_paths=model_paths,
            activation_threshold=threshold,
            target_sample_rate_hz=16000,
            enabled=True,
        )
        wake_detector = WakeDetector(wake_config, service_name="testing")

        # Get detection result
        detection_result = wake_detector.detect_audio(pcm_bytes, metadata.sample_rate)

        # Get scores for debugging (even if below threshold)
        debug_scores = _get_wake_scores_for_debugging(
            wake_detector, pcm_bytes, metadata.sample_rate
        )

        # Calculate quality metrics
        quality_metrics = await AudioQualityMetrics.calculate_metrics(segment)

        # Format detection results
        detection_data = {
            "detected": detection_result is not None,
            "threshold": threshold,
            "result": (
                {
                    "phrase": detection_result.phrase,
                    "score": detection_result.confidence,
                    "source": detection_result.source,
                }
                if detection_result
                else None
            ),
            "all_scores": debug_scores,
            "audio_metadata": {
                "sample_rate": metadata.sample_rate,
                "channels": metadata.channels,
                "sample_width": metadata.sample_width,
                "duration": metadata.duration,
                "frames": metadata.frames,
            },
        }

        return json.dumps(detection_data, indent=2), json.dumps(
            quality_metrics, indent=2
        )

    except Exception as e:
        logger.error(
            "Wake word detection test failed",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        return (
            json.dumps({"error": str(e), "error_type": type(e).__name__}),
            json.dumps({}),
        )


def get_available_wav_files() -> list[tuple[str, str]]:
    """
    Get list of available WAV files with metadata.

    Returns:
        List of (filepath, display_name) tuples
    """
    files: list[tuple[str, str]] = []
    if not WAV_STORAGE_DIR.exists():
        return files

    for wav_file in sorted(WAV_STORAGE_DIR.glob("*.wav"), reverse=True):
        # Load metadata if available
        metadata_file = wav_file.with_suffix(".json")
        display_name = wav_file.stem
        if metadata_file.exists():
            try:
                with metadata_file.open("r") as f:
                    metadata = json.load(f)
                    timestamp = metadata.get("timestamp", "")
                    notes = metadata.get("notes", "")
                    if timestamp:
                        display_name = f"{wav_file.stem} | {timestamp}"
                    if notes:
                        display_name += f" | {notes[:30]}"
            except Exception as exc:
                logger.debug(
                    "Failed to load metadata for display name",
                    extra={"error": str(exc), "file": str(metadata_file)},
                )

        files.append((str(wav_file), display_name))

    return files


def save_approved_wav(
    audio_path: str | None,
    notes: str = "",
    custom_metadata: str = "",
) -> tuple[str, bool]:
    """
    Save approved WAV file with metadata.

    Args:
        audio_path: Path to audio file to save
        notes: User notes about the file
        custom_metadata: Additional metadata as JSON string

    Returns:
        Tuple of (status_message, success)
    """
    try:
        if not audio_path:
            return "No audio file provided", False

        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"wake_word_{timestamp}.wav"
        dest_path = WAV_STORAGE_DIR / filename

        # Copy file
        with Path(audio_path).open("rb") as src, dest_path.open("wb") as dst:
            dst.write(src.read())

        # Parse custom metadata if provided
        extra_metadata = {}
        if custom_metadata.strip():
            try:
                extra_metadata = json.loads(custom_metadata)
            except json.JSONDecodeError:
                logger.warning(
                    "Invalid JSON in custom metadata, ignoring",
                    extra={"custom_metadata": custom_metadata},
                )

        # Save metadata
        metadata = {
            "timestamp": timestamp,
            "notes": notes,
            "original_filename": Path(audio_path).name,
            "file_size": dest_path.stat().st_size,
            **extra_metadata,
        }

        metadata_file = dest_path.with_suffix(".json")
        with metadata_file.open("w") as f:
            json.dump(metadata, f, indent=2)

        return f"Saved: {filename}", True

    except Exception as e:
        logger.error(
            "Failed to save approved WAV",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        return f"Error: {str(e)}", False


def get_wav_metadata(filename: str) -> dict[str, Any] | None:
    """
    Load metadata for a WAV file.

    Args:
        filename: WAV filename (without path)

    Returns:
        Metadata dict or None if not found
    """
    try:
        metadata_file = WAV_STORAGE_DIR / Path(filename).with_suffix(".json")
        if not metadata_file.exists():
            return None

        with metadata_file.open("r") as f:
            result: dict[str, Any] = json.load(f)
            return result

    except Exception as e:
        logger.warning(
            "Failed to load WAV metadata",
            extra={"error": str(e), "wav_filename": filename},
        )
        return None


def load_wav_file(filename: str) -> str | None:
    """
    Get full path to WAV file for loading.

    Args:
        filename: WAV filename (without path)

    Returns:
        Full file path or None if not found
    """
    file_path = WAV_STORAGE_DIR / filename
    if file_path.exists():
        return str(file_path)
    return None


def create_gradio_interface() -> Any:
    """Create the Gradio interface for testing with tabs."""

    with gr.Blocks(
        title="Audio Orchestrator Testing Interface",
        theme="default",
    ) as demo:
        gr.Markdown(
            "# Audio Orchestrator Testing Interface\n\n"
            "Test the complete audio pipeline and wake word detection."
        )

        with gr.Tabs():
            # Pipeline Testing Tab
            with gr.Tab("Pipeline Testing"):
                gr.Markdown(
                    "Test the complete audio pipeline: "
                    "preprocessing → transcription → orchestration → synthesis"
                )
                with gr.Row():
                    with gr.Column():
                        pipeline_audio = gr.Audio(
                            type="filepath",
                            label="Speak (or upload audio file)",
                        )
                        pipeline_text = gr.Textbox(
                            label="Or type text input",
                            placeholder="Enter text to test the pipeline...",
                            lines=3,
                        )
                        pipeline_voice = gr.Dropdown(
                            choices=[
                                "v2/en_speaker_0",
                                "v2/en_speaker_1",
                                "v2/en_speaker_2",
                                "v2/en_speaker_3",
                            ],
                            value="v2/en_speaker_0",
                            label="Voice Preset",
                        )
                        pipeline_btn = gr.Button("Run Pipeline", variant="primary")
                    with gr.Column():
                        pipeline_transcript = gr.Textbox(label="Transcript", lines=2)
                        pipeline_response = gr.Textbox(label="Response", lines=4)
                        pipeline_audio_output = gr.Audio(label="Audio Output")

                pipeline_btn.click(
                    fn=run_pipeline,
                    inputs=[pipeline_audio, pipeline_text, pipeline_voice],
                    outputs=[
                        pipeline_transcript,
                        pipeline_response,
                        pipeline_audio_output,
                    ],
                )

            # Wake Word Debug Tab
            with gr.Tab("Wake Word Debug"):
                gr.Markdown("Test wake word detection with detailed debugging output.")
                with gr.Row():
                    with gr.Column():
                        wake_audio = gr.Audio(
                            type="filepath",
                            label="Upload Audio File",
                        )
                        wake_threshold = gr.Slider(
                            minimum=0.0,
                            maximum=1.0,
                            value=0.5,
                            step=0.01,
                            label="Detection Threshold",
                        )
                        wake_auto_save = gr.Checkbox(
                            label="Auto-save on detection",
                            value=False,
                        )
                        wake_btn = gr.Button(
                            "Test Wake Word Detection", variant="primary"
                        )
                    with gr.Column():
                        wake_result = gr.JSON(
                            label="Detection Results", show_label=True
                        )
                        wake_metrics = gr.JSON(
                            label="Audio Quality Metrics", show_label=True
                        )

                async def test_and_auto_save(
                    audio_path: str | None,
                    threshold: float,
                    auto_save: bool,
                ) -> tuple[str, str, str]:
                    """Test wake word detection and optionally auto-save."""
                    result_json, metrics_json = await test_wake_word_detection(
                        audio_path, threshold
                    )
                    save_status = ""
                    if (
                        auto_save
                        and audio_path
                        and json.loads(result_json).get("detected", False)
                    ):
                        status, success = save_approved_wav(
                            audio_path,
                            notes="Auto-saved from wake word detection",
                            custom_metadata=json.dumps(
                                {
                                    "detection_result": json.loads(result_json),
                                    "quality_metrics": json.loads(metrics_json),
                                },
                                indent=2,
                            ),
                        )
                        save_status = status if success else f"Save failed: {status}"
                    return result_json, metrics_json, save_status

                wake_save_status = gr.Textbox(
                    label="Auto-save Status", visible=False, interactive=False
                )

                wake_btn.click(
                    fn=test_and_auto_save,
                    inputs=[wake_audio, wake_threshold, wake_auto_save],
                    outputs=[wake_result, wake_metrics, wake_save_status],
                )

            # WAV File Management Tab
            with gr.Tab("WAV File Management"):
                gr.Markdown("Save approved WAV files and load them for testing.")

                # Save Section
                with gr.Row():  # noqa: SIM117
                    with gr.Column():
                        gr.Markdown("### Save Approved WAV")
                        save_audio = gr.Audio(
                            type="filepath",
                            label="Audio File to Save",
                        )
                        save_notes = gr.Textbox(
                            label="Notes",
                            placeholder="Enter notes about this file...",
                            lines=2,
                        )
                        save_custom_metadata = gr.Textbox(
                            label="Custom Metadata (JSON, optional)",
                            placeholder='{"key": "value"}',
                            lines=3,
                        )
                        save_btn = gr.Button("Save Approved WAV", variant="primary")
                        save_status = gr.Textbox(label="Status", interactive=False)

                        save_btn.click(
                            fn=save_approved_wav,
                            inputs=[save_audio, save_notes, save_custom_metadata],
                            outputs=[save_status],
                        )

                gr.Markdown("---")

                # Load Section
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Load Saved WAV")
                        wav_file_dropdown = gr.Dropdown(
                            label="Select WAV File",
                            choices=[],
                            value=None,  # Explicitly set to None
                            interactive=True,
                            allow_custom_value=False,  # Prevent manual entry
                        )
                        refresh_btn = gr.Button("Refresh File List")
                        load_btn = gr.Button("Load Selected File", variant="primary")
                    with gr.Column():
                        wav_metadata = gr.JSON(label="File Metadata", show_label=True)
                        wav_preview = gr.Audio(label="Audio Preview", interactive=False)

                        def refresh_files() -> Any:
                            """Refresh the file list."""
                            try:
                                files = get_available_wav_files()
                                choices = [display for _, display in files]
                                # Use gr.update() instead of gr.Dropdown.update()
                                return gr.update(choices=choices, value=None)
                            except Exception as e:
                                logger.error(
                                    "Failed to refresh WAV file list",
                                    extra={"error": str(e)},
                                )
                                return gr.update(choices=[], value=None)

                        def load_file(
                            filename_display: str | None,
                        ) -> tuple[str | None, str, str | None]:
                            """Load a file and its metadata."""
                            # Handle None or empty input
                            if not filename_display or not filename_display.strip():
                                return None, json.dumps({}, indent=2), None

                            try:
                                # Find the filepath from the display name
                                files = get_available_wav_files()
                                filepath = None
                                filename = None
                                for fp, display in files:
                                    if display == filename_display:
                                        filepath = fp
                                        filename = Path(fp).name
                                        break

                                if not filepath or not filename:
                                    logger.warning(
                                        "WAV file not found",
                                        extra={"display_name": filename_display},
                                    )
                                    return None, json.dumps({}, indent=2), None

                                metadata = get_wav_metadata(filename)
                                return (
                                    filepath,
                                    json.dumps(metadata or {}, indent=2),
                                    filepath,
                                )
                            except Exception as e:
                                logger.error(
                                    "Failed to load WAV file",
                                    extra={
                                        "error": str(e),
                                        "display_name": filename_display,
                                    },
                                )
                                return (
                                    None,
                                    json.dumps({"error": str(e)}, indent=2),
                                    None,
                                )

                        refresh_btn.click(
                            fn=refresh_files,
                            outputs=[wav_file_dropdown],
                        )

                        load_btn.click(
                            fn=load_file,
                            inputs=[wav_file_dropdown],
                            outputs=[wav_preview, wav_metadata, wake_audio],
                        )

                        # Auto-refresh on tab load
                        demo.load(fn=refresh_files, outputs=[wav_file_dropdown])

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

    # Launch in a separate thread with error handling
    import threading

    def _launch_gradio() -> None:
        """Launch Gradio interface with error handling."""
        try:
            # Configure Gradio to prevent localhost detection issues in Docker
            import os

            os.environ.setdefault("GRADIO_SERVER_NAME", "0.0.0.0")
            os.environ.setdefault("GRADIO_SERVER_PORT", "8080")

            demo.launch(
                server_name="0.0.0.0",
                server_port=8080,
                share=False,
                quiet=True,
                inbrowser=False,  # Don't try to open browser
                show_api=False,  # Disable API info generation to avoid schema errors
                prevent_thread_lock=True,  # Allow thread to continue
            )
        except Exception as exc:
            logger.error(
                "gradio.launch_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                message="Gradio interface failed to launch",
            )

    gradio_thread = threading.Thread(target=_launch_gradio)
    gradio_thread.daemon = True
    gradio_thread.start()

    # Start FastAPI server for health checks
    uvicorn.run(app, host="127.0.0.1", port=8081)
