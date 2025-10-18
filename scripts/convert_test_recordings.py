#!/usr/bin/env python3
"""
Convert test recordings from WebM to WAV format for Discord Voice Lab testing.

This script processes audio files recorded with the test-recorder.html interface
and converts them to the proper format expected by the testing infrastructure.

Usage:
    python scripts/convert_test_recordings.py input_dir output_dir
    python scripts/convert_test_recordings.py --help
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    import ffmpeg
except ImportError:
    print("Error: ffmpeg-python is required. Install with: pip install ffmpeg-python")
    sys.exit(1)


def convert_webm_to_wav(input_file: Path, output_file: Path, sample_rate: int = 48000) -> bool:
    """
    Convert WebM audio file to WAV format with specified sample rate.
    
    Args:
        input_file: Path to input WebM file
        output_file: Path to output WAV file
        sample_rate: Target sample rate (default: 48000 for Discord)
        
    Returns:
        True if conversion successful, False otherwise
    """
    try:
        # Create output directory if it doesn't exist
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert using ffmpeg
        (
            ffmpeg
            .input(str(input_file))
            .output(
                str(output_file),
                acodec='pcm_s16le',  # 16-bit PCM
                ac=1,                # Mono channel
                ar=sample_rate,      # Sample rate
                af='aresample=resampler=soxr'  # High-quality resampling
            )
            .overwrite_output()
            .run(quiet=True)
        )
        
        print(f"✓ Converted: {input_file.name} -> {output_file.name}")
        return True
        
    except ffmpeg.Error as e:
        print(f"✗ Error converting {input_file.name}: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error converting {input_file.name}: {e}")
        return False


def process_metadata_file(metadata_file: Path, input_dir: Path, output_dir: Path) -> Dict:
    """
    Process metadata file and convert associated audio files.
    
    Args:
        metadata_file: Path to JSON metadata file
        input_dir: Directory containing original audio files
        output_dir: Directory for converted audio files
        
    Returns:
        Dictionary with conversion results
    """
    try:
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
    except Exception as e:
        print(f"✗ Error reading metadata file: {e}")
        return {"error": str(e)}
    
    results = {
        "total_phrases": metadata.get("totalPhrases", 0),
        "converted": 0,
        "failed": 0,
        "converted_files": [],
        "failed_files": []
    }
    
    print(f"Processing {results['total_phrases']} phrases from metadata...")
    
    for phrase in metadata.get("phrases", []):
        phrase_id = phrase.get("id", "unknown")
        phrase_text = phrase.get("text", "unknown")
        category = phrase.get("category", "unknown")
        
        # Find the corresponding audio file
        # Look for WebM files that might match this phrase
        audio_files = list(input_dir.glob(f"*{phrase_id}*.webm"))
        if not audio_files:
            # Try to find by category and text pattern
            text_pattern = phrase_text.replace(" ", "_").replace("'", "").replace(",", "").replace("?", "").replace("!", "")
            audio_files = list(input_dir.glob(f"{category}_*{text_pattern[:20]}*.webm"))
        
        if not audio_files:
            print(f"⚠️  No audio file found for phrase: {phrase_text}")
            results["failed"] += 1
            results["failed_files"].append({
                "phrase_id": phrase_id,
                "text": phrase_text,
                "reason": "Audio file not found"
            })
            continue
        
        # Use the first matching file
        input_file = audio_files[0]
        
        # Create output filename
        safe_text = "".join(c for c in phrase_text if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_text = safe_text.replace(' ', '_')[:30]
        output_filename = f"{category}_{phrase_id}_{safe_text}.wav"
        output_file = output_dir / output_filename
        
        # Convert the file
        if convert_webm_to_wav(input_file, output_file):
            results["converted"] += 1
            results["converted_files"].append({
                "phrase_id": phrase_id,
                "text": phrase_text,
                "category": category,
                "input_file": str(input_file),
                "output_file": str(output_file)
            })
        else:
            results["failed"] += 1
            results["failed_files"].append({
                "phrase_id": phrase_id,
                "text": phrase_text,
                "input_file": str(input_file),
                "reason": "Conversion failed"
            })
    
    return results


def process_directory(input_dir: Path, output_dir: Path) -> Dict:
    """
    Process all WebM files in a directory and convert to WAV.
    
    Args:
        input_dir: Directory containing WebM files
        output_dir: Directory for converted WAV files
        
    Returns:
        Dictionary with conversion results
    """
    webm_files = list(input_dir.glob("*.webm"))
    
    if not webm_files:
        print(f"No WebM files found in {input_dir}")
        return {"error": "No WebM files found"}
    
    results = {
        "total_files": len(webm_files),
        "converted": 0,
        "failed": 0,
        "converted_files": [],
        "failed_files": []
    }
    
    print(f"Processing {len(webm_files)} WebM files...")
    
    for webm_file in webm_files:
        # Create output filename
        wav_filename = webm_file.stem + ".wav"
        wav_file = output_dir / wav_filename
        
        if convert_webm_to_wav(webm_file, wav_file):
            results["converted"] += 1
            results["converted_files"].append({
                "input_file": str(webm_file),
                "output_file": str(wav_file)
            })
        else:
            results["failed"] += 1
            results["failed_files"].append({
                "input_file": str(webm_file),
                "reason": "Conversion failed"
            })
    
    return results


def create_test_manifest(converted_files: List[Dict], output_dir: Path) -> None:
    """
    Create a test manifest file for the converted audio files.
    
    Args:
        converted_files: List of converted file information
        output_dir: Directory containing converted files
    """
    manifest = {
        "created_at": str(Path().cwd()),
        "total_files": len(converted_files),
        "format": {
            "sample_rate": 48000,
            "channels": 1,
            "bit_depth": 16,
            "encoding": "PCM"
        },
        "files": []
    }
    
    for file_info in converted_files:
        file_path = Path(file_info["output_file"])
        if file_path.exists():
            file_size = file_path.stat().st_size
            manifest["files"].append({
                "filename": file_path.name,
                "path": str(file_path.relative_to(output_dir)),
                "size_bytes": file_size,
                "phrase_id": file_info.get("phrase_id"),
                "text": file_info.get("text"),
                "category": file_info.get("category")
            })
    
    manifest_file = output_dir / "test_manifest.json"
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"✓ Created test manifest: {manifest_file}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Convert test recordings from WebM to WAV format for Discord Voice Lab testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert all WebM files in a directory
  python scripts/convert_test_recordings.py recordings/ converted/
  
  # Convert using metadata file
  python scripts/convert_test_recordings.py --metadata metadata.json recordings/ converted/
  
  # Convert with custom sample rate
  python scripts/convert_test_recordings.py --sample-rate 16000 recordings/ converted/
        """
    )
    
    parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing WebM audio files or metadata file"
    )
    
    parser.add_argument(
        "output_dir", 
        type=Path,
        help="Directory for converted WAV files"
    )
    
    parser.add_argument(
        "--metadata",
        type=Path,
        help="Path to JSON metadata file (if processing with metadata)"
    )
    
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=48000,
        help="Target sample rate for WAV files (default: 48000)"
    )
    
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Create a test manifest file for the converted files"
    )
    
    args = parser.parse_args()
    
    # Validate input
    if not args.input_dir.exists():
        print(f"Error: Input directory {args.input_dir} does not exist")
        sys.exit(1)
    
    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Converting test recordings...")
    print(f"Input: {args.input_dir}")
    print(f"Output: {args.output_dir}")
    print(f"Sample rate: {args.sample_rate} Hz")
    print()
    
    # Process files
    if args.metadata and args.metadata.exists():
        results = process_metadata_file(args.metadata, args.input_dir, args.output_dir)
    else:
        results = process_directory(args.input_dir, args.output_dir)
    
    # Print results
    print()
    print("=" * 50)
    print("CONVERSION RESULTS")
    print("=" * 50)
    
    if "error" in results:
        print(f"Error: {results['error']}")
        sys.exit(1)
    
    print(f"Total files: {results.get('total_files', results.get('total_phrases', 0))}")
    print(f"Converted: {results['converted']}")
    print(f"Failed: {results['failed']}")
    
    if results['failed'] > 0:
        print("\nFailed conversions:")
        for failed in results['failed_files']:
            print(f"  - {failed.get('input_file', 'unknown')}: {failed.get('reason', 'unknown error')}")
    
    # Create manifest if requested
    if args.manifest and results['converted'] > 0:
        print()
        create_test_manifest(results['converted_files'], args.output_dir)
    
    print(f"\n✓ Conversion complete! Files saved to: {args.output_dir}")
    
    if results['converted'] > 0:
        print("\nNext steps:")
        print("1. Copy the converted WAV files to services/tests/fixtures/audio/")
        print("2. Update your test cases to use the new audio files")
        print("3. Run tests with: make test")


if __name__ == "__main__":
    main()