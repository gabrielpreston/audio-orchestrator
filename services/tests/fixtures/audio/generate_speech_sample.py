"""Generate real speech audio using TTS service for STT testing.

This script generates a spoken English audio file that can be used for testing
the STT service with real speech instead of synthetic sine waves.
"""

import asyncio
import base64
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import httpx  # noqa: E402

# Import audio utilities (import after path setup)
from services.common.audio import AudioProcessor  # noqa: E402


async def generate_speech_sample(
    text: str = "Hello, this is a test of the speech transcription system.",
    tts_url: str = "http://localhost:7120",  # External port when running from host
    voice: str = "v2/en_speaker_1",
    output_filename: str = "spoken_english.wav",
) -> Path:
    """Generate a speech sample using the TTS service.

    Args:
        text: Text to synthesize
        tts_url: URL of the TTS service
        voice: Voice preset to use
        output_filename: Output filename

    Returns:
        Path to the generated audio file
    """
    fixtures_dir = Path(__file__).parent
    output_path = fixtures_dir / output_filename

    print(f"Generating speech sample from TTS service at {tts_url}...")
    print(f"Text: {text}")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Check if TTS service is available
            try:
                health_response = await client.get(
                    f"{tts_url}/health/ready", timeout=5.0
                )
                if health_response.status_code != 200:
                    print(
                        f"Warning: TTS service health check failed ({health_response.status_code})"
                    )
                    print("Attempting synthesis anyway...")
            except Exception as e:
                print(f"Warning: Could not check TTS service health: {e}")
                print("Attempting synthesis anyway...")

            # Generate speech
            response = await client.post(
                f"{tts_url}/synthesize",
                json={"text": text, "voice": voice},
                timeout=60.0,
            )

            if response.status_code != 200:
                raise Exception(
                    f"TTS synthesis failed: {response.status_code} - {response.text}"
                )

            data = response.json()
            audio_base64 = data.get("audio")
            if not audio_base64:
                raise Exception("TTS response missing audio data")

            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_base64)

            # Process audio to match STT requirements (16kHz, 16-bit, mono)
            processor = AudioProcessor("stt")
            metadata = processor.extract_metadata(audio_bytes, "wav")

            print(f"Original audio: {metadata.sample_rate}Hz, {metadata.channels}ch")

            # Convert to STT format if needed
            if metadata.sample_rate != 16000 or metadata.channels != 1:
                print("Converting to 16kHz mono...")
                pcm_data, _ = processor.wav_to_pcm(audio_bytes)

                # Resample if needed
                if metadata.sample_rate != 16000:
                    # Convert numpy array for resampling
                    import numpy as np

                    audio_array = np.frombuffer(pcm_data, dtype=np.int16).astype(
                        np.float32
                    )
                    audio_array = audio_array / 32768.0  # Normalize to [-1, 1]

                    # Resample using librosa
                    import librosa

                    audio_resampled = librosa.resample(
                        audio_array,
                        orig_sr=metadata.sample_rate,
                        target_sr=16000,
                    )

                    # Convert back to int16
                    audio_resampled = np.clip(audio_resampled * 32768.0, -32768, 32767)
                    pcm_data = audio_resampled.astype(np.int16).tobytes()

                # Create WAV file in STT format
                processed_audio = processor.pcm_to_wav(pcm_data, 16000, 1, 2)
            else:
                processed_audio = audio_bytes

            # Verify final format
            final_metadata = processor.extract_metadata(processed_audio, "wav")
            print(
                f"Final audio: {final_metadata.sample_rate}Hz, "
                f"{final_metadata.channels}ch, {final_metadata.bit_depth}-bit"
            )

            # Save to fixtures directory
            output_path.write_bytes(processed_audio)
            print(f"\n✓ Generated speech sample: {output_path}")
            print(f"  File size: {len(processed_audio)} bytes")
            print(f"  Duration: ~{final_metadata.duration:.2f}s")

            return output_path

    except Exception as e:
        print(f"\n✗ Error generating speech sample: {e}")
        print("\nNote: Make sure the TTS service is running:")
        print("  make run  # Start all services")
        print("  # OR")
        print("  docker compose up bark  # Start just TTS service")
        raise


def main():
    """Generate speech sample."""
    # Default text - short phrase for testing
    text = "Hello, this is a test of the speech transcription system."

    # Allow text to be passed as command-line argument
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])

    # Try to get TTS URL from environment or use default
    # Supports TTS_URL or TTS_BASE_URL (standardized env var)
    import os

    tts_url_env = os.getenv("TTS_URL") or os.getenv("TTS_BASE_URL")
    tts_url = tts_url_env if tts_url_env is not None else "http://localhost:7120"

    try:
        output_path = asyncio.run(generate_speech_sample(text=text, tts_url=tts_url))
        print(f"\nSuccess! Speech sample saved to: {output_path}")
        return 0
    except Exception as e:
        print(f"\nFailed to generate speech sample: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
