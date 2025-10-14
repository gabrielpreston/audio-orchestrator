"""TTS adapter implementation for LiveKit agent service."""

import asyncio
import json
from typing import Dict, List, Optional

import httpx
from services.common.audio_contracts import TTSAdapter
from services.common.logging import get_logger


class LiveKitTTSAdapter(TTSAdapter):
    """TTS adapter that integrates with the existing TTS service."""
    
    def __init__(self, tts_base_url: str, timeout: int = 30):
        self.tts_base_url = tts_base_url.rstrip('/')
        self.timeout = timeout
        self.logger = get_logger("tts_adapter")
        self._active_streams: Dict[str, Dict] = {}
    
    async def synthesize_text(self, text: str, voice: str = "default", correlation_id: str = "") -> bytes:
        """Synthesize text to audio and return as bytes."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.tts_base_url}/synthesize",
                    json={
                        "text": text,
                        "voice": voice,
                        "stream": False
                    }
                )
                response.raise_for_status()
                
                # Return the audio data directly
                return response.content
                
        except httpx.HTTPError as e:
            self.logger.error(
                "tts.synthesis_error",
                correlation_id=correlation_id,
                error=str(e),
                text=text[:100]
            )
            raise RuntimeError(f"TTS synthesis failed: {e}")
        except Exception as e:
            self.logger.error(
                "tts.unexpected_error",
                correlation_id=correlation_id,
                error=str(e),
                text=text[:100]
            )
            raise
    
    async def start_stream(self, correlation_id: str) -> str:
        """Start a new TTS stream for incremental synthesis."""
        stream_id = f"tts_{correlation_id}_{asyncio.get_event_loop().time()}"
        
        self._active_streams[stream_id] = {
            "correlation_id": correlation_id,
            "text_chunks": [],
            "audio_chunks": [],
            "is_paused": False,
            "is_finalized": False,
            "start_time": asyncio.get_event_loop().time()
        }
        
        self.logger.info(
            "tts.stream_started",
            stream_id=stream_id,
            correlation_id=correlation_id
        )
        
        return stream_id
    
    async def add_text_chunk(self, stream_id: str, text: str) -> None:
        """Add text chunk to the stream."""
        if stream_id not in self._active_streams:
            self.logger.warning("tts.unknown_stream", stream_id=stream_id)
            return
        
        stream_data = self._active_streams[stream_id]
        
        if stream_data["is_finalized"]:
            self.logger.warning("tts.stream_finalized", stream_id=stream_id)
            return
        
        stream_data["text_chunks"].append(text)
        
        # Synthesize the chunk immediately for streaming
        try:
            audio_data = await self.synthesize_text(
                text,
                correlation_id=stream_data["correlation_id"]
            )
            stream_data["audio_chunks"].append(audio_data)
            
            self.logger.debug(
                "tts.chunk_added",
                stream_id=stream_id,
                correlation_id=stream_data["correlation_id"],
                text_length=len(text),
                audio_size=len(audio_data)
            )
            
        except Exception as e:
            self.logger.error(
                "tts.chunk_synthesis_failed",
                stream_id=stream_id,
                correlation_id=stream_data["correlation_id"],
                error=str(e),
                text=text[:100]
            )
    
    async def get_audio_chunk(self, stream_id: str) -> Optional[bytes]:
        """Get the next audio chunk from the stream."""
        if stream_id not in self._active_streams:
            return None
        
        stream_data = self._active_streams[stream_id]
        
        if stream_data["is_paused"] or not stream_data["audio_chunks"]:
            return None
        
        # Return the first available chunk
        chunk = stream_data["audio_chunks"].pop(0)
        
        self.logger.debug(
            "tts.chunk_retrieved",
            stream_id=stream_id,
            correlation_id=stream_data["correlation_id"],
            chunk_size=len(chunk),
            remaining_chunks=len(stream_data["audio_chunks"])
        )
        
        return chunk
    
    async def pause_stream(self, stream_id: str) -> None:
        """Pause the TTS stream."""
        if stream_id in self._active_streams:
            self._active_streams[stream_id]["is_paused"] = True
            self.logger.info("tts.stream_paused", stream_id=stream_id)
    
    async def resume_stream(self, stream_id: str) -> None:
        """Resume the TTS stream."""
        if stream_id in self._active_streams:
            self._active_streams[stream_id]["is_paused"] = False
            self.logger.info("tts.stream_resumed", stream_id=stream_id)
    
    async def stop_stream(self, stream_id: str) -> None:
        """Stop and cleanup the stream."""
        if stream_id in self._active_streams:
            stream_data = self._active_streams[stream_id]
            stream_data["is_finalized"] = True
            
            # Finalize any remaining text
            if stream_data["text_chunks"]:
                remaining_text = " ".join(stream_data["text_chunks"])
                if remaining_text.strip():
                    try:
                        audio_data = await self.synthesize_text(
                            remaining_text,
                            correlation_id=stream_data["correlation_id"]
                        )
                        stream_data["audio_chunks"].append(audio_data)
                    except Exception as e:
                        self.logger.error(
                            "tts.finalization_failed",
                            stream_id=stream_id,
                            correlation_id=stream_data["correlation_id"],
                            error=str(e)
                        )
            
            del self._active_streams[stream_id]
            
            self.logger.info(
                "tts.stream_stopped",
                stream_id=stream_id,
                correlation_id=stream_data["correlation_id"]
            )