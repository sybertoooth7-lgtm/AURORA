"""AURORA operator CLI.

Granting admin (and forcing verification) are deliberately NOT HTTP
endpoints: self-service admin escalation would defeat the purpose of the
role, so those powers live behind the deployment itself. Use this CLI on
the machine that can reach the database the API uses.

Run:

    python cli.py create-admin <username> --password <pw>     # first operator
    python cli.py set-admin <username> --password <pw>        # promote + rotate pw
    python cli.py revoke-admin <username>
    python cli.py list-users
    python cli.py set-verified <username>                     # mark email verified

The password can be supplied with --password, or via the AURORA_CLI_PASSWORD
environment variable (preferred -- it stays out of shell history). Reading
functions are pure; write functions open their own SessionLocal, so the whole
thing is unit-testable against the in-process demo database.
"""

import argparse
import os
import sys
from datetime import UTC, datetime
from getpass import getpass

from sqlalchemy.orm import Session

from app.database import SessionLocal, demo_mode, init_demo_schema
from app.logging_conf import get_logger
from app.models.user import User
from app.security import hash_password

logger = get_logger(__name__)


def _session() -> Session:
    # Demo mode's database is created by the app lifespan / conftest; running
    # the CLI against the same in-process engine needs the schema ensured too.
    if demo_mode():
        init_demo_schema()
    return SessionLocal()


def _find_user(db: Session, username: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise SystemExit(f"User '{username}' not found.")
    return user


def _resolve_password(arg_password: str | None) -> str:
    env_password = os.environ.get("AURORA_CLI_PASSWORD")
    password = arg_password or env_password
    if not password:
        password = getpass("Password: ")
    if not password:
        raise SystemExit("A password is required (--password, AURORA_CLI_PASSWORD, or prompt).")
    return password


def register_parsers(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-admin", help="Create a user and grant admin (first operator).")
    create.add_argument("username")
    create.add_argument("--password", default=None)
    create.set_defaults(func=cmd_create_admin)

    promote = sub.add_parser("set-admin", help="Grant admin to an existing user.")
    promote.add_argument("username")
    promote.add_argument("--password", default=None, help="Optionally rotate the account password too.")
    promote.set_defaults(func=cmd_set_admin)

    revoke = sub.add_parser("revoke-admin", help="Remove admin from a user.")
    revoke.add_argument("username")
    revoke.set_defaults(func=cmd_revoke_admin)

    list_users = sub.add_parser("list-users", help="List accounts with their admin/verification state.")
    list_users.set_defaults(func=cmd_list_users)

    verify = sub.add_parser("set-verified", help="Mark a user's email as verified (operator override).")
    verify.add_argument("username")
    verify.set_defaults(func=cmd_set_verified)


def cmd_create_admin(args: argparse.Namespace) -> int:
    password = _resolve_password(args.password)
    with _session() as db:
        existing = db.query(User).filter(User.username == args.username).first()
        if existing:
            raise SystemExit(f"User '{args.username}' already exists -- use set-admin instead.")
        now = datetime.now(UTC)
        from app.config import get_settings

        email = f"{args.username}@{get_settings().CLI_ADMIN_EMAIL_DOMAIN}"
        user = User(
            username=args.username,
            email=email,
            hashed_password=hash_password(password),
            full_name=args.username,
            is_active=True,
            is_admin=True,
            email_verified_at=now,
            onboarding_completed_at=now,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("created admin", extra_keys={"username": args.username, "user_id": user.id})
        print(f"Created admin '{args.username}' (id={user.id}, email={email}).")
    return 0


def cmd_set_admin(args: argparse.Namespace) -> int:
    password = _resolve_password(args.password) if args.password is not None else None
    with _session() as db:
        user = _find_user(db, args.username)
        if not user.is_admin:
            user.is_admin = True
        if password is not None:
            user.hashed_password = hash_password(password)
            user.token_version += 1  # invalidate every outstanding session
        db.commit()
    print(f"'{args.username}' is now an admin.")
    return 0


def cmd_revoke_admin(args: argparse.Namespace) -> int:
    with _session() as db:
        user = _find_user(db, args.username)
        user.is_admin = False
        db.commit()
    print(f"'{args.username}' is no longer an admin.")
    return 0


def cmd_list_users(args: argparse.Namespace) -> int:
    with _session() as db:
        rows = db.query(User).order_by(User.created_at).all()
        if not rows:
            print("No users.")
            return 0
        for u in rows:
            verified = "verified" if u.email_verified_at is not None else "unverified"
            admin = "admin" if u.is_admin else "user"
            active = "active" if u.is_active else "disabled"
            print(f"#{u.id}  {u.username:<20} {u.email:<32} {verified:<10} {admin:<6} {active}")
    return 0


def cmd_set_verified(args: argparse.Namespace) -> int:
    now = datetime.now(UTC)
    with _session() as db:
        user = _find_user(db, args.username)
        if user.email_verified_at is None:
            user.email_verified_at = now
            db.commit()
    print(f"'{args.username}' is now email-verified.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python cli.py",
        description="AURORA operator CLI (admin grants + verification overrides).",
    )
    register_parsers(parser)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
