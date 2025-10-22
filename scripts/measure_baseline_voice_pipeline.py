"""Measure baseline voice pipeline performance."""
import asyncio
import json
from pathlib import Path
import time

import httpx
import numpy as np


async def measure_baseline_accuracy():
    """Measure baseline transcription accuracy."""
    test_dir = Path("tests/fixtures/voice_pipeline")
    results = {
        "clean_accuracy": [],
        "noisy_accuracy": [],
        "latencies": [],
        "false_wake_detections": 0,
        "total_wake_tests": 0,
    }

    # Test clean audio
    clean_dir = test_dir / "clean"
    for wav_file in sorted(clean_dir.glob("*.wav")):
        ground_truth_file = wav_file.with_suffix(".txt")
        if not ground_truth_file.exists():
            continue

        ground_truth = ground_truth_file.read_text().strip()

        # Transcribe
        start = time.time()
        async with httpx.AsyncClient() as client:
            with open(wav_file, "rb") as f:
                files = {"file": (wav_file.name, f, "audio/wav")}
                response = await client.post(
                    "http://stt:9000/transcribe",
                    files=files,
                    timeout=30.0
                )
        latency = time.time() - start

        if response.status_code == 200:
            transcript = response.json().get("text", "")
            # Calculate word error rate (simplified)
            wer = calculate_wer(ground_truth, transcript)
            accuracy = max(0, 1.0 - wer)
            results["clean_accuracy"].append(accuracy)
            results["latencies"].append(latency)

    # Test noisy audio
    noisy_dir = test_dir / "noisy"
    for wav_file in sorted(noisy_dir.glob("*.wav")):
        ground_truth_file = wav_file.with_suffix(".txt")
        if not ground_truth_file.exists():
            continue

        ground_truth = ground_truth_file.read_text().strip()

        # Transcribe
        start = time.time()
        async with httpx.AsyncClient() as client:
            with open(wav_file, "rb") as f:
                files = {"file": (wav_file.name, f, "audio/wav")}
                response = await client.post(
                    "http://stt:9000/transcribe",
                    files=files,
                    timeout=30.0
                )
        latency = time.time() - start

        if response.status_code == 200:
            transcript = response.json().get("text", "")
            # Calculate word error rate (simplified)
            wer = calculate_wer(ground_truth, transcript)
            accuracy = max(0, 1.0 - wer)
            results["noisy_accuracy"].append(accuracy)
            results["latencies"].append(latency)

    # Calculate statistics
    baseline = {
        "clean_accuracy_mean": np.mean(results["clean_accuracy"]) if results["clean_accuracy"] else 0.0,
        "clean_accuracy_std": np.std(results["clean_accuracy"]) if results["clean_accuracy"] else 0.0,
        "noisy_accuracy_mean": np.mean(results["noisy_accuracy"]) if results["noisy_accuracy"] else 0.0,
        "noisy_accuracy_std": np.std(results["noisy_accuracy"]) if results["noisy_accuracy"] else 0.0,
        "latency_p50": np.percentile(results["latencies"], 50) if results["latencies"] else 0.0,
        "latency_p95": np.percentile(results["latencies"], 95) if results["latencies"] else 0.0,
        "false_wake_rate": results["false_wake_detections"] / results["total_wake_tests"] if results["total_wake_tests"] > 0 else 0,
        "sample_count": len(results["clean_accuracy"]) + len(results["noisy_accuracy"])
    }

    # Save results
    output_file = Path("docs/testing/voice-pipeline-baseline.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(baseline, f, indent=2)

    print(f"✓ Baseline measurements saved to {output_file}")
    return baseline

def calculate_wer(reference: str, hypothesis: str) -> float:
    """Calculate Word Error Rate."""
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()

    # Simple Levenshtein distance for WER
    d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]

    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j

    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i-1] == hyp_words[j-1]:
                d[i][j] = d[i-1][j-1]
            else:
                d[i][j] = min(d[i-1][j], d[i][j-1], d[i-1][j-1]) + 1

    return d[len(ref_words)][len(hyp_words)] / len(ref_words) if ref_words else 0.0

if __name__ == "__main__":
    asyncio.run(measure_baseline_accuracy())
