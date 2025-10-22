"""Test MetricGAN+ model loading and enhancement."""
from speechbrain.inference.enhancement import SpectralMaskEnhancement
import torch


def test_metricgan():
    """Test MetricGAN+ model loading."""
    try:
        # Test model loading
        model = SpectralMaskEnhancement.from_hparams(
            source="speechbrain/metricgan-plus-voicebank",
            savedir="pretrained_models/metricgan-plus"
        )

        # Test with sample audio (1 second at 16kHz)
        audio = torch.randn(1, 16000)
        enhanced = model.enhance_batch(audio, lengths=torch.tensor([1.0]))

        print("✓ MetricGAN+ model loaded successfully")
        print(f"✓ Enhancement test passed: {enhanced.shape}")
        return True
    except Exception as e:
        print(f"✗ MetricGAN+ test failed: {e}")
        return False

if __name__ == "__main__":
    test_metricgan()
