"""Administrative endpoints -- listing and disabling/enabling accounts.

Everything here is gated by app.security.require_admin. There is
deliberately no API to grant is_admin itself: that has to be set
directly in the database by whoever operates the deployment. An
API endpoint that could mint admins would just move the same
privileged-access problem one level up rather than solving it, and at
this scale (one operator, direct DB access) a manual UPDATE is both
simpler and harder to abuse than any self-serve mechanism would be.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import ConflictError, NotFoundError
from app.logging_conf import get_logger
from app.models.user import User
from app.schemas.admin import UserListResponse
from app.schemas.user import UserResponse
from app.security import require_admin

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users", response_model=UserListResponse)
def list_users(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    limit = min(limit, 200)
    total = db.query(User).count()
    users = db.query(User).order_by(User.id).offset(skip).limit(limit).all()
    return UserListResponse(users=users, total=total, skip=skip, limit=limit)


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError(f"User {user_id} not found")
    return user


@router.post("/users/{user_id}/disable", response_model=UserResponse)
def disable_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if user_id == admin.id:
        raise ConflictError("You can't disable your own account.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError(f"User {user_id} not found")

    user.is_active = False
    # Kill every outstanding session immediately, not just future logins --
    # disabling an account should mean "logged out everywhere right now",
    # especially if this is being done because the account is compromised.
    user.token_version += 1
    db.commit()
    db.refresh(user)

    logger.info(
        "User disabled",
        extra_keys={"user_id": user.id, "username": user.username, "actor": admin.username},
    )
    return user


@router.post("/users/{user_id}/enable", response_model=UserResponse)
def enable_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError(f"User {user_id} not found")

    user.is_active = True
    db.commit()
    db.refresh(user)

    logger.info(
        "User enabled",
        extra_keys={"user_id": user.id, "username": user.username, "actor": admin.username},
    )
    return user
