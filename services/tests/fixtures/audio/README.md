# Audio Test Fixtures

This directory contains audio files used for testing the STT service and other audio processing components.

## Real Speech Sample

### Generating `spoken_english.wav`

To generate a real speech audio file using the TTS service:

```bash
# Make sure TTS service is running
make run  # or docker compose up bark

# Generate speech sample
python services/tests/fixtures/audio/generate_speech_sample.py

# Or with custom text:
python services/tests/fixtures/audio/generate_speech_sample.py "Your custom text here"
```

The script will:
1. Call the TTS service to synthesize speech
2. Convert the audio to STT format (16kHz, 16-bit PCM, mono)
3. Save it as `spoken_english.wav` in this directory

**Environment Variables:**
- `TTS_URL` or `TTS_BASE_URL`: TTS service URL (default: `http://localhost:7120`)

**Note:** The default port is 7120 (external port when running Docker Compose from the host).
If running inside Docker, use `http://bark:7100` (internal port).

**Requirements:**
- TTS service must be running and accessible
- Services must have access to audio processing libraries (librosa, soundfile)

## Synthetic Audio Samples

Other audio files in this directory are generated using:
```bash
python services/tests/fixtures/audio/generate_samples_simple.py
```

These include:
- `sine_440hz_1s.wav`: 1 second sine wave at 440Hz
- `sine_1000hz_2s.wav`: 2 second sine wave at 1000Hz
- `voice_range_300hz.wav`: Audio in human voice frequency range (300Hz)
- `voice_range_3400hz.wav`: Audio in human voice frequency range (3400Hz)
- `silence.wav`: Silent audio
- `low_amplitude.wav`: Low amplitude audio
- `high_amplitude.wav`: High amplitude audio

## Usage in Tests

Tests automatically use `spoken_english.wav` if available, falling back to synthetic audio:

```python
from services.tests.fixtures.integration_fixtures import sample_audio_bytes

audio = sample_audio_bytes()  # Returns real speech if available
```

