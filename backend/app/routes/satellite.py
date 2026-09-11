"""Satellite imagery endpoints"""


from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.satellite_imagery import SatelliteImage

router = APIRouter(prefix="/satellite", tags=["Satellite Data"])


@router.get("/images", response_model=list[dict])
async def list_satellite_images(
    db: Session = Depends(get_db),
    source: str | None = None,
    skip: int = 0,
    limit: int = 100
):
    """List satellite images"""
    query = db.query(SatelliteImage)

    if source:
        query = query.filter(SatelliteImage.source == source)

    images = query.offset(skip).limit(limit).all()

    return [
        {
            "id": img.id,
            "source": img.source,
            "image_id": img.image_id,
            "date_acquired": img.date_acquired,
            "cloud_coverage": img.cloud_coverage,
            "resolution_m": img.resolution_m,
        }
        for img in images
    ]


@router.get("/sources")
async def get_available_sources():
    """Get available satellite data sources"""
    return {
        "sources": [
            "Sentinel-2",
            "Sentinel-1",
            "Landsat-8",
            "Landsat-9",
        ]
    }
