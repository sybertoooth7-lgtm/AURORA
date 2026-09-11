"""Tests for the auth hardening pass: lockout, timing-safe login, token
revocation, and the SECRET_KEY production guard.

Lockout/revocation tests need a real Redis (they exercise app.queue.get_redis()
directly) -- same expectation as running the app itself locally.
"""


import pytest
from pydantic import ValidationError

from app.config import DEFAULT_SECRET_KEY, Settings
from app.models.user import User
from app.queue import get_redis
from app.security import (
    clear_failed_logins,
    create_access_token,
    is_locked_out,
    record_failed_login,
    revoke_token,
    verify_password_or_dummy,
)


@pytest.fixture(autouse=True)
def _clean_redis():
    """Isolate each test's lockout/revocation keys."""
    redis = get_redis()
    for key in redis.keys("auth:*"):
        redis.delete(key)
    yield
    for key in redis.keys("auth:*"):
        redis.delete(key)


def test_verify_password_or_dummy_handles_missing_user():
    assert verify_password_or_dummy("anything", None) is False


def test_lockout_triggers_after_max_attempts():
    username = "lockout-test-user"
    assert not is_locked_out(username)

    for _ in range(5):
        record_failed_login(username)

    assert is_locked_out(username)


def test_lockout_clears_on_success():
    username = "lockout-clear-user"
    for _ in range(4):
        record_failed_login(username)
    assert not is_locked_out(username)  # one below the threshold

    clear_failed_logins(username)
    for _ in range(4):
        record_failed_login(username)
    assert not is_locked_out(username)  # counter was actually reset


def test_revoked_token_is_flagged_in_redis():
    user = User(id=1, username="revoke-test", email="r@test.com", is_active=True)
    token = create_access_token(user)

    revoke_token(token)

    import jwt as pyjwt

    from app.config import get_settings

    settings = get_settings()
    payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert get_redis().exists(f"auth:revoked:{payload['jti']}")


def test_secret_key_guard_rejects_default_in_production():
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", SECRET_KEY=DEFAULT_SECRET_KEY)


def test_secret_key_guard_rejects_short_key_in_production():
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", SECRET_KEY="short")


def test_secret_key_guard_allows_default_in_development():
    Settings(ENVIRONMENT="development", SECRET_KEY=DEFAULT_SECRET_KEY)


def test_secret_key_guard_allows_strong_key_in_production():
    Settings(ENVIRONMENT="production", SECRET_KEY="x" * 32)
