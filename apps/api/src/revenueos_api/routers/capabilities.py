"""Provider capability registry surface (V1A-4).

Read is available to any authenticated principal with provider_capability:read.
Registration is TENANT_ADMIN-only (wildcard write policy). A capability is only
usable once it is explicitly VERIFIED and enabled — registering it is not enough.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select

from revenueos_capabilities.models import ProviderCapability
from revenueos_capabilities.service import register_capability
from revenueos_schemas.execution import CapabilityCreateRequest, CapabilityOut
from revenueos_shared.db import session_scope

from revenueos_api.deps import Principal, permission

logger = logging.getLogger("revenueos.api.capabilities")
router = APIRouter(prefix="/api/v1/capabilities", tags=["capabilities"])


def _out(c: ProviderCapability) -> CapabilityOut:
    return CapabilityOut(
        id=c.id,
        provider_id=c.provider_id,
        capability_id=c.capability_id,
        verification_state=c.verification_state,
        enabled=c.enabled,
        scope_json=c.scope_json,
        notes=c.notes,
    )


@router.get("", response_model=list[CapabilityOut])
def list_capabilities_route(
    principal: Principal = Depends(permission("provider_capability", "read")),
) -> list[CapabilityOut]:
    with session_scope() as db:
        rows = db.execute(
            select(ProviderCapability).order_by(ProviderCapability.capability_id)
        ).scalars()
        return [_out(c) for c in rows]


@router.post("", response_model=CapabilityOut, status_code=201)
def register_capability_route(
    payload: CapabilityCreateRequest,
    principal: Principal = Depends(permission("provider_capability", "write")),
) -> CapabilityOut:
    with session_scope() as db:
        row = register_capability(
            db,
            provider_id=payload.provider_id,
            capability_id=payload.capability_id,
            verification_state=payload.verification_state,
            enabled=payload.enabled,
            scope=payload.scope,
            notes=payload.notes,
        )
        return _out(row)
