"""Schemas for the API-key endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    """Request to mint a new API key for the calling account."""

    name: str = Field(min_length=1, max_length=100)
    expires_days: int | None = Field(default=None, ge=1, le=365)


class ApiKeyCreated(BaseModel):
    """Creation response -- ``key`` is the plaintext secret, shown once."""

    id: int
    name: str
    prefix: str
    key: str
    expires_at: datetime | None
    created_at: datetime


class ApiKeyListEntry(BaseModel):
    """A key as listed later: no secret, just enough to identify it."""

    id: int
    name: str
    prefix: str
    revoked: bool
    expires_at: datetime | None
    created_at: datetime
    last_used_at: datetime | None


class ApiKeyListResponse(BaseModel):
    keys: list[ApiKeyListEntry]
    total: int
