# Debug File Management Library

This library provides a centralized way to save debug files across all services in the Discord Voice Lab project.

## Features

- **Correlation-based organization**: Files are grouped by `correlation_id` in flattened directories
- **Service-specific environment variables**: Each service can control debug saving independently
- **Multiple file types**: Support for text, audio, JSON, and manifest files
- **Automatic WAV conversion**: Raw PCM audio data is automatically converted to WAV format
- **Structured logging**: All debug operations are logged with structured metadata

## Directory Structure

Debug files are organized as follows:

```
debug/
└── correlation-id-123/
    ├── 20251012_051758_audio.wav
    ├── 20251012_051758_response.txt
    ├── 20251012_051758_metadata.json
    └── 20251012_051758_manifest.json
```

## Usage

### Basic Usage

```python
from services.common.debug import get_debug_manager

# Get debug manager for your service
debug_manager = get_debug_manager("your_service_name")

# Save text file
debug_manager.save_text_file(
    correlation_id="test-123",
    content="Debug information here",
    filename_prefix="debug",
)

# Save audio file
debug_manager.save_audio_file(
    correlation_id="test-123",
    audio_data=raw_audio_bytes,
    filename_prefix="audio",
)

# Save JSON data
debug_manager.save_json_file(
    correlation_id="test-123",
    data={"key": "value", "timestamp": "2025-01-01T00:00:00Z"},
    filename_prefix="metadata",
)

# Save manifest
debug_manager.save_manifest(
    correlation_id="test-123",
    metadata={"service": "your_service", "event": "processing_complete"},
    files={"debug": "debug.txt", "audio": "audio.wav"},
    stats={"duration": 2.5, "size_bytes": 1024},
)
```

### Convenience Functions

```python
from services.common.debug import save_debug_text, save_debug_audio, save_debug_json

# Quick text saving
save_debug_text(
    correlation_id="test-123",
    content="Quick debug message",
    service_name="your_service",
)

# Quick audio saving
save_debug_audio(
    correlation_id="test-123",
    audio_data=raw_audio_bytes,
    service_name="your_service",
)

# Quick JSON saving
save_debug_json(
    correlation_id="test-123",
    data={"status": "success"},
    service_name="your_service",
)
```

## Environment Variables

Each service can control debug saving with its own environment variable:

- **Orchestrator**: `ORCHESTRATOR_DEBUG_SAVE=true`
- **Discord**: `DISCORD_DEBUG_SAVE=true`
- **STT**: `STT_DEBUG_SAVE=true`
- **TTS**: `TTS_DEBUG_SAVE=true`

## Service Integration Examples

### Discord Service

```python
from services.common.debug import get_debug_manager

class DiscordService:
    def __init__(self):
        self.debug_manager = get_debug_manager("discord")
    
    def process_voice_segment(self, correlation_id: str, audio_data: bytes):
        # Save debug audio
        self.debug_manager.save_audio_file(
            correlation_id=correlation_id,
            audio_data=audio_data,
            filename_prefix="voice_segment",
        )
        
        # Save debug metadata
        self.debug_manager.save_json_file(
            correlation_id=correlation_id,
            data={
                "user_id": self.user_id,
                "channel_id": self.channel_id,
                "duration": len(audio_data) / 48000,  # Assuming 48kHz
            },
            filename_prefix="voice_metadata",
        )
```

### STT Service

```python
from services.common.debug import save_debug_text, save_debug_json

def transcribe_audio(correlation_id: str, audio_data: bytes) -> str:
    # Process audio...
    transcript = "Hello, world!"
    
    # Save debug information
    save_debug_text(
        correlation_id=correlation_id,
        content=f"Transcription result: {transcript}",
        service_name="stt",
        filename_prefix="transcription",
    )
    
    save_debug_json(
        correlation_id=correlation_id,
        data={
            "transcript": transcript,
            "confidence": 0.95,
            "language": "en",
            "processing_time_ms": 1500,
        },
        service_name="stt",
        filename_prefix="transcription_metadata",
    )
    
    return transcript
```

## File Naming Convention

Files are named using the pattern: `{timestamp}_{prefix}.{extension}`

- `timestamp`: `YYYYMMDD_HHMMSS` format
- `prefix`: Customizable prefix (e.g., "audio", "response", "metadata")
- `extension`: Based on file type (`.wav`, `.txt`, `.json`)

## Audio Format Support

The library automatically converts raw PCM audio data to WAV format with the following defaults:

- **Sample Rate**: 48kHz
- **Channels**: Mono
- **Bit Depth**: 16-bit
- **Format**: PCM

## Error Handling

All debug operations are wrapped in try-catch blocks and log errors without raising exceptions. This ensures that debug failures don't affect the main application flow.

## Logging

All debug operations are logged with structured metadata:

```json
{
  "event": "debug.audio_file_saved",
  "correlation_id": "test-123",
  "file_path": "/app/debug/test-123/20251012_051758_audio.wav",
  "size_bytes": 1024,
  "service": "common",
  "component": "debug"
}
```
