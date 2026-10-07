"""Provider usage/cost event endpoints (V1A-2 ingestion contract).

Raw observations only — these endpoints never derive conversions,
commissions, or any financial truth. Ledger linkage requires an actually
posted balanced journal entry (journal_entry_id)."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from revenueos_ledger.events import (
    EventError,
    format_quantity,
    ingest_cost_event,
    ingest_usage_event,
    list_cost_events,
    list_usage_events,
)
from revenueos_ledger.validation import PostingError
from revenueos_money import Money, MoneyError, UnknownCurrencyError
from revenueos_schemas import ledger as ls
from revenueos_shared.db import session_scope

from revenueos_api.deps import Principal, permission

logger = logging.getLogger("revenueos.api.provider_events")
router = APIRouter(prefix="/api/v1/provider-events", tags=["provider-events"])


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/usage", response_model=ls.UsageEventOut, status_code=201)
def ingest_usage_route(
    payload: ls.UsageEventCreateRequest,
    principal: Principal = Depends(permission("provider_event", "write")),
) -> ls.UsageEventOut:
    with session_scope() as db:
        try:
            event, _created = ingest_usage_event(
                db,
                tenant_id=principal.tenant_id,
                provider_id=payload.provider_id,
                occurred_at=_utc(payload.occurred_at),
                quantity=payload.quantity,
                unit=payload.unit,
                idempotency_key=payload.idempotency_key,
                capability_id=payload.capability_id,
                metadata=payload.metadata,
            )
        except (EventError, PostingError, MoneyError) as exc:
            raise _bad_request(exc)
        return ls.UsageEventOut(
            id=event.id,
            provider_id=event.provider_id,
            capability_id=event.capability_id,
            occurred_at=event.occurred_at,
            quantity=format_quantity(event.quantity),
            unit=event.unit,
            idempotency_key=event.idempotency_key,
            created_at=event.created_at,
        )


@router.post("/cost", response_model=ls.CostEventOut, status_code=201)
def ingest_cost_route(
    payload: ls.CostEventCreateRequest,
    principal: Principal = Depends(permission("provider_event", "write")),
) -> ls.CostEventOut:
    with session_scope() as db:
        try:
            event, _created = ingest_cost_event(
                db,
                tenant_id=principal.tenant_id,
                provider_id=payload.provider_id,
                occurred_at=_utc(payload.occurred_at),
                amount=payload.amount,
                currency=payload.currency,
                cost_type=payload.cost_type,
                usage_event_id=payload.usage_event_id,
                journal_entry_id=payload.journal_entry_id,
                idempotency_key=payload.idempotency_key,
            )
        except (EventError, PostingError, UnknownCurrencyError, MoneyError) as exc:
            raise _bad_request(exc)
        return ls.CostEventOut(
            id=event.id,
            provider_id=event.provider_id,
            occurred_at=event.occurred_at,
            amount=str(Money(event.amount, event.currency).amount),
            currency=event.currency,
            cost_type=event.cost_type,
            usage_event_id=event.usage_event_id,
            journal_entry_id=event.journal_entry_id,
            idempotency_key=event.idempotency_key,
            created_at=event.created_at,
        )


@router.get("/usage", response_model=list[ls.UsageEventOut])
def list_usage_route(
    limit: int = 50,
    offset: int = 0,
    principal: Principal = Depends(permission("provider_event", "read")),
) -> list[ls.UsageEventOut]:
    with session_scope() as db:
        return [
            ls.UsageEventOut(
                id=e.id,
                provider_id=e.provider_id,
                capability_id=e.capability_id,
                occurred_at=e.occurred_at,
                quantity=str(e.quantity),
                unit=e.unit,
                idempotency_key=e.idempotency_key,
                created_at=e.created_at,
            )
            for e in list_usage_events(db, principal.tenant_id, limit=limit, offset=offset)
        ]


@router.get("/cost", response_model=list[ls.CostEventOut])
def list_cost_route(
    limit: int = 50,
    offset: int = 0,
    principal: Principal = Depends(permission("provider_event", "read")),
) -> list[ls.CostEventOut]:
    with session_scope() as db:
        return [
            ls.CostEventOut(
                id=e.id,
                provider_id=e.provider_id,
                occurred_at=e.occurred_at,
                amount=str(e.amount),
                currency=e.currency,
                cost_type=e.cost_type,
                usage_event_id=e.usage_event_id,
                journal_entry_id=e.journal_entry_id,
                idempotency_key=e.idempotency_key,
                created_at=e.created_at,
            )
            for e in list_cost_events(db, principal.tenant_id, limit=limit, offset=offset)
        ]
