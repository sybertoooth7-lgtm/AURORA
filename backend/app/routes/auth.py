"""Registration, login, and logout endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import TokenRequest, TokenResponse, UserCreate, UserResponse
from app.security import (
    clear_failed_logins,
    create_access_token,
    get_current_user,
    hash_password,
    is_locked_out,
    record_failed_login,
    revoke_token,
    verify_password_or_dummy,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Separate from app.security.oauth2_scheme's tokenUrl-carrying instance so
# /auth/logout can accept a token without FastAPI's docs treating it as the
# thing that issues one; behaviourally identical (reads the Bearer header).
_bearer_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=True)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter((User.email == user.email) | (User.username == user.username)).first():
        raise HTTPException(status_code=409, detail="Email or username already registered")
    db_user = User(
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=hash_password(user.password),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/token", response_model=TokenResponse)
def token(credentials: TokenRequest, db: Session = Depends(get_db)):
    settings = get_settings()

    if is_locked_out(credentials.username):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many failed login attempts. Try again in "
                f"{settings.LOGIN_LOCKOUT_SECONDS // 60} minutes."
            ),
        )

    user = db.query(User).filter(User.username == credentials.username).first()
    # Always does real password-hashing work, even if `user` is None, so
    # the response time doesn't reveal whether the username exists.
    password_ok = verify_password_or_dummy(
        credentials.password, user.hashed_password if user else None
    )

    if not user or not password_ok:
        record_failed_login(credentials.username)
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    clear_failed_logins(credentials.username)
    return TokenResponse(access_token=create_access_token(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str = Depends(_bearer_scheme), _user: User = Depends(get_current_user)):
    """Revoke the current access token so it can't be used again, even
    though it hasn't naturally expired yet (e.g. after a shared/public
    device, or a suspected leak)."""
    revoke_token(token)
