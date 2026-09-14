"""API-key management endpoints (machine credentials).

``POST /auth/api-keys`` mints a new key (the raw secret is returned exactly
once); ``GET /auth/api-keys`` lists the account's keys (secrets are never
repeated); ``POST /auth/api-keys/{id}/revoke`` soft-deletes a key.

The same ``Authorization: Bearer <key>`` header used for JWTs also accepts
a raw API key -- ``app.security.get_current_user`` routes by prefix before
hitting the DB, so the extra lookup is only paid when the token *starts
with* ``API_KEY_PREFIX``.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api_keys import generate_api_key
from app.config import get_settings
from app.database import get_db
from app.exceptions import ConflictError, NotFoundError
from app.logging_conf import get_logger
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.api_keys import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyListEntry,
    ApiKeyListResponse,
)
from app.security import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


def _to_list_entry(row: ApiKey) -> ApiKeyListEntry:
    return ApiKeyListEntry(
        id=row.id,
        name=row.name,
        prefix=row.prefix,
        revoked=row.revoked_at is not None,
        expires_at=row.expires_at,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
    )


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=201)
def create_api_key(
    body: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mint a new long-lived API key.  The plaintext secret is returned
    only in this response -- copy it somewhere safe immediately."""
    settings = get_settings()
    active_count = (
        db.query(ApiKey)
        .filter(
            ApiKey.user_id == current_user.id,
            ApiKey.revoked_at.is_(None),
        )
        .count()
    )
    if active_count >= settings.MAX_API_KEYS_PER_USER:
        raise ConflictError(
            f"Maximum of {settings.MAX_API_KEYS_PER_USER} active API keys reached."
        )

    raw_key, prefix, key_hash = generate_api_key()
    expires_at = None
    if body.expires_days is not None:
        expires_at = datetime.now(UTC) + timedelta(days=body.expires_days)

    row = ApiKey(
        user_id=current_user.id,
        name=body.name,
        prefix=prefix,
        key_hash=key_hash,
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    logger.info(
        "API key created",
        extra_keys={
            "user_id": current_user.id,
            "key_id": row.id,
            "name": body.name,
            "has_expiry": expires_at is not None,
        },
    )

    return ApiKeyCreated(
        id=row.id,
        name=row.name,
        prefix=row.prefix,
        key=raw_key,
        expires_at=row.expires_at,
        created_at=row.created_at,
    )


@router.get("/api-keys", response_model=ApiKeyListResponse)
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List every key minted by the calling account (secrets are never
    repeated -- only the short prefix is shown)."""
    rows = (
        db.query(ApiKey)
        .filter(ApiKey.user_id == current_user.id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )
    return ApiKeyListResponse(
        keys=[_to_list_entry(r) for r in rows],
        total=len(rows),
    )


@router.post("/api-keys/{key_id}/revoke", response_model=ApiKeyListEntry)
def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete an API key. Idempotent -- revoking an already-revoked
    key is a harmless no-op."""
    row = (
        db.query(ApiKey)
        .filter(ApiKey.id == key_id, ApiKey.user_id == current_user.id)
        .first()
    )
    if not row:
        raise NotFoundError("API key not found")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        db.commit()
        db.refresh(row)
        logger.info(
            "API key revoked",
            extra_keys={"user_id": current_user.id, "key_id": row.id},
        )
    return _to_list_entry(row)
