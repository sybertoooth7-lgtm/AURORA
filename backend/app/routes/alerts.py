"""User alert endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alert import Alert
from app.models.user import User
from app.security import get_current_user

router = APIRouter(prefix="/alerts", tags=["Alerts"])


def _serialize(alert: Alert) -> dict:
    return {
        "id": alert.id,
        "analysis_result_id": alert.analysis_result_id,
        "alert_type": alert.alert_type,
        "title": alert.title,
        "description": alert.description,
        "is_read": alert.is_read,
        "created_at": alert.created_at,
        "acknowledged_at": alert.acknowledged_at,
    }


@router.get("", response_model=list[dict])
def list_alerts(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Alert).filter(Alert.user_id == current_user.id)
    if unread_only:
        query = query.filter(Alert.is_read.is_(False))
    return [_serialize(alert) for alert in query.order_by(Alert.created_at.desc()).all()]


@router.post("/{alert_id}/acknowledge", response_model=dict)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.query(Alert).filter(
        Alert.id == alert_id, Alert.user_id == current_user.id
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_read = True
    alert.acknowledged_at = datetime.now(UTC)
    db.commit()
    db.refresh(alert)
    return _serialize(alert)
