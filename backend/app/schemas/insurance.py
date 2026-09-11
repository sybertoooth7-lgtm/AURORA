"""Schemas for the parametric-agriculture-insurance endpoints (AURORA-2)."""


from pydantic import BaseModel, Field, field_validator

from app.config import get_settings
from app.schemas.ai import PipelineResultResponse


class TriggerCheckRequest(BaseModel):
    """One trigger-check against a policy/area.

    ``sum_insured_usd`` is the policy limit; the platform returns an honest
    *estimate* (severity-adjusted) but never a binding settlement -- the
    prototype pipeline has not been validated against loss-adjuster ground
    truth, and that is disclosed in the response.
    """

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=500)
    use_history: bool = True
    sum_insured_usd: float = Field(gt=0)
    coverage_ratio: float = Field(default=1.0, gt=0, le=1)
    trigger_threshold: float = Field(default=get_settings().INSURANCE_DEFAULT_TRIGGER_THRESHOLD, ge=0, le=1)
    crop_type: str | None = Field(default=None, max_length=80)
    policy_id: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("sum_insured_usd")
    @classmethod
    def _respect_policy_limit(cls, value: float) -> float:
        limit = get_settings().INSURANCE_MAX_SUM_INSURED_USD
        if value > limit:
            raise ValueError(
                f"sum_insured_usd exceeds the configured policy limit of {limit:,.0f} USD"
            )
        return value


class TriggerCheckResponse(BaseModel):
    """Result of a trigger-check, with provenance and payout estimate.

    ``estimated_liability_usd`` is ``sum_insured * severity`` under the
    proportional model; ``payout_usd`` is that amount only when the trigger
    threshold is breached, else zero. These are estimates for planning, not
    a binding settlement acknowledgment.
    """

    result: PipelineResultResponse
    analysis_id: int
    policy_id: str | None = None
    crop_type: str | None = None
    trigger_threshold: float
    severity_at_check: float
    trigger_breached: bool
    estimated_liability_usd: float
    payout_usd: float
    coverage_ratio: float
    data_quality: str
    warning: str | None = None
