"""User schemas"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


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
    created_at: datetime

    class Config:
        from_attributes = True


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
