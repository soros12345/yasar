"""Request authentication + permission dependencies (authority order:
Security > Compliance > Data Rights > User Locks > Rules > Approval >
Business Policies > Agents — implemented here as: authenticate → account/
tenant security status → Casbin business authorization)."""

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from fastapi import Depends, Header, HTTPException

from revenueos_identity.models import TENANT_ACTIVE, USER_ACTIVE, Tenant, User
from revenueos_identity.sessions import get_active_session
from revenueos_shared.db import session_scope

UNAUTHORIZED = HTTPException(status_code=401, detail="invalid_token")
NOT_AUTHENTICATED = HTTPException(status_code=401, detail="not_authenticated")


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    tenant_slug: str
    email: str
    role: str
    display_name: str
    session_id: str
    session_expires_at: datetime


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise NOT_AUTHENTICATED
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise NOT_AUTHENTICATED
    return token.strip()


@lru_cache
def _dummy_hash() -> str:
    """Constant-work comparison target for unknown-user logins."""
    from revenueos_identity.passwords import hash_password

    return hash_password("invalid-credential-placeholder-value")


def get_current_principal(authorization: str | None = Header(None)) -> Principal:
    token = _bearer_token(authorization)
    with session_scope() as db:
        session_row = get_active_session(db, token)
        if session_row is None:
            raise UNAUTHORIZED
        user = db.get(User, session_row.user_id)
        tenant = db.get(Tenant, session_row.tenant_id)
        if user is None or tenant is None:
            raise UNAUTHORIZED
        # Security status gates run BEFORE business authorization
        if user.status != USER_ACTIVE:
            raise HTTPException(status_code=403, detail="account_disabled")
        if tenant.status != TENANT_ACTIVE:
            raise HTTPException(status_code=403, detail="tenant_suspended")
        return Principal(
            user_id=user.id,
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            email=user.email,
            role=user.role,
            display_name=user.display_name,
            session_id=session_row.id,
            session_expires_at=session_row.expires_at,
        )


def permission(obj: str, act: str):
    """Factory producing a dependency that enforces a Casbin decision for
    the principal's domain (tenant). Deny by default."""

    def dependency(
        principal: Principal = Depends(get_current_principal),
    ) -> Principal:
        from revenueos_authorization.enforcer import can

        if not can(principal.user_id, principal.tenant_id, obj, act):
            raise HTTPException(status_code=403, detail="forbidden")
        return principal

    dependency.__name__ = f"permission_{obj}_{act}"
    return dependency
