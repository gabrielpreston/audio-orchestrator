---
title: Integrated Test Recorder
description: Test phrase recorder integrated with the Orchestrator service
last-updated: 2025-10-18
---

# Integrated Test Recorder

The Test Phrase Recorder is now integrated into the Orchestrator service, providing a web-based interface for recording and managing test phrases for automated testing of the Discord Voice Lab system.

## Overview

The integrated test recorder provides:

- **Web Interface**: Accessible at `/test-recorder` on the orchestrator service
- **REST API**: Full programmatic access to recording management
- **Audio Processing**: Built-in conversion from WebM to WAV format
- **Persistent Storage**: Recordings stored in the orchestrator container
- **Configuration**: Configurable via environment variables

## Quick Start

### 1. Start the Services

```bash
make run
```

### 2. Access the Test Recorder

```bash
make test-recorder
```

This will open the test recorder web interface in your browser at `http://localhost:8000/test-recorder`.

### 3. Test the Integration

```bash
make test-recorder-integration
```

## Web Interface

The web interface provides:

- **Phrase Management**: Add, edit, and delete test phrases
- **Audio Recording**: Real-time recording with visual feedback
- **Category Organization**: Organize phrases by type (wake, core, edge, noise)
- **Audio Playback**: Test recorded phrases
- **Format Conversion**: Convert WebM recordings to WAV
- **Export Functionality**: Download metadata and audio files

## API Endpoints

### Phrase Management

- `POST /test-recorder/phrases` - Add a new phrase
- `GET /test-recorder/phrases` - List all phrases
- `GET /test-recorder/phrases/{id}` - Get specific phrase
- `DELETE /test-recorder/phrases/{id}` - Delete phrase

### Audio Management

- `POST /test-recorder/phrases/{id}/audio` - Upload audio for phrase
- `GET /test-recorder/phrases/{id}/audio` - Download audio file
- `POST /test-recorder/phrases/{id}/convert` - Convert to WAV format

### Data Export

- `GET /test-recorder/metadata` - Export all metadata
- `GET /test-recorder/stats` - Get recording statistics
- `DELETE /test-recorder/phrases` - Clear all recordings

## Configuration

Configure the test recorder via environment variables in `services/orchestrator/.env.service`:

```bash
# Test recorder configuration
TEST_RECORDER_RECORDINGS_DIR=/app/recordings
TEST_RECORDER_MAX_FILE_SIZE_MB=10
TEST_RECORDER_DEFAULT_SAMPLE_RATE=48000
```

### Configuration Options

- **`TEST_RECORDER_RECORDINGS_DIR`**: Directory to store recordings (default: `/app/recordings`)
- **`TEST_RECORDER_MAX_FILE_SIZE_MB`**: Maximum file size in MB (default: 10)
- **`TEST_RECORDER_DEFAULT_SAMPLE_RATE`**: Default sample rate for conversion (default: 48000)

## Usage Examples

### Recording a Test Phrase

1. **Add Phrase**: Enter text and select category
2. **Start Recording**: Click "Start Recording" and speak clearly
3. **Stop Recording**: Click "Stop Recording" when finished
4. **Convert**: Click "Convert" to create WAV format
5. **Test**: Use "Play" to verify the recording

### Programmatic Usage

```python
import requests

# Add a phrase
response = requests.post("http://localhost:8000/test-recorder/phrases", json={
    "text": "Hey Atlas, what's the weather?",
    "category": "wake"
})
phrase_id = response.json()["phrase"]["id"]

# Upload audio (base64 encoded)
with open("recording.webm", "rb") as f:
    audio_data = base64.b64encode(f.read()).decode()

requests.post(f"http://localhost:8000/test-recorder/phrases/{phrase_id}/audio", json={
    "phrase_id": phrase_id,
    "audio_data": audio_data,
    "audio_format": "webm"
})

# Convert to WAV
requests.post(f"http://localhost:8000/test-recorder/phrases/{phrase_id}/convert", json={
    "sample_rate": 48000
})
```

### Integration with Testing

```python
# Download converted audio for testing
response = requests.get(f"http://localhost:8000/test-recorder/phrases/{phrase_id}/audio?converted=true")
with open("test_audio.wav", "wb") as f:
    f.write(response.content)

# Use in test cases
def test_wake_phrase_detection():
    audio_file = Path("test_audio.wav")
    audio_data = audio_file.read_bytes()
    
    detector = WakePhraseDetector(wake_phrases=["hey atlas"])
    result = detector.detect(audio_data)
    
    assert result.detected
    assert "hey atlas" in result.transcript.lower()
```

## File Storage

Recordings are stored in the orchestrator container at `/app/recordings/`:

```text
/app/recordings/
├── recordings_metadata.json    # Phrase metadata
├── wake_123_hey_atlas.webm    # Original WebM recording
├── wake_123_hey_atlas_converted.wav  # Converted WAV file
└── ...
```

## Audio Format

- **Input**: WebM with Opus codec (48kHz, mono)
- **Output**: WAV with PCM encoding (16-bit, mono, configurable sample rate)
- **Conversion**: Uses ffmpeg for high-quality conversion

## Troubleshooting

### Common Issues

1. **Service Not Accessible**

   ```bash
   # Check if orchestrator is running
   make logs SERVICE=orchestrator
   
   # Check service health
   curl http://localhost:8000/health/ready
   ```

2. **Audio Recording Issues**
   - Ensure browser has microphone permissions
   - Check for HTTPS requirement (some browsers require secure context)
   - Verify microphone is working in other applications

3. **Conversion Failures**
   - Check if ffmpeg is installed in the container
   - Verify audio file format is supported
   - Check container logs for error details

4. **Storage Issues**
   - Check available disk space in container
   - Verify write permissions to recordings directory
   - Check file size limits

### Debug Commands

```bash
# Check orchestrator logs
make logs SERVICE=orchestrator

# Test API endpoints
make test-recorder-integration

# Check container storage
docker exec -it discord-voice-lab-orchestrator-1 ls -la /app/recordings/

# Check ffmpeg installation
docker exec -it discord-voice-lab-orchestrator-1 ffmpeg -version
```

## Development

### Adding New Features

1. **Backend**: Add endpoints to `services/orchestrator/app.py`
2. **Frontend**: Update `services/orchestrator/static/js/test-recorder.js`
3. **Styling**: Modify `services/orchestrator/static/css/test-recorder.css`
4. **Configuration**: Add options to `TestRecorderConfig`

### Testing Changes

```bash
# Rebuild orchestrator service
make docker-build-service SERVICE=orchestrator

# Test integration
make test-recorder-integration

# Test web interface
make test-recorder
```

## Related Documentation

- [Test Artifacts Management](TEST_ARTIFACTS.md)
- [Main Testing Documentation](TESTING.md)
- [Quality Thresholds](QUALITY_THRESHOLDS.md)
- [TTS Testing Guide](TTS_TESTING.md)
