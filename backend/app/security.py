"""Authentication helpers for the API."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.queue import get_redis

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# A password hash of *something* (not a real password, just a fixed
# constant) that verify_password can always run against when no user was
# found. Without this, a login request for a nonexistent username returns
# faster than one for a real username with a wrong password -- an easy way
# to enumerate valid usernames from response timing alone. Comparing
# against a constant-shape hash costs the same PBKDF2 work either way.
_DUMMY_HASH = (
    "pbkdf2_sha256$120000$0000000000000000000000000000000000$"
    "0000000000000000000000000000000000000000000000000000000000000000"
)


def hash_password(password: str) -> str:
    """Hash a password with a slow, salted standard-library primitive."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
    )
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Check a password hash without exposing timing information."""
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(rounds)
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


def verify_password_or_dummy(password: str, encoded: str | None) -> bool:
    """Like verify_password, but always does real PBKDF2 work even when
    `encoded` is None (i.e. the username wasn't found), so a login attempt
    against a nonexistent account takes the same time as a wrong password
    against a real one."""
    return verify_password(password, encoded or _DUMMY_HASH)


# --- Login lockout (per-account, Redis-backed) -----------------------------
#
# The general API rate limiter is per-IP and far too loose to stop
# brute-forcing a single account (it's easy to spray guesses at one
# username from many source IPs). This tracks failed attempts per
# *username* instead, so distributing the attempts doesn't help.

def _lockout_key(username: str) -> str:
    return f"auth:lockout:{username.lower()}"


def _attempts_key(username: str) -> str:
    return f"auth:attempts:{username.lower()}"


def is_locked_out(username: str) -> bool:
    return bool(get_redis().exists(_lockout_key(username)))


def record_failed_login(username: str) -> None:
    settings = get_settings()
    redis = get_redis()
    key = _attempts_key(username)
    attempts = redis.incr(key)
    if attempts == 1:
        redis.expire(key, settings.LOGIN_LOCKOUT_SECONDS)
    if attempts >= settings.LOGIN_MAX_ATTEMPTS:
        redis.set(_lockout_key(username), "1", ex=settings.LOGIN_LOCKOUT_SECONDS)


def clear_failed_logins(username: str) -> None:
    redis = get_redis()
    redis.delete(_attempts_key(username), _lockout_key(username))


# --- Tokens ------------------------------------------------------------

def create_access_token(user: User) -> str:
    settings = get_settings()
    expires = datetime.now(UTC) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        {
            "sub": str(user.id),
            "username": user.username,
            "exp": expires,
            "jti": secrets.token_hex(16),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except jwt.PyJWTError:
        raise credentials_error from None
    return payload


def revoke_token(token: str) -> None:
    """Blocklist a token's jti in Redis until it would have expired anyway.

    Access tokens are short-lived (30 min by default), so the blocklist
    entry is cheap and self-cleans -- no unbounded growth.
    """
    payload = _decode_token(token)
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return
    ttl = int(exp - datetime.now(UTC).timestamp())
    if ttl > 0:
        get_redis().set(f"auth:revoked:{jti}", "1", ex=ttl)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = _decode_token(token)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise credentials_error from None

    jti = payload.get("jti")
    if jti and get_redis().exists(f"auth:revoked:{jti}"):
        raise credentials_error

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise credentials_error
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency for administrative actions (e.g. promoting models)."""
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return current_user
