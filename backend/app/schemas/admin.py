"""Admin API schemas."""

from pydantic import BaseModel

from app.schemas.user import UserResponse


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
    skip: int
    limit: int
