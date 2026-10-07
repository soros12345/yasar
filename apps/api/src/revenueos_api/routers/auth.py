"""Authentication endpoints (V1A-1).

Login is the only unauthenticated business endpoint. Responses never echo
passwords or tokens other than the one-time access token; logs contain IDs
only — never credentials."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from revenueos_authorization.enforcer import permissions_matrix
from revenueos_identity.models import TENANT_ACTIVE, USER_ACTIVE, Tenant, User, UserSession
from revenueos_identity.passwords import verify_password
from revenueos_identity.services import get_user_by_email
from revenueos_identity.sessions import create_session, revoke_session
from revenueos_schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MeResponse,
    SessionOut,
    TenantOut,
    UserOut,
)
from revenueos_shared.config import get_settings
from revenueos_shared.db import session_scope

from revenueos_api.deps import Principal, get_current_principal
from fastapi import Depends

logger = logging.getLogger("revenueos.api.auth")
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

INVALID_CREDENTIALS = HTTPException(status_code=401, detail="invalid_credentials")


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        status=user.status,
        tenant_id=user.tenant_id,
    )


def _tenant_out(tenant: Tenant) -> TenantOut:
    return TenantOut(id=tenant.id, slug=tenant.slug, name=tenant.name, status=tenant.status)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    settings = get_settings()
    password = payload.password.get_secret_value()
    slug = payload.tenant_slug.strip().lower()

    with session_scope() as db:
        tenant = db.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none()
        user = get_user_by_email(db, tenant.id, payload.email) if tenant else None

        if user is not None:
            credentials_ok = verify_password(password, user.password_hash)
        else:
            # constant work for unknown users (anti-enumeration), result ignored
            from revenueos_api.deps import _dummy_hash

            verify_password(password, _dummy_hash())
            credentials_ok = False

        if tenant is None or user is None or not credentials_ok:
            logger.warning(
                "login rejected",
                extra={"event": "login_rejected", "component": "auth", "detail": slug},
            )
            raise INVALID_CREDENTIALS

        # Security status gates after credential verification
        if user.status != USER_ACTIVE:
            raise HTTPException(status_code=403, detail="account_disabled")
        if tenant.status != TENANT_ACTIVE:
            raise HTTPException(status_code=403, detail="tenant_suspended")

        token, session_row = create_session(db, user, settings.session_ttl_hours)
        expires_at = session_row.expires_at
        user_out, tenant_out = _user_out(user), _tenant_out(tenant)

    logger.info(
        "login succeeded",
        extra={
            "event": "login_succeeded",
            "component": "auth",
            "detail": f"user_id={user_out.id} tenant_id={tenant_out.id}",
        },
    )
    return LoginResponse(access_token=token, expires_at=expires_at, user=user_out, tenant=tenant_out)


@router.post("/logout", response_model=LogoutResponse)
def logout(principal: Principal = Depends(get_current_principal)) -> LogoutResponse:
    with session_scope() as db:
        row = db.get(UserSession, principal.session_id)
        if row is not None:
            revoke_session(db, row)
    logger.info(
        "logout succeeded",
        extra={"event": "logout", "component": "auth", "detail": principal.user_id},
    )
    return LogoutResponse()


@router.get("/me", response_model=MeResponse)
def me(principal: Principal = Depends(get_current_principal)) -> MeResponse:
    with session_scope() as db:
        user = db.get(User, principal.user_id)
        tenant = db.get(Tenant, principal.tenant_id)
        assert user is not None and tenant is not None
        permissions = permissions_matrix(principal.user_id, principal.tenant_id)
        return MeResponse(
            user=_user_out(user),
            tenant=_tenant_out(tenant),
            session_id=principal.session_id,
            session_expires_at=principal.session_expires_at,
            permissions=permissions,
        )
