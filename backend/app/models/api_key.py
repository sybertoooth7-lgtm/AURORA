"""API key model.

Long-lived credentials for machine/script access in place of a short-lived
JWT. The raw secret is never stored -- only a sha256 hash plus a short
display prefix, so a database dump can't be replayed as live keys.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class ApiKey(Base):
    """One persisted API key. ``revoked_at`` set => soft-deleted key."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    # First characters of the raw key, e.g. "aur_ab12cd34" -- shown in the UI
    # so owners can tell keys apart without seeing (or brute-forcing) the secret.
    prefix = Column(String(14), nullable=False)
    key_hash = Column(String(64), unique=True, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ApiKey(id={self.id}, prefix={self.prefix}, revoked={self.revoked_at is not None})>"
