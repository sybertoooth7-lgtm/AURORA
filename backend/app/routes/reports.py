"""Analysis report exports."""

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.analysis import Analysis, AnalysisResult
from app.models.user import User
from app.security import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports"])


def _get_analysis(analysis_id: int, user_id: int, db: Session) -> Analysis:
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id, Analysis.user_id == user_id
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.get("/{analysis_id}")
def export_report(
    analysis_id: int,
    format: str = "json",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = _get_analysis(analysis_id, current_user.id, db)
    results = db.query(AnalysisResult).filter(AnalysisResult.analysis_id == analysis.id).all()
    records = [
        {
            "analysis_id": analysis.id,
            "analysis_type": analysis.analysis_type.value,
            "status": analysis.status,
            "latitude": analysis.latitude,
            "longitude": analysis.longitude,
            "radius_km": analysis.radius_km,
            "severity_score": result.severity_score,
            "confidence": result.confidence,
            "finding": result.finding,
            "metadata": json.loads(result.metadata_json) if result.metadata_json else {},
        }
        for result in results
    ]
    if format.lower() == "csv":
        output = io.StringIO()
        fieldnames = list(records[0].keys()) if records else ["analysis_id", "status"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
        return Response(output.getvalue(), media_type="text/csv")
    if format.lower() != "json":
        raise HTTPException(status_code=400, detail="format must be json or csv")
    return {"analysis": {"id": analysis.id, "status": analysis.status}, "results": records}
