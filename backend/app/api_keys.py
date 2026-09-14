"""API key generation, hashing, and lookup.

Keys look like ``aur_<token_urlsafe>``. Only the sha256 hash is persisted
(see app.models.api_key); the lookup path hashes an incoming key and
matches on the hash column -- never a plaintext compare.
"""

import hashlib
import secrets

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.api_key import ApiKey


def hash_api_key(raw_key: str) -> str:
    """Deterministic hash used for storage AND lookup."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Return ``(raw_key, prefix, key_hash)``.

    ``raw_key`` is the only copy of the secret and must be shown to the
    caller exactly once; ``key_hash`` is what gets persisted.
    """
    settings = get_settings()
    raw_key = settings.API_KEY_PREFIX + secrets.token_urlsafe(32)
    return raw_key, raw_key[:14], hash_api_key(raw_key)


def find_api_key(db: Session, raw_key: str) -> ApiKey | None:
    """Resolve a raw key (prefix already validated by the caller)."""
    if not raw_key:
        return None
    return (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == hash_api_key(raw_key))
        .first()
    )
