"""Schemas for field-boundary crop analysis."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAX_RING_VERTICES = 250


class FieldBoundary(BaseModel):
    """A GeoJSON polygon defining the field to analyse.

    Only a single outer ring (no interior holes) is accepted so the boundary
    maps 1:1 onto the PostGIS POLYGON column and the satellite survey stays a
    single contiguous coverage area.
    """

    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[list[float]]]

    @field_validator("coordinates")
    @classmethod
    def _validate_ring(cls, rings: list[list[list[float]]]) -> list[list[list[float]]]:
        if len(rings) != 1:
            raise ValueError("field boundary must describe a single ring (interior holes are not supported)")
        ring = rings[0]
        if len(ring) < 4:
            raise ValueError("field boundary ring must have at least 4 positions (a closed ring)")
        if len(ring) > MAX_RING_VERTICES + 1:
            raise ValueError(f"field boundary ring exceeds the {MAX_RING_VERTICES} vertex limit")
        if ring[0] != ring[-1]:
            raise ValueError("field boundary ring must be closed (first position equals last)")
        if len({tuple(pos) for pos in ring[:-1]}) < 3:
            raise ValueError("field boundary ring is degenerate (fewer than 3 distinct vertices)")
        for pos in ring:
            if len(pos) < 2:
                raise ValueError("GeoJSON position must be [longitude, latitude]")
            lon, lat = pos[0], pos[1]
            if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
                raise ValueError("GeoJSON position out of range (longitude in [-180, 180], latitude in [-90, 90])")
        return rings


class CropAnalysisRequest(BaseModel):
    """Analyse a crop field from its boundary polygon.

    The boundary is taken as-is; the route derives the satellite survey area
    (centroid + covering radius) from it, so callers never have to.
    """

    field_boundary: FieldBoundary
    use_history: bool = True
    description: str | None = Field(default=None, max_length=500)


class CropObservationResponse(BaseModel):
    """The satellite observation the report is based on."""

    source: str
    image_id: str
    acquired_at: datetime
    cloud_coverage: float
    resolution_m: float
    simulated: bool


class CropAnalysisResponse(BaseModel):
    """End-to-end crop report over a field boundary.

    ``provenance`` repeats the observation's honesty flag at the top level so
    a simulated run can never be mistaken for real data, and ``report`` holds
    the human-readable lines rendered from the analysis.
    """

    analysis_id: int
    boundary: FieldBoundary
    boundary_wkt: str
    latitude: float
    longitude: float
    radius_km: float
    observation: CropObservationResponse
    ndvi: float
    change_score: float
    condition: str
    severity: float
    confidence: float
    findings: list[str]
    metrics: dict[str, float]
    model: str
    provenance: Literal["real", "simulated"]
    report: list[str]
