"""Payload management for CubeSat imaging mission.

Models a multispectral/imaging camera payload with power, data, and
thermal constraints.  The payload manager schedules imaging passes
based on ground station visibility and power budgets.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PayloadMode(Enum):
    OFF = "off"
    STANDBY = "standby"
    IMAGING = "imaging"
    DOWNLOADING = "downloading"


@dataclass
class ImageProduct:
    image_id: str
    timestamp: float
    latitude: float
    longitude: float
    resolution_m: float
    bands: List[str]
    data_size_bytes: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "timestamp": self.timestamp,
            "lat": self.latitude,
            "lon": self.longitude,
            "resolution_m": self.resolution_m,
            "bands": self.bands,
            "size_bytes": self.data_size_bytes,
        }


class ImagingPayload:
    """Multispectral imaging camera for CubeSat.

    Reference: similar to a CubeSat-grade multispectral camera
    (e.g., PlanetScope / SuperDove class).
    """

    def __init__(
        self,
        resolution_m: float = 3.0,
        fov_deg: float = 20.0,
        bands: Optional[List[str]] = None,
        power_w: float = 1.5,
        data_per_image_mb: float = 5.0,
        storage_capacity_mb: float = 2000.0,
        is_simulated: bool = True,
    ):
        self.resolution_m = resolution_m
        self.fov_deg = fov_deg
        self.bands = bands or ["red", "green", "blue", "nir"]
        self.power_w = power_w
        self.data_per_image_mb = data_per_image_mb
        self.storage_capacity_mb = storage_capacity_mb
        self.is_simulated = is_simulated
        self.mode = PayloadMode.OFF
        self._images: List[ImageProduct] = []
        self._used_storage_mb = 0.0
        self._image_counter = 0
        self._total_power_on_time_s = 0.0

    @property
    def storage_used_mb(self) -> float:
        return self._used_storage_mb

    @property
    def storage_free_mb(self) -> float:
        return self.storage_capacity_mb - self._used_storage_mb

    @property
    def image_count(self) -> int:
        return len(self._images)

    def power_on(self) -> None:
        self.mode = PayloadMode.STANDBY

    def power_off(self) -> None:
        self.mode = PayloadMode.OFF

    def capture(self, timestamp: float, latitude: float, longitude: float, duration_s: float = 1.0) -> Optional[ImageProduct]:
        if self.mode == PayloadMode.OFF:
            return None
        if self.storage_free_mb < self.data_per_image_mb:
            return None
        self.mode = PayloadMode.IMAGING
        self._image_counter += 1
        image = ImageProduct(
            image_id=f"img-{self._image_counter:06d}",
            timestamp=timestamp,
            latitude=latitude,
            longitude=longitude,
            resolution_m=self.resolution_m,
            bands=list(self.bands),
            data_size_bytes=int(self.data_per_image_mb * 1e6),
        )
        self._images.append(image)
        self._used_storage_mb += self.data_per_image_mb
        self._total_power_on_time_s += duration_s
        self.mode = PayloadMode.STANDBY
        return image

    def download_images(self, max_mb: float) -> List[ImageProduct]:
        """Simulate downloading images from storage to ground."""
        self.mode = PayloadMode.DOWNLOADING
        downloaded: List[ImageProduct] = []
        remaining_mb = max_mb
        while self._images and remaining_mb >= self.data_per_image_mb:
            img = self._images.pop(0)
            downloaded.append(img)
            self._used_storage_mb -= self.data_per_image_mb
            remaining_mb -= self.data_per_image_mb
        self.mode = PayloadMode.STANDBY
        return downloaded

    def flush_storage(self) -> None:
        self._images.clear()
        self._used_storage_mb = 0.0


class PayloadManager:
    """Top-level payload manager orchestrating multiple instruments."""

    def __init__(self):
        self._payloads: Dict[str, Any] = {}

    def add_payload(self, name: str, payload: Any) -> None:
        self._payloads[name] = payload

    def get_payload(self, name: str) -> Any:
        return self._payloads.get(name)

    def all_power_w(self) -> float:
        total = 0.0
        for p in self._payloads.values():
            if hasattr(p, "power_w") and hasattr(p, "mode"):
                if p.mode != PayloadMode.OFF:
                    total += p.power_w
        return total

    def status(self) -> Dict[str, Any]:
        return {
            name: {
                "mode": getattr(p, "mode", "unknown").value if hasattr(getattr(p, "mode", None), "value") else str(getattr(p, "mode", "unknown")),
                "power_w": getattr(p, "power_w", 0),
            }
            for name, p in self._payloads.items()
        }