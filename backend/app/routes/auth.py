"""Registration and access-token endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import TokenRequest, TokenResponse, UserCreate, UserResponse
from app.security import (
    _DUMMY_PASSWORD_HASH,
    create_access_token,
    get_current_user,
    hash_password,
    oauth2_scheme,
    verify_password,
)
from app.rate_limit import record_login_attempt, revoke_token
import jwt
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    email = str(user.email).casefold()
    if db.query(User).filter(
        (User.email == email) | (User.username == user.username)
    ).first():
        raise HTTPException(status_code=409, detail="Email or username already registered")
    db_user = User(
        email=email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=hash_password(user.password),
    )
    db.add(db_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email or username already registered")
    db.refresh(db_user)
    return db_user


@router.post("/token", response_model=TokenResponse)
async def token(credentials: TokenRequest, request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    try:
        ip_count, ip_retry_after = await record_login_attempt(f"ip:{client_ip}")
        username_count, username_retry_after = await record_login_attempt(
            f"username:{credentials.username}"
        )
    except RedisError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login rate limiter unavailable",
        )
    if (
        ip_count > settings.LOGIN_RATE_LIMIT_REQUESTS
        or username_count > settings.LOGIN_RATE_LIMIT_REQUESTS
    ):
        retry_after = max(ip_retry_after, username_retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts",
            headers={"Retry-After": str(retry_after)},
        )
    user = db.query(User).filter(User.username == credentials.username).first()
    password_hash = user.hashed_password if user else _DUMMY_PASSWORD_HASH
    if not verify_password(credentials.password, password_hash) or (
        user is not None and not user.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    token: str = Depends(oauth2_scheme),
    _current_user: User = Depends(get_current_user),
):
    """Revoke the current access token until it expires."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
        options={"verify_exp": False},
    )
    try:
        revoke_token(payload["jti"], int(payload["exp"]))
    except RedisError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token revocation service unavailable",
        )


@router.get("/me", response_model=UserResponse)
def current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's profile from the database."""
    return current_user