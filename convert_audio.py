#!/usr/bin/env python3
"""
Convert raw audio data from TTS service to proper WAV file for STT service.
"""

import wave
import io
import requests
import sys

def convert_tts_to_wav(tts_url, text, output_file):
    """Convert TTS audio to proper WAV file."""
    
    # Get raw audio from TTS service
    response = requests.post(
        tts_url,
        json={"text": text, "voice": "default"},
        headers={"Authorization": "Bearer changeme"}
    )
    
    if response.status_code != 200:
        print(f"TTS request failed: {response.status_code}")
        return False
    
    raw_audio = response.content
    print(f"Received {len(raw_audio)} bytes of raw audio")
    
    # Convert to proper WAV file
    # TTS service generates 16-bit PCM at 22050 Hz, mono
    sample_rate = 22050
    channels = 1
    sample_width = 2  # 16-bit = 2 bytes
    
    with wave.open(output_file, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(raw_audio)
    
    print(f"Created WAV file: {output_file}")
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python convert_audio.py <text>")
        sys.exit(1)
    
    text = sys.argv[1]
    tts_url = "http://localhost:7000/synthesize"
    output_file = "converted_audio.wav"
    
    success = convert_tts_to_wav(tts_url, text, output_file)
    if success:
        print("Conversion successful!")
    else:
        print("Conversion failed!")
        sys.exit(1)
