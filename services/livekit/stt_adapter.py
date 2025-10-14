"""STT adapter implementation for LiveKit agent service."""

import asyncio
import json
from typing import Dict, List, Optional

import httpx
from services.common.audio_contracts import AudioFrame, AudioSegment, STTAdapter, WordTiming
from services.common.logging import get_logger


class LiveKitSTTAdapter(STTAdapter):
    """STT adapter that integrates with the existing STT service."""
    
    def __init__(self, stt_base_url: str, timeout: int = 45):
        self.stt_base_url = stt_base_url.rstrip('/')
        self.timeout = timeout
        self.logger = get_logger("stt_adapter")
        self._active_streams: Dict[str, Dict] = {}
    
    async def start_stream(self, correlation_id: str) -> str:
        """Start a new STT stream."""
        stream_id = f"stt_{correlation_id}_{asyncio.get_event_loop().time()}"
        
        self._active_streams[stream_id] = {
            "correlation_id": correlation_id,
            "audio_frames": [],
            "start_time": asyncio.get_event_loop().time(),
            "last_activity": asyncio.get_event_loop().time()
        }
        
        self.logger.info(
            "stt.stream_started",
            stream_id=stream_id,
            correlation_id=correlation_id
        )
        
        return stream_id
    
    async def process_audio_frame(self, stream_id: str, frame: AudioFrame) -> Optional[AudioSegment]:
        """Process an audio frame and return partial/final transcript if available."""
        if stream_id not in self._active_streams:
            self.logger.warning("stt.unknown_stream", stream_id=stream_id)
            return None
        
        stream_data = self._active_streams[stream_id]
        stream_data["audio_frames"].append(frame)
        stream_data["last_activity"] = asyncio.get_event_loop().time()
        
        # For now, we'll process frames in batches
        # In production, you'd want more sophisticated batching logic
        if len(stream_data["audio_frames"]) >= 10:  # Process every 10 frames (200ms)
            return await self._process_frame_batch(stream_id)
        
        return None
    
    async def flush_stream(self, stream_id: str) -> Optional[AudioSegment]:
        """Flush the stream and return final transcript."""
        if stream_id not in self._active_streams:
            return None
        
        stream_data = self._active_streams[stream_id]
        
        if not stream_data["audio_frames"]:
            return None
        
        # Process remaining frames
        result = await self._process_frame_batch(stream_id, is_final=True)
        
        # Clean up stream
        del self._active_streams[stream_id]
        
        self.logger.info(
            "stt.stream_flushed",
            stream_id=stream_id,
            correlation_id=stream_data["correlation_id"]
        )
        
        return result
    
    async def stop_stream(self, stream_id: str) -> None:
        """Stop and cleanup the stream."""
        if stream_id in self._active_streams:
            del self._active_streams[stream_id]
            self.logger.info("stt.stream_stopped", stream_id=stream_id)
    
    async def _process_frame_batch(self, stream_id: str, is_final: bool = False) -> Optional[AudioSegment]:
        """Process a batch of audio frames."""
        stream_data = self._active_streams[stream_id]
        frames = stream_data["audio_frames"]
        
        if not frames:
            return None
        
        # Convert frames to WAV format for STT service
        wav_data = await self._frames_to_wav(frames)
        
        try:
            # Call STT service
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.stt_base_url}/transcribe",
                    files={"audio": ("audio.wav", wav_data, "audio/wav")},
                    data={"is_final": str(is_final).lower()}
                )
                response.raise_for_status()
                
                result = response.json()
                
                if not result.get("text", "").strip():
                    return None
                
                # Create audio segment
                start_time = frames[0].timestamp
                end_time = frames[-1].timestamp + (frames[-1].frame_duration_ms / 1000.0)
                
                words = []
                if "words" in result:
                    for word_data in result["words"]:
                        words.append(WordTiming(
                            word=word_data["word"],
                            start_time=word_data.get("start", 0.0),
                            end_time=word_data.get("end", 0.0),
                            confidence=word_data.get("confidence", 0.0)
                        ))
                
                segment = AudioSegment(
                    audio_frames=frames,
                    transcript=result["text"],
                    words=words,
                    start_time=start_time,
                    end_time=end_time,
                    confidence=result.get("confidence", 0.0),
                    is_final=is_final
                )
                
                # Clear processed frames
                stream_data["audio_frames"] = []
                
                self.logger.info(
                    "stt.transcript_processed",
                    stream_id=stream_id,
                    correlation_id=stream_data["correlation_id"],
                    text=result["text"][:100],  # Log first 100 chars
                    is_final=is_final,
                    confidence=result.get("confidence", 0.0)
                )
                
                return segment
                
        except httpx.HTTPError as e:
            self.logger.error(
                "stt.http_error",
                stream_id=stream_id,
                correlation_id=stream_data["correlation_id"],
                error=str(e)
            )
            return None
        except Exception as e:
            self.logger.error(
                "stt.processing_error",
                stream_id=stream_id,
                correlation_id=stream_data["correlation_id"],
                error=str(e)
            )
            return None
    
    async def _frames_to_wav(self, frames: List[AudioFrame]) -> bytes:
        """Convert audio frames to WAV format."""
        if not frames:
            return b""
        
        # Concatenate PCM data from all frames
        pcm_data = b"".join(frame.pcm_data for frame in frames)
        
        # Convert to WAV using the audio processor
        from ..common.audio import AudioProcessor
        processor = AudioProcessor("livekit")
        
        return processor.pcm_to_wav(
            pcm_data,
            sample_rate=frames[0].sample_rate,
            channels=1,
            sample_width=2
        )