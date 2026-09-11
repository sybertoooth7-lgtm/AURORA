"""Alert model"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class Alert(Base):
    """Alert for significant findings"""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    analysis_result_id = Column(Integer, ForeignKey("analysis_results.id"), nullable=False)
    alert_type = Column(String, nullable=False)  # critical, warning, info
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Alert(id={self.id}, type={self.alert_type})>"
