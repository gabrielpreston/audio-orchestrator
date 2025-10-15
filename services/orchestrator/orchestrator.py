"""Core orchestration logic for handling transcripts and coordinating LLM with MCP tools."""

from __future__ import annotations

import asyncio
import json
import os
import struct
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from services.common.debug import get_debug_manager
from services.common.logging import get_logger

from .mcp_manager import MCPManager

logger = get_logger(__name__, service_name="orchestrator")


class Orchestrator:
    """Core orchestration logic for voice assistant interactions."""

    def __init__(
        self,
        mcp_manager: MCPManager,
        llm_base_url: str | None = None,
        tts_base_url: str | None = None,
    ):
        self.mcp_manager = mcp_manager
        self.llm_base_url = llm_base_url
        self.tts_base_url = tts_base_url
        self._logger = get_logger(__name__, service_name="orchestrator")
        self._http_client: httpx.AsyncClient | None = None
        self._available_tools: dict[str, list[dict[str, Any]]] = {}

    async def initialize(self) -> None:
        """Initialize the orchestrator."""
        if self.tts_base_url or self.llm_base_url:
            self._http_client = httpx.AsyncClient(timeout=60.0)

        # Load available tools from all MCP clients
        await self._load_available_tools()

        # Subscribe to transcript notifications
        self.mcp_manager.subscribe_notifications(self._handle_transcript_notification)

        self._logger.info("orchestrator.initialized")

    async def shutdown(self) -> None:
        """Shutdown the orchestrator."""
        if self._http_client:
            await self._http_client.aclose()
        self._logger.info("orchestrator.shutdown")

    def _save_debug_data(
        self,
        transcript: str,
        response: str,
        audio_data: bytes,
        metadata: dict[str, Any],
    ) -> None:
        """Save debug data to disk for analysis, grouped by correlation_id."""
        from services.common.debug import get_debug_manager

        try:
            correlation_id = metadata.get("correlation_id", "unknown")
            debug_manager = get_debug_manager("orchestrator")

            # Save text response
            response_content = (
                f"Original Transcript: {transcript}\n\nLLM Response: {response}"
            )
            response_file = debug_manager.save_text_file(
                correlation_id=correlation_id,
                content=response_content,
                filename_prefix="response",
            )

            # Save manifest with metadata
            files = {}
            if response_file:
                files["response_file"] = str(response_file)

            debug_manager.save_manifest(
                correlation_id=correlation_id,
                metadata=metadata,
                files=files,
                stats={
                    "transcript_length": len(transcript),
                    "response_length": len(response),
                    "audio_size_bytes": len(audio_data) if audio_data else 0,
                },
            )

        except Exception as exc:
            self._logger.error(
                "orchestrator.debug_save_failed",
                error=str(exc),
                correlation_id=metadata.get("correlation_id", "unknown"),
            )

    def _convert_raw_to_wav(
        self,
        raw_audio_data: bytes,
        sample_rate: int = 22050,
        num_channels: int = 1,
        sample_width: int = 2,
    ) -> bytes:
        """Convert raw PCM audio data to proper WAV format using standardized audio processing."""
        from services.common.audio import AudioProcessor

        processor = AudioProcessor("orchestrator")
        processor.set_logger(self._logger)

        try:
            # Use standardized audio processing
            wav_data = processor.pcm_to_wav(
                raw_audio_data, sample_rate, num_channels, sample_width
            )
            return wav_data

        except Exception as exc:
            self._logger.error(
                "orchestrator.wav_conversion_failed",
                error=str(exc),
            )
            # Fallback to original implementation
            try:
                # Calculate number of frames
                num_frames = len(raw_audio_data) // (num_channels * sample_width)

                # Create WAV header
                wav_header = self._create_wav_header(
                    sample_rate, num_channels, sample_width, num_frames
                )

                # Combine header with audio data
                return wav_header + raw_audio_data

            except Exception as fallback_exc:
                self._logger.error(
                    "orchestrator.wav_conversion_fallback_failed",
                    error=str(fallback_exc),
                )
                # Return original data if conversion fails
                return raw_audio_data

    def _create_wav_header(
        self, sample_rate: int, num_channels: int, sample_width: int, num_frames: int
    ) -> bytes:
        """Create a WAV file header."""
        # RIFF header
        riff_id = b"RIFF"
        riff_format = b"WAVE"

        # fmt chunk
        fmt_id = b"fmt "
        fmt_size = 16
        audio_format = 1  # PCM
        byte_rate = num_channels * sample_rate * sample_width
        block_align = num_channels * sample_width

        fmt_chunk = struct.pack(
            "<4sIHHIIHH",
            fmt_id,
            fmt_size,
            audio_format,
            num_channels,
            sample_rate,
            byte_rate,
            block_align,
            sample_width * 8,
        )

        # data chunk
        data_id = b"data"
        data_size = num_frames * num_channels * sample_width

        # Total file size
        file_size = 36 + data_size

        riff_chunk = struct.pack("<4sI4s", riff_id, file_size, riff_format)

        return riff_chunk + fmt_chunk + struct.pack("<4sI", data_id, data_size)

    def _save_audio_file(self, audio_data: bytes, correlation_id: str) -> str:
        """Save audio data to a temporary file and return the file path."""
        from services.common.debug import get_debug_manager

        try:
            debug_manager = get_debug_manager("orchestrator")
            file_path = debug_manager.save_audio_file(
                correlation_id=correlation_id,
                audio_data=audio_data,
                filename_prefix="audio",
                convert_to_wav=True,
            )

            if file_path:
                return str(file_path)
            else:
                # Fallback to old method if debug saving is disabled
                correlation_dir = Path("/app/debug") / correlation_id
                correlation_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_audio.wav"
                file_path = correlation_dir / filename
                wav_data = self._convert_raw_to_wav(audio_data)
                with open(file_path, "wb") as f:
                    f.write(wav_data)
                return str(file_path)

        except Exception as exc:
            self._logger.error(
                "orchestrator.audio_file_save_failed",
                error=str(exc),
                correlation_id=correlation_id,
            )
            raise

    async def process_transcript(
        self,
        guild_id: str,
        channel_id: str,
        user_id: str,
        transcript: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Process a transcript from Discord service."""
        try:
            from services.common.correlation import generate_orchestrator_correlation_id

            # Create transcript data in the expected format
            transcript_data = {
                "text": transcript,
                "user_id": user_id,
                "channel_id": channel_id,
                "guild_id": guild_id,
                "correlation_id": correlation_id
                or generate_orchestrator_correlation_id(user_id=user_id),
            }

            # Process the transcript
            await self._process_transcript(transcript_data)

            return {
                "status": "processed",
                "guild_id": guild_id,
                "channel_id": channel_id,
                "user_id": user_id,
                "transcript": transcript,
                "correlation_id": transcript_data["correlation_id"],
            }

        except Exception as exc:
            self._logger.error(
                "orchestrator.process_transcript_failed",
                error=str(exc),
                guild_id=guild_id,
                channel_id=channel_id,
                user_id=user_id,
            )
            return {"error": str(exc)}

    async def _load_available_tools(self) -> None:
        """Load available tools from all MCP clients."""
        self._available_tools = await self.mcp_manager.list_all_tools()

        total_tools = sum(len(tools) for tools in self._available_tools.values())
        self._logger.info(
            "orchestrator.tools_loaded",
            total_tools=total_tools,
            clients=list(self._available_tools.keys()),
        )

    async def _handle_transcript_notification(
        self, client_name: str, method: str, params: dict[str, Any]
    ) -> None:
        """Handle transcript notifications from Discord."""
        if client_name != "discord" or method != "discord/transcript":
            return

        self._logger.info(
            "orchestrator.transcript_received",
            correlation_id=params.get("correlation_id"),
            text_length=len(str(params.get("text", ""))),
        )

        # Process the transcript asynchronously
        _process_task = asyncio.create_task(self._process_transcript(params))
        # Store reference to prevent garbage collection

    async def _process_transcript(self, transcript_data: dict[str, Any]) -> None:
        """Process a transcript and generate a response."""
        correlation_id = transcript_data.get("correlation_id", "unknown")
        text = transcript_data.get("text", "")
        context = {
            "text": text,
            "guild_id": transcript_data.get("guild_id"),
            "channel_id": transcript_data.get("channel_id"),
            "user_id": transcript_data.get("user_id"),
            "correlation_id": correlation_id,
        }

        try:
            # Generate response using LLM with function calling
            response = await self._generate_response(text)

            self._logger.info(
                "orchestrator.response_generated",
                response_length=len(response) if response else 0,
                response_preview=response[:100] if response else "None",
                tts_base_url=self.tts_base_url,
                correlation_id=correlation_id,
            )

            # Synthesize and play audio if TTS is available
            if self.tts_base_url and response:
                self._logger.info(
                    "orchestrator.calling_tts",
                    correlation_id=correlation_id,
                )
                await self._synthesize_and_play(response, context)
            else:
                self._logger.warning(
                    "orchestrator.tts_skipped",
                    tts_base_url=self.tts_base_url,
                    has_response=bool(response),
                    correlation_id=correlation_id,
                )

        except Exception as exc:
            self._logger.error(
                "orchestrator.transcript_processing_failed",
                correlation_id=correlation_id,
                error=str(exc),
            )

    async def _generate_response(self, transcript: str) -> str:
        """Generate a response using LLM service via HTTP."""
        if not self.llm_base_url or not self._http_client:
            self._logger.warning("orchestrator.llm_unavailable")
            return "I'm sorry, but the language model is currently unavailable."

        # Build conversation messages
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": transcript},
        ]

        self._logger.info(
            "orchestrator.llm_request",
            transcript=transcript,
            messages_count=len(messages),
        )

        try:
            # Call LLM service
            llm_auth_token = os.getenv("LLM_AUTH_TOKEN")
            headers = {}
            if llm_auth_token:
                headers["Authorization"] = f"Bearer {llm_auth_token}"

            response = await self._http_client.post(
                f"{self.llm_base_url}/v1/chat/completions",
                json={
                    "model": "local-llama",
                    "messages": messages,
                    "max_tokens": 256,
                },
                headers=headers,
                timeout=60.0,
            )
            response.raise_for_status()

            result = response.json()
            choices = result.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")

                # Clean the response content to remove special tokens
                if content:
                    import re

                    # Remove various special tokens and formatting
                    content = re.sub(
                        r"\[INST\]|\[/INST\]|<<SYS>>|<<\/SYS>>|\[/SYS\]|<<SYS\]",
                        "",
                        content,
                    )
                    # Remove any remaining special characters and normalize whitespace
                    content = re.sub(r'[^\w\s.,!?;:\'"-]', "", content)
                    content = re.sub(r"\s+", " ", content).strip()
                    # If the response is too short or empty after cleaning, provide a fallback
                    if len(content) < 10:
                        content = "I understand your message. How can I help you?"

                self._logger.info(
                    "orchestrator.llm_response",
                    response_length=len(content),
                    response_preview=content[:100] if content else "Empty",
                )

                return content
            else:
                self._logger.warning("orchestrator.llm_empty_response")
                return "I understand your message. How can I help you?"

        except Exception as exc:
            self._logger.error(
                "orchestrator.llm_generation_failed",
                error=str(exc),
            )
            return f"I apologize, but I encountered an error processing your request: {exc!s}"

    async def _synthesize_and_play(self, text: str, context: dict[str, Any]) -> None:
        """Synthesize text to speech and play it in Discord."""
        if not self._http_client or not self.tts_base_url:
            return

        try:
            # Get TTS auth token from environment
            tts_auth_token = os.getenv("TTS_AUTH_TOKEN")
            headers = {}
            if tts_auth_token:
                headers["Authorization"] = f"Bearer {tts_auth_token}"

            # Call TTS service
            response = await self._http_client.post(
                f"{self.tts_base_url}/synthesize",
                json={
                    "text": text,
                    "voice": "default",
                    "correlation_id": context.get("correlation_id"),
                },
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()

            # Get audio data
            audio_data = response.content
            audio_id = response.headers.get("X-Audio-Id", "unknown")

            self._logger.info(
                "orchestrator.tts_synthesized",
                audio_id=audio_id,
                size_bytes=len(audio_data),
            )

            # Save debug data
            debug_metadata = {
                "audio_id": audio_id,
                "tts_service_url": self.tts_base_url,
                "voice": "default",
                "correlation_id": context.get("correlation_id"),
                "guild_id": context.get("guild_id"),
                "channel_id": context.get("channel_id"),
                "user_id": context.get("user_id"),
            }
            self._save_debug_data(
                transcript=context.get("text", ""),
                response=text,
                audio_data=audio_data,
                metadata=debug_metadata,
            )

            # Save audio file and create HTTP URL
            audio_file_path = self._save_audio_file(
                audio_data, context.get("correlation_id", "unknown")
            )
            audio_url = (
                f"http://orchestrator:8000/audio/{os.path.basename(audio_file_path)}"
            )

            # Play audio in Discord
            await self.mcp_manager.call_discord_tool(
                "discord.play_audio",
                {
                    "guild_id": context.get("guild_id"),
                    "channel_id": context.get("channel_id"),
                    "audio_url": audio_url,
                },
            )

            self._logger.info(
                "orchestrator.audio_played",
                correlation_id=context.get("correlation_id"),
            )

        except Exception as exc:
            self._logger.error(
                "orchestrator.audio_playback_failed",
                error=str(exc),
            )

    def _save_debug_mcp_tool_call(
        self,
        client_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        success: bool,
        context: dict[str, Any],
    ) -> None:
        """Save debug data for MCP tool calls."""
        try:
            from services.common.correlation import generate_mcp_correlation_id

            base_correlation_id = context.get("correlation_id", "unknown")
            correlation_id = generate_mcp_correlation_id(
                base_correlation_id, client_name, tool_name
            )
            debug_manager = get_debug_manager("orchestrator")

            # Save tool call details
            tool_call_content = f"""MCP Tool Call:
Client: {client_name}
Tool: {tool_name}
Arguments: {json.dumps(arguments, indent=2)}
Success: {success}
Result: {json.dumps(result, indent=2)}
Context: {json.dumps(context, indent=2)}"""

            debug_manager.save_text_file(
                correlation_id=correlation_id,
                content=tool_call_content,
                filename_prefix=f"mcp_tool_call_{client_name}_{tool_name}",
            )

            # Save tool call metadata
            debug_manager.save_json_file(
                correlation_id=correlation_id,
                data={
                    "client_name": client_name,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": result,
                    "success": success,
                    "context": context,
                    "timestamp": datetime.now().isoformat(),
                },
                filename_prefix=f"mcp_metadata_{client_name}_{tool_name}",
            )

        except Exception as exc:
            self._logger.error(
                "orchestrator.debug_mcp_tool_call_save_failed",
                client_name=client_name,
                tool_name=tool_name,
                error=str(exc),
            )


__all__ = ["Orchestrator"]
