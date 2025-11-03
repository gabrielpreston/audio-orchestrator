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
    from unittest.mock import Mock, patch

    from services.common.audio_enhancement import AudioEnhancer

    if enhancement_class is None and enhancement_enabled:
        enhancement_class = MockSpectralMaskEnhancement

    # Mock BackgroundModelLoader for the new lazy-loading pattern
    mock_loader = Mock()
    if enhancement_enabled:
        mock_loader.is_loaded.return_value = True
        mock_model = Mock()
        import torch

        mock_model.enhance_batch.return_value = torch.tensor([[0.1, 0.2, 0.3]])
        mock_loader.get_model.return_value = mock_model
    else:
        mock_loader.is_loaded.return_value = False
        mock_loader.get_model.return_value = None
    mock_loader.is_loading.return_value = False

    with patch(
        "services.common.audio_enhancement.BackgroundModelLoader",
        return_value=mock_loader,
    ):
        enhancer = AudioEnhancer(
            enable_metricgan=enhancement_enabled,
            enhancement_class=enhancement_class,
        )
        # Store the mock loader for tests that need to access it
        enhancer._model_loader = mock_loader
        return enhancer
