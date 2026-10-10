"""Provider adapter registry surface (V1A-4).

Lists the adapters RevenueOS knows about and whether each is enabled. No route
dispatches a provider call: invocation happens only inside the execution
authority chain, gated by a VERIFIED capability.
"""
import logging

from fastapi import APIRouter, Depends

from revenueos_execution_controller.adapters import list_adapters
from revenueos_schemas.execution import AdapterOut

from revenueos_api.deps import Principal, permission

logger = logging.getLogger("revenueos.api.adapters")
router = APIRouter(prefix="/api/v1/adapters", tags=["adapters"])


@router.get("", response_model=list[AdapterOut])
def list_adapters_route(
    principal: Principal = Depends(permission("provider_adapter", "read")),
) -> list[AdapterOut]:
    return [
        AdapterOut(adapter_id=a.adapter_id, capability_id=a.capability_id, enabled=a.enabled)
        for a in list_adapters()
    ]
