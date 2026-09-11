"""Schemas for the /ai inference and model-management endpoints."""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.analysis import AnalysisType


class InferRequest(BaseModel):
    """Synchronous inference request against an area of interest."""

    analysis_type: AnalysisType
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=500)
    use_history: bool = True
    description: Optional[str] = Field(default=None, max_length=500)


class ModelIdentityResponse(BaseModel):
    name: str
    version: str
    kind: str


class LabelResponse(BaseModel):
    class_: str = Field(alias="class")
    confidence: float
    attributes: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class PipelineResultResponse(BaseModel):
    """Serialized PipelineResult returned by /ai/infer and analysis results."""

    analysis_type: str
    severity: float
    confidence: float
    findings: List[str]
    metrics: Dict[str, float]
    provenance: str
    simulated: bool
    source: str
    image_id: str
    acquired_at: datetime
    model: ModelIdentityResponse
    preprocessing: List[str]
    labels: List[LabelResponse] = Field(default_factory=list)
    warning: Optional[str] = None
    history_length: int = 0
    analysis_id: Optional[int] = None


class InferResponse(BaseModel):
    """Envelope returned by POST /ai/infer."""

    result: PipelineResultResponse
    created_analysis_id: int


class ModelCreate(BaseModel):
    """Register a new model version."""

    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    framework: str = Field(default="band-math", max_length=60)
    description: Optional[str] = Field(default=None, max_length=500)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    artifact_uri: Optional[str] = Field(default=None, max_length=500)
    status: str = "prototype"

    @field_validator("metrics", "parameters")
    @classmethod
    def _json_safe(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import json

            json.dumps(value)
        except (TypeError, ValueError) as exc:  # noqa: B014 - json raises TypeError/ValueError
            raise ValueError("Must be JSON-serialisable") from exc
        return value


class ModelResponse(BaseModel):
    id: int
    name: str
    version: str
    status: str
    framework: str
    description: Optional[str]
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    artifact_uri: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class ModelStatusUpdate(BaseModel):
    """Target status for promote/archive (`VALID_STATUSES` enforced in repo)."""

    status: str


class PipelineDescription(BaseModel):
    name: str
    description: str
    handles: List[str]
    model: ModelIdentityResponse
    preprocessing: List[str]
    data_requirements: Dict[str, Any] = Field(default_factory=dict)