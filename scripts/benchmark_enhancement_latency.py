"""Benchmark MetricGAN+ enhancement latency."""
import time

from speechbrain.inference.enhancement import SpectralMaskEnhancement
import torch


def benchmark_latency():
    """Measure enhancement latency for different audio lengths."""
    model = SpectralMaskEnhancement.from_hparams(
        source="speechbrain/metricgan-plus-voicebank",
        savedir="pretrained_models/metricgan-plus"
    )

    durations = [1, 3, 5]  # seconds
    results = {}

    for duration in durations:
        samples = 16000 * duration
        audio = torch.randn(1, samples)

        # Warmup
        _ = model.enhance_batch(audio, lengths=torch.tensor([1.0]))

        # Benchmark
        latencies = []
        for _ in range(10):
            start = time.time()
            _ = model.enhance_batch(audio, lengths=torch.tensor([1.0]))
            latencies.append(time.time() - start)

        avg_latency = sum(latencies) / len(latencies)
        results[f"{duration}s"] = f"{avg_latency * 1000:.0f}ms"
        print(f"✓ {duration}s audio: {avg_latency * 1000:.0f}ms avg latency")

    return results

if __name__ == "__main__":
    benchmark_latency()
