---
title: Test Phrase Recorder
description: Web interface for recording test phrases for automated testing
last-updated: 2025-10-18
---

# Test Phrase Recorder

The Test Phrase Recorder is a web-based interface for recording audio test phrases that can be used in automated testing of the Discord Voice Lab system.

## Overview

The recorder provides a simple, user-friendly interface for:

- Recording test phrases with different categories
- Managing recorded phrases
- Exporting audio files and metadata
- Converting recordings to the proper format for testing

## Usage

### 1. Open the Recorder

Open `test-recorder.html` in a modern web browser that supports:

- Web Audio API
- MediaRecorder API
- File API

### 2. Record Test Phrases

1. **Add a Phrase**: Enter the text of the test phrase and select a category:
   - **Wake Phrases**: Commands to activate the bot (e.g., "Hey Atlas")
   - **Core Commands**: Main functionality tests (e.g., "What's the weather?")
   - **Edge Cases**: Unusual or challenging inputs
   - **Noise/Background**: Tests with background noise

2. **Record Audio**: Click "Start Recording" and speak the phrase clearly
3. **Stop Recording**: Click "Stop Recording" when finished
4. **Review**: Use "Play Last Recording" to verify the audio quality
5. **Save**: The phrase is automatically saved when you stop recording

### 3. Manage Recordings

- **View All**: See all recorded phrases in the list
- **Play**: Test any recorded phrase
- **Delete**: Remove unwanted recordings
- **Export**: Download all recordings as a ZIP file

### 4. Export for Testing

1. **Download Audio Files**: Click "Download Audio Files (ZIP)" to get all recordings
2. **Download Metadata**: Click "Download Metadata (JSON)" to get phrase information
3. **Convert Format**: Use the conversion script to convert to WAV format

## Audio Format

The recorder captures audio in WebM format with:

- Sample rate: 48kHz (Discord standard)
- Channels: Mono
- Codec: Opus

For testing, these files are converted to WAV format with:

- Sample rate: 48kHz or 16kHz (configurable)
- Channels: Mono
- Bit depth: 16-bit PCM

## Conversion Script

Use `scripts/convert_test_recordings.py` to convert WebM recordings to WAV format:

```bash
# Convert all WebM files in a directory
python scripts/convert_test_recordings.py recordings/ converted/

# Convert using metadata file
python scripts/convert_test_recordings.py --metadata metadata.json recordings/ converted/

# Convert with custom sample rate (16kHz for VAD testing)
python scripts/convert_test_recordings.py --sample-rate 16000 recordings/ converted/

# Create test manifest
python scripts/convert_test_recordings.py --manifest recordings/ converted/
```

### Prerequisites

Install the required dependency:

```bash
pip install ffmpeg-python
```

## Integration with Testing

### 1. Add to Test Fixtures

Copy converted WAV files to the test fixtures directory:

```bash
cp converted/*.wav services/tests/fixtures/audio/
```

### 2. Update Test Cases

Reference the new audio files in your test cases:

```python
def test_wake_phrase_detection():
    """Test wake phrase detection with recorded audio."""
    audio_file = Path("services/tests/fixtures/audio/wake_1_hey_atlas.wav")
    audio_data = audio_file.read_bytes()
    
    # Test wake phrase detection
    result = wake_detector.detect(audio_data)
    assert result.detected
    assert "hey atlas" in result.transcript.lower()
```

### 3. Create Test Categories

Organize test files by category:

```python
# services/tests/fixtures/audio/test_phrases/
# ├── wake/
# │   ├── hey_atlas.wav
# │   └── ok_atlas.wav
# ├── core/
# │   ├── weather_query.wav
# │   └── time_query.wav
# └── edge/
#     ├── background_noise.wav
#     └── multiple_commands.wav
```

## Best Practices

### Recording Quality

1. **Environment**: Record in a quiet environment with minimal background noise
2. **Microphone**: Use a good quality microphone for clear audio
3. **Distance**: Maintain consistent distance from microphone (6-12 inches)
4. **Pace**: Speak at normal pace, clearly enunciating words
5. **Volume**: Maintain consistent volume levels

### Test Coverage

1. **Wake Phrases**: Record multiple variations of wake phrases
2. **Core Commands**: Cover all main functionality areas
3. **Edge Cases**: Include challenging scenarios:
   - Background noise
   - Multiple speakers
   - Interruptions
   - Unclear speech
   - Different accents/dialects

### File Organization

1. **Naming**: Use descriptive filenames that indicate content
2. **Categories**: Group related phrases by functionality
3. **Metadata**: Include detailed information in JSON exports
4. **Versioning**: Keep track of different versions of test phrases

## Troubleshooting

### Common Issues

1. **Microphone Access Denied**
   - Check browser permissions
   - Ensure HTTPS is used (required for microphone access)
   - Try refreshing the page

2. **Audio Quality Issues**
   - Check microphone quality
   - Reduce background noise
   - Adjust microphone distance

3. **Conversion Errors**
   - Ensure ffmpeg is installed
   - Check file permissions
   - Verify input file format

4. **Playback Issues**
   - Check browser audio support
   - Verify file format compatibility
   - Try different browser

### Debug Commands

```bash
# Check ffmpeg installation
ffmpeg -version

# Test audio file format
file recordings/*.webm

# Check converted files
file converted/*.wav

# Verify audio properties
ffprobe converted/test_phrase.wav
```

## File Structure

```text
test-recorder.html              # Main web interface
scripts/
  convert_test_recordings.py    # Conversion script
docs/testing/
  TEST_RECORDER.md             # This documentation
services/tests/fixtures/audio/  # Test audio files
  test_phrases/                # Organized test phrases
    wake/                      # Wake phrase recordings
    core/                      # Core command recordings
    edge/                      # Edge case recordings
    noise/                     # Background noise tests
```

## Related Documentation

- [Test Artifacts Management](TEST_ARTIFACTS.md)
- [Main Testing Documentation](TESTING.md)
- [Quality Thresholds](QUALITY_THRESHOLDS.md)
- [TTS Testing Guide](TTS_TESTING.md)
