"""Analysis endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.analysis import AnalysisCreate, AnalysisResponse
from app.models.analysis import Analysis
from typing import List

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/", response_model=AnalysisResponse)
async def create_analysis(
    analysis: AnalysisCreate,
    db: Session = Depends(get_db)
):
    """Create a new analysis"""
    # TODO: Implement full analysis creation with geospatial polygon
    db_analysis = Analysis(
        user_id=1,  # TODO: Get from auth
        analysis_type=analysis.analysis_type,
        status="pending",
        description=analysis.description
    )
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)
    return db_analysis


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db)
):
    """Get analysis by ID"""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.get("/", response_model=List[AnalysisResponse])
async def list_analyses(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """List analyses"""
    analyses = db.query(Analysis).offset(skip).limit(limit).all()
    return analyses
