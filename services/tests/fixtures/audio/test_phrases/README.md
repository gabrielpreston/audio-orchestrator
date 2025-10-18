# Test Phrases Directory

This directory contains recorded test phrases for automated testing of the Discord Voice Lab system.

## Directory Structure

```
test_phrases/
├── wake/          # Wake phrase recordings (e.g., "Hey Atlas", "OK Atlas")
├── core/          # Core command recordings (e.g., "What's the weather?")
├── edge/          # Edge case recordings (e.g., background noise, interruptions)
├── noise/         # Background noise and challenging audio conditions
└── README.md      # This file
```

## Usage

1. **Record Phrases**: Use the test recorder web interface (`test-recorder.html`)
2. **Convert Format**: Use the conversion script to convert WebM to WAV
3. **Organize Files**: Place converted files in the appropriate category directories
4. **Run Tests**: Use the test suite to validate the recordings

## File Naming Convention

Use descriptive filenames that indicate the content:
- `wake_1_hey_atlas.wav`
- `core_weather_query.wav`
- `edge_background_noise.wav`
- `noise_multiple_speakers.wav`

## Audio Format Requirements

- **Format**: WAV
- **Sample Rate**: 48kHz (Discord) or 16kHz (VAD)
- **Channels**: Mono
- **Bit Depth**: 16-bit PCM
- **Encoding**: Uncompressed PCM

## Integration with Tests

The recorded phrases are automatically discovered and used by the test suite:

```python
# Test wake phrase detection
def test_wake_phrase_detection():
    wake_files = list(Path("test_phrases/wake").glob("*.wav"))
    for audio_file in wake_files:
        # Test the recording
        pass
```

## Adding New Recordings

1. Record using the web interface
2. Convert to WAV format using the conversion script
3. Place in the appropriate category directory
4. Update test cases if needed
5. Run tests to verify the new recordings work

## Quality Guidelines

- Record in a quiet environment
- Use consistent microphone distance
- Speak clearly and at normal pace
- Maintain consistent volume levels
- Test different scenarios (quiet, noisy, etc.)