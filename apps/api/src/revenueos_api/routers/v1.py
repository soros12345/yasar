"""Tenant-scoped resource endpoints (V1A-1).

Every list/query is constrained to the principal's tenant.
Cross-tenant single-resource reads are enforced through Casbin domain
checks: the requested tenant must hold a role binding for the principal,
otherwise the request is denied — no cross-tenant data can leak."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from revenueos_authorization.enforcer import bind_role, can, ensure_default_policies
from revenueos_identity.models import Tenant, User, UserSession
from revenueos_identity.services import IdentityError, create_user
from revenueos_schemas.auth import SessionOut, TenantOut, UserCreateRequest, UserOut
from revenueos_shared.db import session_scope

from revenueos_api.deps import Principal, permission

logger = logging.getLogger("revenueos.api.v1")
router = APIRouter(prefix="/api/v1", tags=["v1"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        status=user.status,
        tenant_id=user.tenant_id,
    )


@router.get("/tenant", response_model=TenantOut)
def read_own_tenant(principal: Principal = Depends(permission("tenant", "read"))) -> TenantOut:
    with session_scope() as db:
        tenant = db.get(Tenant, principal.tenant_id)
        assert tenant is not None
        return TenantOut(id=tenant.id, slug=tenant.slug, name=tenant.name, status=tenant.status)


@router.get("/tenants/{tenant_id}", response_model=TenantOut)
def read_tenant_by_id(
    tenant_id: str,
    principal: Principal = Depends(permission("tenant", "read")),
) -> TenantOut:
    # Casbin domain check: principal must hold a role binding IN the
    # requested tenant's domain. Cross-tenant requests are denied.
    if not can(principal.user_id, tenant_id, "tenant", "read"):
        logger.warning(
            "cross-tenant access denied",
            extra={
                "event": "cross_tenant_denied",
                "component": "v1",
                "detail": f"requested={tenant_id}",
            },
        )
        raise HTTPException(status_code=403, detail="forbidden")
    with session_scope() as db:
        tenant = db.get(Tenant, tenant_id)
        if tenant is None:
            raise HTTPException(status_code=404, detail="not_found")
        return TenantOut(id=tenant.id, slug=tenant.slug, name=tenant.name, status=tenant.status)


@router.get("/users", response_model=list[UserOut])
def list_users(principal: Principal = Depends(permission("user", "read"))) -> list[UserOut]:
    with session_scope() as db:
        rows = db.execute(
            select(User)
            .where(User.tenant_id == principal.tenant_id)
            .order_by(User.created_at)
        ).scalars()
        return [_user_out(u) for u in rows]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user_endpoint(
    payload: UserCreateRequest,
    principal: Principal = Depends(permission("user", "write")),
) -> UserOut:
    with session_scope() as db:
        try:
            user = create_user(
                db,
                tenant_id=principal.tenant_id,
                email=payload.email,
                display_name=payload.display_name,
                password=payload.password.get_secret_value(),
                role=payload.role,
            )
        except IdentityError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        new_user_id = user.id

    # Role bindings + default policies are idempotent (self-healing) and
    # persisted through the Casbin adapter.
    ensure_default_policies(principal.tenant_id)
    bind_role(new_user_id, payload.role, principal.tenant_id)

    logger.info(
        "user created",
        extra={
            "event": "user_created",
            "component": "v1",
            "detail": f"user_id={new_user_id} role={payload.role}",
        },
    )
    with session_scope() as db:
        created = db.get(User, new_user_id)
        assert created is not None
        return _user_out(created)


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(principal: Principal = Depends(permission("session", "read"))) -> list[SessionOut]:
    with session_scope() as db:
        rows = db.execute(
            select(UserSession)
            .where(UserSession.tenant_id == principal.tenant_id)
            .order_by(UserSession.created_at)
        ).scalars()
        return [
            SessionOut(
                id=s.id,
                user_id=s.user_id,
                created_at=s.created_at,
                expires_at=s.expires_at,
                revoked=s.revoked_at is not None,
            )
            for s in rows
        ]
