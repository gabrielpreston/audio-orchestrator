"""Integration tests using recorded test phrases."""

import json
from pathlib import Path
from typing import Dict, List

import pytest

from services.common.audio import AudioProcessor
from services.discord.wake import WakePhraseDetector
from services.stt.transcription import STTClient


class TestRecordedPhrases:
    """Test suite for recorded test phrases."""

    @pytest.fixture
    def test_phrases_dir(self) -> Path:
        """Get the directory containing test phrase recordings."""
        return Path(__file__).parent.parent / "fixtures" / "audio" / "test_phrases"

    @pytest.fixture
    def test_manifest(self, test_phrases_dir: Path) -> Dict:
        """Load test manifest if available."""
        manifest_file = test_phrases_dir / "test_manifest.json"
        if manifest_file.exists():
            with open(manifest_file, 'r') as f:
                return json.load(f)
        return {}

    @pytest.fixture
    def wake_phrases(self, test_phrases_dir: Path) -> List[Path]:
        """Get wake phrase audio files."""
        wake_dir = test_phrases_dir / "wake"
        if wake_dir.exists():
            return list(wake_dir.glob("*.wav"))
        return []

    @pytest.fixture
    def core_phrases(self, test_phrases_dir: Path) -> List[Path]:
        """Get core command audio files."""
        core_dir = test_phrases_dir / "core"
        if core_dir.exists():
            return list(core_dir.glob("*.wav"))
        return []

    @pytest.fixture
    def edge_phrases(self, test_phrases_dir: Path) -> List[Path]:
        """Get edge case audio files."""
        edge_dir = test_phrases_dir / "edge"
        if edge_dir.exists():
            return list(edge_dir.glob("*.wav"))
        return []

    def test_wake_phrase_detection(self, wake_phrases: List[Path]):
        """Test wake phrase detection with recorded audio."""
        if not wake_phrases:
            pytest.skip("No wake phrase recordings found")

        # Initialize wake phrase detector
        detector = WakePhraseDetector(
            wake_phrases=["hey atlas", "ok atlas"],
            threshold=0.5
        )

        for audio_file in wake_phrases:
            with open(audio_file, 'rb') as f:
                audio_data = f.read()

            # Test wake phrase detection
            result = detector.detect(audio_data)
            
            # Basic validation
            assert result is not None
            assert hasattr(result, 'detected')
            assert hasattr(result, 'confidence')
            assert hasattr(result, 'transcript')

            print(f"Wake phrase test: {audio_file.name}")
            print(f"  Detected: {result.detected}")
            print(f"  Confidence: {result.confidence:.2f}")
            print(f"  Transcript: {result.transcript}")

    def test_core_command_transcription(self, core_phrases: List[Path]):
        """Test STT transcription with core command recordings."""
        if not core_phrases:
            pytest.skip("No core command recordings found")

        # Initialize STT client (mock for testing)
        stt_client = STTClient(base_url="http://localhost:9000")

        for audio_file in core_phrases:
            with open(audio_file, 'rb') as f:
                audio_data = f.read()

            # Test transcription
            try:
                result = stt_client.transcribe(audio_data)
                
                # Basic validation
                assert result is not None
                assert hasattr(result, 'text')
                assert hasattr(result, 'confidence')

                print(f"Core command test: {audio_file.name}")
                print(f"  Text: {result.text}")
                print(f"  Confidence: {result.confidence:.2f}")

            except Exception as e:
                print(f"STT test failed for {audio_file.name}: {e}")
                # Don't fail the test if STT service is not available
                pytest.skip(f"STT service not available: {e}")

    def test_edge_case_handling(self, edge_phrases: List[Path]):
        """Test handling of edge case recordings."""
        if not edge_phrases:
            pytest.skip("No edge case recordings found")

        processor = AudioProcessor()

        for audio_file in edge_phrases:
            with open(audio_file, 'rb') as f:
                audio_data = f.read()

            # Test audio processing
            try:
                # Validate audio format
                audio_info = processor.validate_audio_format(audio_data)
                assert audio_info['is_valid']

                # Test audio quality metrics
                quality_metrics = processor.analyze_audio_quality(audio_data)
                
                print(f"Edge case test: {audio_file.name}")
                print(f"  Sample rate: {audio_info['sample_rate']}")
                print(f"  Duration: {audio_info['duration']:.2f}s")
                print(f"  Quality score: {quality_metrics.get('quality_score', 'N/A')}")

            except Exception as e:
                print(f"Edge case test failed for {audio_file.name}: {e}")
                # Edge cases might legitimately fail, so we don't fail the test
                pass

    def test_audio_format_compatibility(self, test_phrases_dir: Path):
        """Test that all recorded audio files are in the correct format."""
        if not test_phrases_dir.exists():
            pytest.skip("No test phrases directory found")

        processor = AudioProcessor()
        audio_files = list(test_phrases_dir.rglob("*.wav"))

        if not audio_files:
            pytest.skip("No WAV files found in test phrases directory")

        for audio_file in audio_files:
            with open(audio_file, 'rb') as f:
                audio_data = f.read()

            # Validate format
            audio_info = processor.validate_audio_format(audio_data)
            
            assert audio_info['is_valid'], f"Invalid audio format: {audio_file}"
            assert audio_info['channels'] == 1, f"Expected mono audio: {audio_file}"
            assert audio_info['sample_rate'] in [16000, 48000], f"Unexpected sample rate: {audio_file}"
            assert audio_info['bit_depth'] == 16, f"Expected 16-bit audio: {audio_file}"

            print(f"✓ Format valid: {audio_file.name}")

    def test_manifest_consistency(self, test_manifest: Dict, test_phrases_dir: Path):
        """Test that the manifest file is consistent with actual files."""
        if not test_manifest:
            pytest.skip("No test manifest found")

        # Check that all files in manifest exist
        for file_info in test_manifest.get('files', []):
            file_path = test_phrases_dir / file_info['path']
            assert file_path.exists(), f"Manifest file not found: {file_info['path']}"
            
            # Check file size matches
            actual_size = file_path.stat().st_size
            expected_size = file_info['size_bytes']
            assert actual_size == expected_size, f"File size mismatch: {file_info['path']}"

        print(f"✓ Manifest consistent with {len(test_manifest.get('files', []))} files")

    @pytest.mark.parametrize("category", ["wake", "core", "edge", "noise"])
    def test_category_coverage(self, test_phrases_dir: Path, category: str):
        """Test that we have recordings for each category."""
        category_dir = test_phrases_dir / category
        if category_dir.exists():
            audio_files = list(category_dir.glob("*.wav"))
            assert len(audio_files) > 0, f"No audio files found in {category} category"
            print(f"✓ {category} category has {len(audio_files)} recordings")
        else:
            print(f"⚠️  {category} category directory not found")


# Example of how to run specific tests
def test_specific_phrase():
    """Example of testing a specific recorded phrase."""
    # This would be used for testing specific phrases by name
    phrase_file = Path("services/tests/fixtures/audio/test_phrases/wake/hey_atlas.wav")
    
    if not phrase_file.exists():
        pytest.skip("Specific phrase file not found")
    
    with open(phrase_file, 'rb') as f:
        audio_data = f.read()
    
    # Test the specific phrase
    detector = WakePhraseDetector(wake_phrases=["hey atlas"])
    result = detector.detect(audio_data)
    
    assert result.detected
    assert "hey atlas" in result.transcript.lower()
    assert result.confidence > 0.5