"""Optional consistency between DB model metadata and running pipelines.

The DB is the system of record for *deployed/validated* model status. The
in-memory ``PipelineRegistry`` is the record for *which code is actually
running in this process*. On API startup we reconcile the two: pipeline
model metadata is stamped with the production status from the DB when one
exists, so a result never claims "production" unless the DB says so.
"""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.ai_model import AIModel

VALID_STATUSES = {"prototype", "production", "archived"}


class ModelValidationError(ValueError):
    """Raised for malformed model metadata."""


def canonical_metrics(metrics: dict[str, Any] | None) -> str | None:
    """Serialize metrics to a sorted JSON string (stable for comparisons)."""
    if not metrics:
        return None
    return json.dumps(metrics, sort_keys=True)


def serialize_model(row: AIModel) -> dict:
    """API-safe serialization of one AI model row."""
    return {
        "id": row.id,
        "name": row.name,
        "version": row.version,
        "status": row.status,
        "framework": row.framework,
        "description": row.description,
        "parameters": json.loads(row.parameters_json) if row.parameters_json else {},
        "metrics": json.loads(row.metrics_json) if row.metrics_json else {},
        "artifact_uri": row.artifact_uri,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_models(db: Session, name: str | None = None) -> list:
    query = db.query(AIModel)
    if name:
        query = query.filter(AIModel.name == name)
    return [serialize_model(row) for row in query.order_by(AIModel.name, AIModel.version).all()]


def get_model(db: Session, model_id: int) -> AIModel | None:
    return db.query(AIModel).filter(AIModel.id == model_id).first()


def create_model(
    db: Session,
    name: str,
    version: str,
    framework: str = "band-math",
    description: str | None = None,
    parameters: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    artifact_uri: str | None = None,
    status: str = "prototype",
) -> dict:
    """Register a new model version. New versions always start as prototype."""
    if status not in VALID_STATUSES:
        raise ModelValidationError(f"Invalid status '{status}'; must be one of {sorted(VALID_STATUSES)}")
    row = AIModel(
        name=name,
        version=version,
        status=status,
        framework=framework,
        description=description,
        parameters_json=json.dumps(parameters or {}, sort_keys=True),
        metrics_json=canonical_metrics(metrics),
        artifact_uri=artifact_uri,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_model(row)


def set_status(db: Session, model_id: int, status: str) -> dict | None:
    """Promote/archive a model. Returns None when the model doesn't exist."""
    if status not in VALID_STATUSES:
        raise ModelValidationError(f"Invalid status '{status}'; must be one of {sorted(VALID_STATUSES)}")
    row = get_model(db, model_id)
    if row is None:
        return None
    row.status = status
    row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return serialize_model(row)


def production_version_of(db: Session, name: str) -> AIModel | None:
    """Active production status for a model name (for registry reconciliation)."""
    return (
        db.query(AIModel)
        .filter(AIModel.name == name, AIModel.status == "production")
        .order_by(AIModel.id.desc())
        .first()
    )
