"""Perception engine: computer vision, object detection, segmentation.

Abstract PerceptionEngine that can be backed by:
- A lightweight CV model (OpenCV-based, runs anywhere).
- A deep-learning model (PyTorch/ONNX, optional dependency).
- A simulation stub that returns synthetic detections.

Used by both Earth robots (crop/weed detection, infrastructure inspection)
and by the spacecraft / multi-planetary layers (hazard detection, terrain
classification).  The interface is intentionally identical.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DetectionClass(Enum):
    """Broad object categories the perception system can return."""
    UNKNOWN = "unknown"
    OBSTACLE = "obstacle"
    CROP = "crop"
    WEED = "weed"
    ROAD = "road"
    WATER = "water"
    BUILDING = "building"
    HAZARD = "hazard"
    ROCK = "rock"
    CRATER = "crater"
    ROVER = "rover"
    LANDER = "lander"


@dataclass
class BBox2D:
    """Axis-aligned 2D bounding box in pixel coordinates."""
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def area(self) -> float:
        return self.width * self.height

    def iou(self, other: "BBox2D") -> float:
        ix1 = max(self.x_min, other.x_min)
        iy1 = max(self.y_min, other.y_min)
        ix2 = min(self.x_max, other.x_max)
        iy2 = min(self.y_max, other.y_max)
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0


@dataclass
class Detection:
    """A single detected object in a frame."""
    bbox: BBox2D
    detection_class: DetectionClass
    confidence: float
    depth_m: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bbox": {"x_min": self.bbox.x_min, "y_min": self.bbox.y_min,
                     "x_max": self.bbox.x_max, "y_max": self.bbox.y_max},
            "class": self.detection_class.value,
            "confidence": round(self.confidence, 4),
            "depth_m": self.depth_m,
            "attributes": self.attributes,
        }


@dataclass
class SegmentationMask:
    """Per-pixel class map from semantic segmentation."""
    width: int
    height: int
    class_map: list[list[int]]  # [y][x] -> class_id
    class_names: dict[int, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PerceptionResult:
    """Output of one perception pass over one frame / point cloud."""
    timestamp: float
    detections: list[Detection]
    segmentation: SegmentationMask | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def obstacle_count(self) -> int:
        return sum(1 for d in self.detections
                   if d.detection_class in (DetectionClass.OBSTACLE, DetectionClass.HAZARD, DetectionClass.ROCK, DetectionClass.CRATER))

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "detections": [d.to_dict() for d in self.detections],
            "obstacle_count": self.obstacle_count(),
            "metadata": self.metadata,
        }


class PerceptionEngine(ABC):
    """Abstract perception engine.

    ``process_frame()`` receives raw image bytes or a numpy array and
    returns detections + optional segmentation.  The concrete backend
    decides whether it runs OpenCV heuristics, a YOLOv8 ONNX model,
    a depthAnything model, or simply returns synthetic detections for
    simulation testing.
    """

    model_name: str = "none"
    is_simulated: bool = True

    @abstractmethod
    def process_frame(
        self,
        frame: Any,
        timestamp: float,
        camera_intrinsic: dict[str, float] | None = None,
    ) -> PerceptionResult:
        """Run detection + optional segmentation on one frame."""

    def initialize(self) -> None:
        """Load model weights / initialize OpenCV pipeline."""

    def shutdown(self) -> None:
        pass


class SyntheticPerceptionEngine(PerceptionEngine):
    """Deterministic simulation stub.

    Returns a fixed set of detections based on the robot's simulated
    world state.  Used for unit tests and offline simulation where no
    real camera or ML model is available.
    """

    model_name = "synthetic"
    is_simulated = True

    def __init__(self, obstacles: list[dict[str, Any]] | None = None):
        self._obstacles = obstacles or []

    def process_frame(
        self,
        frame: Any,
        timestamp: float,
        camera_intrinsic: dict[str, float] | None = None,
    ) -> PerceptionResult:
        detections: list[Detection] = []
        for obs in self._obstacles:
            detections.append(Detection(
                bbox=BBox2D(obs.get("x_min", 0), obs.get("y_min", 0),
                            obs.get("x_max", 50), obs.get("y_max", 50)),
                detection_class=DetectionClass(obs.get("class", "obstacle")),
                confidence=obs.get("confidence", 0.9),
                depth_m=obs.get("depth_m"),
            ))
        return PerceptionResult(
            timestamp=timestamp,
            detections=detections,
            metadata={"backend": "synthetic"},
        )
