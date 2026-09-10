"""Authentication helpers for the API."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.rate_limit import is_token_revoked

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
_PBKDF2_ITERATIONS = 600_000
_DUMMY_PASSWORD_HASH = (
    "pbkdf2_sha256$600000$"
    "0123456789abcdef0123456789abcdef$"
    "8f3c7e4b0d4a4c9d7d0b4e7b8a8f5e5c7a9f8d4c3b2a19081716151413121110"
)


def hash_password(password: str) -> str:
    """Hash a password with a slow, salted standard-library primitive."""
    if len(password.encode("utf-8")) > 512:
        raise ValueError("password is too long")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Check a password hash without exposing timing information."""
    try:
        if len(password.encode("utf-8")) > 512:
            return False
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(rounds)
        if iterations < 100_000 or iterations > 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError, UnicodeError):
        return False


def create_access_token(user: User) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        {
            "sub": str(user.id),
            "username": user.username,
            "type": "access",
            "jti": secrets.token_urlsafe(24),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "exp": expires,
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
        headers={"typ": "JWT"},
    )


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    settings = get_settings()
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload: Any = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={"require": ["exp", "sub", "iss", "aud", "type", "jti"]},
        )
        if not isinstance(payload, dict):
            raise credentials_error
        if payload.get("type") != "access" or not isinstance(payload.get("jti"), str):
            raise credentials_error
        if is_token_revoked(payload["jti"]):
            raise credentials_error
        user_id = int(payload["sub"])
    except RedisError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token revocation service unavailable",
        )
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise credentials_error

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise credentials_error
    return user