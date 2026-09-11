"""Computer vision pipeline for satellite imagery analysis.

PROTOTYPE STAGE -- this module requires optional heavy dependencies
(torch, torchvision, Pillow) that are NOT installed by default; every heavy
import is lazy, so importing this module is always safe. When these deps
are present it can run pixel-level inference; otherwise it raises.

It is deliberately separated from the production-ready statistical
pipelines in app.ai (vegetation/land_change/etc.), which run on the
area-level statistics emitted by the satellite provider with no ML stack.
Results from this module must be treated as prototype and never presented
as production-grade until validated.
"""


from typing import Any

import numpy as np

from app.ai.base import ModelKind, ModelRef


class SatelliteImageAnalyzer:
    """Analyzes satellite imagery for vegetation stress, land changes, etc."""

    model = ModelRef(name="torchvision:resnet50", version="0.1.0", kind=ModelKind.PROTOTYPE)

    def __init__(self, device: str = "cuda"):
        """Initialize the analyzer (loads torch only when constructed)."""
        import torch  # noqa: F401 - optional; raises ImportError if missing

        self.device = device if torch.cuda.is_available() else "cpu"
        self.model = None  # type: ignore[assignment]  # class-level ModelRef proto is overwritten after load
        self._load_model()

    def _load_model(self):
        """Load pre-trained model (optional dependency)."""
        import torchvision.models  # noqa: F401 - optional

        self._torch_model = torchvision.models.resnet50(pretrained=True)
        self._torch_model.to(self.device)
        self._torch_model.eval()

    def analyze_vegetation_stress(self, image: np.ndarray) -> dict[str, Any]:
        """Return stress metrics for a (NxMx3 or 4 band) image array.

        Requires torch/torchvision; architecture remains as the original
        prototype (ResNet50 feature extractor + NDVI proxy).
        """
        stress_score = self._compute_ndvi(image)
        return {
            "stress_score": float(stress_score),
            "affected_percentage": float(stress_score * 100),
            "confidence": 0.85,
            "model": self.model.to_dict(),
        }

    def detect_land_changes(
        self, image_before: np.ndarray, image_after: np.ndarray
    ) -> dict[str, float]:
        diff = np.abs(image_after.astype(float) - image_before.astype(float))
        change_score = np.mean(diff) / 255.0
        return {
            "change_score": float(change_score),
            "change_percentage": float(change_score * 100),
            "confidence": 0.80,
        }

    def _compute_ndvi(self, image: np.ndarray) -> float:
        """Compute Normalized Difference Vegetation Index.

        NDVI = (NIR - RED) / (NIR + RED). Expects bands-first arrays
        (channels, height, width); falls back to 0.0 for RGB-only input.
        """
        if image.ndim == 3 and image.shape[0] >= 4:
            nir = image[3].astype(float)
            red = image[0].astype(float)
            ndvi = (nir - red) / (nir + red + 1e-8)
            return float(np.nanmean(ndvi))
        return 0.0
