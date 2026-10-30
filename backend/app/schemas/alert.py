"""Alert schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertResponse(BaseModel):
    """One alert as returned to the dashboard and area detail pages."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_result_id: int
    alert_type: str
    title: str
    description: str
    is_read: bool
    created_at: datetime
    acknowledged_at: datetime | None


class AlertListResponse(BaseModel):
    """One page of alerts plus the total the filter matched."""

    total: int
    skip: int
    limit: int
    items: list[AlertResponse]
