"""Model registry (database-backed metadata about AI models/approaches)."""

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class AIModel(Base):
    """Versioned metadata for a model/approach powering a pipeline.

    Kept deliberately small: at MVP stage the models are band-math / rules /
    statistical approaches, so storing weights is unnecessary. What matters
    operationally is provenance -- which version is deployed, its status
    (prototype vs production vs archived), and the metrics that justify its
    status. Future ML stages record artifact references (paths/URIs) in the
    JSON column.
    """

    __tablename__ = "ai_models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    version = Column(String, nullable=False)
    status = Column(String, nullable=False, default="prototype")  # prototype|production|archived
    framework = Column(String, nullable=False, default="band-math")  # family, e.g. band-math|ml|rules|statistical
    description = Column(Text, nullable=True)
    parameters_json = Column("parameters", Text, nullable=True)  # JSON string of hyperparameters/refs
    metrics_json = Column("metrics", Text, nullable=True)  # JSON string of eval metrics (e.g. {"f1": 0.82})
    artifact_uri = Column(String, nullable=True)  # future: location of weights/bundle
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<AIModel(id={self.id}, name={self.name}, version={self.version}, status={self.status})>"
