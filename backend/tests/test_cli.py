"""Operator CLI tests.

The CLI writes against the same in-process demo database the app tests use
(SessionLocal is shared), so every command is exercised for real: boot the
first admin, promote/revoke, list, and force-verify, including the env-var
password route that keeps secrets out of shell history.
"""


import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models.user import User
from app.security import verify_password
from cli import main
from main import app


def _user(username: str) -> User | None:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == username).first()
    finally:
        db.close()


class TestCli:
    def test_create_admin_boots_first_operator(self):
        code = main(["create-admin", "root_admin", "--password", "rootpass123"])
        assert code == 0
        user = _user("root_admin")
        assert user is not None
        assert user.is_admin is True
        assert user.is_active is True
        assert user.email_verified_at is not None
        assert user.onboarding_completed_at is not None
        assert verify_password("rootpass123", user.hashed_password)

    def test_create_existing_user_fails(self):
        with pytest.raises(SystemExit, match="already exists"):
            main(["create-admin", "root_admin", "--password", "rootpass123"])

    def test_set_revoke_cycle(self):
        code = main(["set-admin", "root_admin", "--password", "rotated-pass-456"])
        assert code == 0
        user = _user("root_admin")
        assert user.is_admin is True
        assert verify_password("rotated-pass-456", user.hashed_password)
        # password rotation bumped token_version so old JWTs die.
        assert user.token_version == 1

        assert main(["revoke-admin", "root_admin"]) == 0
        assert _user("root_admin").is_admin is False

        assert main(["set-admin", "root_admin"]) == 0
        assert _user("root_admin").is_admin is True

    def test_set_admin_requires_existing_user(self):
        with pytest.raises(SystemExit, match="not found"):
            main(["set-admin", "nobody_here"])

    def test_list_users_reports_state(self, capsys):
        assert main(["list-users"]) == 0
        captured = capsys.readouterr().out
        assert "root_admin" in captured
        assert "admin" in captured
        assert "verified" in captured

    def test_set_verified_flips_unverified_user(self):
        # Create a normal (unverified) admin via the flag-less path by
        # crafting the row directly, then force verification.
        db = SessionLocal()
        try:
            if not _user("plain_user"):
                from app.security import hash_password

                db.add(
                    User(
                        username="plain_user",
                        email="plain_user@test.com",
                        hashed_password=hash_password("whatever123"),
                        is_active=True,
                        is_admin=False,
                    )
                )
                db.commit()
            row = _user("plain_user")
        finally:
            db.close()
        assert row.email_verified_at is None

        assert main(["set-verified", "plain_user"]) == 0
        assert _user("plain_user").email_verified_at is not None

    def test_password_from_environment_variable(self, monkeypatch):
        monkeypatch.setenv("AURORA_CLI_PASSWORD", "env-pass-789")
        assert main(["create-admin", "env_admin"]) == 0
        user = _user("env_admin")
        assert user is not None
        assert verify_password("env-pass-789", user.hashed_password)

        # The env-var password actually works end to end through the API.
        with TestClient(app) as client:
            login = client.post(
                "/auth/token", json={"username": "env_admin", "password": "env-pass-789"}
            )
            assert login.status_code == 200

    def test_cli_password_requires_something(self, monkeypatch):
        monkeypatch.delenv("AURORA_CLI_PASSWORD", raising=False)
        # cli.py binds getpass by name at import time, so patch the binding.
        monkeypatch.setattr("cli.getpass", lambda _: "")
        with pytest.raises(SystemExit):
            main(["create-admin", "nopw_user", "--password", ""])
