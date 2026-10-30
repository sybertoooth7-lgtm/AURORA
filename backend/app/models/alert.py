"""Alert model"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class Alert(Base):
    """Alert for significant findings"""
    __tablename__ = "alerts"

    # Alerts are listed per owner, newest first, and unread-only from both the
    # dashboard badge and the account roll-up. The composite read index keeps
    # the unread inbox ordered without a sort; the result index serves the
    # per-area filter (join on analysis_results).
    __table_args__ = (
        Index("ix_alerts_user_created", "user_id", "created_at"),
        Index("ix_alerts_user_read_created", "user_id", "is_read", "created_at"),
        Index("ix_alerts_user_result", "user_id", "analysis_result_id"),
    )

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
