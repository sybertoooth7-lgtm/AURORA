"""User schemas"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator


class UserCreate(BaseModel):
    """User creation schema"""
    email: EmailStr
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    # Upper bound matters as much as the lower one here: without it, a
    # multi-megabyte password gets run through 120,000 PBKDF2 rounds on
    # every login attempt -- a cheap CPU-exhaustion lever. NIST SP 800-63B
    # suggests supporting at least 64 characters; 128 is generous headroom
    # above any real passphrase.
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)


class UserResponse(BaseModel):
    """User response schema"""
    id: int
    email: str
    username: str
    full_name: str | None
    is_active: bool
    email_verified: bool = False
    created_at: datetime

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def _derive_email_verified(cls, data):
        """`email_verified` is derived from the ORM model's
        `email_verified_at` (null vs set), not a real column on this
        schema -- computed here rather than via @computed_field/@property
        purely because that combination isn't understood by our mypy
        version even with the pydantic plugin enabled."""
        if isinstance(data, dict):
            return data
        return {
            "id": data.id,
            "email": data.email,
            "username": data.username,
            "full_name": data.full_name,
            "is_active": data.is_active,
            "email_verified": getattr(data, "email_verified_at", None) is not None,
            "created_at": data.created_at,
        }


class TokenRequest(BaseModel):
    """Credentials accepted by the JSON token endpoint."""
    username: str = Field(max_length=64)
    password: str = Field(max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class EmailVerificationConfirm(BaseModel):
    token: str
