"""User schemas"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    """User creation schema"""
    email: EmailStr
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=200)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value = value.strip().casefold()
        if not value:
            raise ValueError("username must not be blank")
        return value

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if (
            not any(char.islower() for char in value)
            or not any(char.isupper() for char in value)
            or not any(char.isdigit() for char in value)
            or not any(not char.isalnum() for char in value)
        ):
            raise ValueError(
                "password must include lowercase, uppercase, digit, and special character"
            )
        return value


class UserResponse(BaseModel):
    """User response schema"""
    id: int
    email: str
    username: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenRequest(BaseModel):
    """Credentials accepted by the JSON token endpoint."""
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().casefold()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
