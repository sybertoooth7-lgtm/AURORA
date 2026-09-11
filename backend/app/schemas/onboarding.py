"""Schemas for the onboarding flow (AURORA-2 conversion milestone)."""


from pydantic import BaseModel, Field

from app.models.analysis import AnalysisType
from app.schemas.ai import PipelineResultResponse


class OnboardingChecklistItem(BaseModel):
    id: str
    label: str
    done: bool
    instructions: str | None = None


class OnboardingStatus(BaseModel):
    user_id: int
    username: str
    completed: bool
    progress: int  # 0..100
    checklist: list[OnboardingChecklistItem]
    next_action: str


class FirstAnalysisRequest(BaseModel):
    """Guided first analysis: pick a pipeline target + an area of interest."""

    analysis_type: AnalysisType = AnalysisType.VEGETATION_STRESS
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=500)
    use_history: bool = True
    description: str | None = Field(default=None, max_length=500)


class FirstAnalysisResponse(BaseModel):
    result: PipelineResultResponse
    created_analysis_id: int
    next_steps: list[str]
