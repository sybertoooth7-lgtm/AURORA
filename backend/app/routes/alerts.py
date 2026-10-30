"""User alert endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alert import Alert
from app.models.analysis import AnalysisResult
from app.models.user import User
from app.schemas.alert import AlertListResponse, AlertResponse
from app.security import get_current_user

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=AlertListResponse)
def list_alerts(
    unread_only: bool = False,
    analysis_id: int | None = Query(None, ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """One page of the caller's alerts, newest first.

    Bounded on purpose: alerts accumulate for the life of an account, and the
    old unbounded list made every inbox poll cost grow with history. ``total``
    counts everything the filters matched so the client can page honestly.
    ``analysis_id`` joins through the result, which lets an area detail page
    ask for just its own alerts instead of loading the whole inbox and
    filtering in the browser.
    """
    query = db.query(Alert).filter(Alert.user_id == current_user.id)
    if unread_only:
        query = query.filter(Alert.is_read.is_(False))
    if analysis_id is not None:
        query = query.join(
            AnalysisResult, Alert.analysis_result_id == AnalysisResult.id
        ).filter(AnalysisResult.analysis_id == analysis_id)
    total = query.count()
    items = (
        query.order_by(Alert.created_at.desc(), Alert.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
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
    return alert
