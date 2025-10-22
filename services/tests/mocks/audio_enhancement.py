"""Mock audio enhancement utilities for testing."""

from typing import Any
from unittest.mock import MagicMock

import torch


class MockSpectralMaskEnhancement:
    """Mock SpectralMaskEnhancement for testing."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize mock enhancement."""
        self.enhance_batch = MagicMock()
        # Return realistic enhanced audio by default
        self.enhance_batch.return_value = torch.tensor([[0.1, 0.2, 0.3]])

    @classmethod
    def from_hparams(cls, *_args: Any, **_kwargs: Any) -> "MockSpectralMaskEnhancement":
        """Create mock from hyperparameters."""
        return cls()


def create_mock_audio_enhancer(
    enhancement_enabled: bool = True,
    enhancement_class: Any = None,
) -> Any:
    """Create a mock AudioEnhancer for testing.

    Args:
        enhancement_enabled: Whether enhancement should be enabled
        enhancement_class: Optional enhancement class to inject

    Returns:
        Configured AudioEnhancer instance
    """
    from services.common.audio_enhancement import AudioEnhancer

    if enhancement_class is None and enhancement_enabled:
        enhancement_class = MockSpectralMaskEnhancement

    return AudioEnhancer(
        enable_metricgan=enhancement_enabled,
        enhancement_class=enhancement_class,
    )
