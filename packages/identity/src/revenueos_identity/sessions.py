"""Session lifecycle: opaque bearer tokens, stored only as SHA-256 hashes."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from revenueos_identity.models import User, UserSession

TOKEN_BYTES = 32  # 256-bit opaque token


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_session(db: DbSession, user: User, ttl_hours: int) -> tuple[str, UserSession]:
    """Create a session. Returns (plaintext_token, row); the plaintext is
    shown to the client exactly once and never stored or logged."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    row = UserSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        tenant_id=user.tenant_id,
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        expires_at=_utcnow() + timedelta(hours=ttl_hours),
    )
    db.add(row)
    db.flush()
    return token, row


def get_active_session(db: DbSession, token: str) -> UserSession | None:
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = db.execute(
        select(UserSession).where(UserSession.token_hash == token_hash)
    ).scalar_one_or_none()
    if row is None:
        return None
    if row.revoked_at is not None:
        return None
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= _utcnow():
        return None
    return row


def revoke_session(db: DbSession, row: UserSession) -> None:
    if row.revoked_at is None:
        row.revoked_at = _utcnow()
        db.flush()


def purge_expired_sessions(db: DbSession) -> int:
    from revenueos_identity.models import UserSession as S

    stale = db.execute(
        select(S).where(S.expires_at <= _utcnow())
    ).scalars().all()
    for row in stale:
        db.delete(row)
    return len(stale)
