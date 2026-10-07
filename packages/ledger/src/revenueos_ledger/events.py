"""Provider usage/cost event ingestion contract (V1A-2).

RevenueOS owns these event tables (constitution §28 — not OpenMeter).
Events are raw observations: they NEVER invent provider capabilities,
prices, or conversions. Linking a cost event into the ledger happens via
journal_entry_id only when an actual balanced entry was posted — no
automatic or fabricated financial truth.
"""

import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from revenueos_ledger.models import (
    LedgerJournalEntry,
    ProviderCostEvent,
    ProviderUsageEvent,
)
from revenueos_money import Money, to_decimal

QUANTITY_SCALE = Decimal("0.000001")


def format_quantity(value) -> str:
    """Render a stored quantity without DB scale padding (3.000000 -> 3)."""
    text = format(Decimal(value), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


class EventError(ValueError):
    pass


def _quantize_quantity(value, *, field: str = "quantity") -> Decimal:
    quantity = to_decimal(value, field=field)
    quantity = quantity.quantize(QUANTITY_SCALE, rounding=ROUND_HALF_UP)
    if quantity <= 0:
        raise EventError(f"{field} must be > 0 (got {value})")
    return quantity


def ingest_usage_event(
    db: DbSession,
    *,
    tenant_id: str,
    provider_id: str,
    occurred_at: datetime,
    quantity,
    unit: str,
    idempotency_key: str | None = None,
    capability_id: str | None = None,
    metadata: dict | None = None,
) -> tuple[ProviderUsageEvent, bool]:
    provider_id = (provider_id or "").strip().lower()
    if not provider_id or len(provider_id) > 64:
        raise EventError("provider_id is required (max 64 chars)")
    if not unit or len(unit) > 32:
        raise EventError("unit is required (max 32 chars)")
    qty = _quantize_quantity(quantity)

    if idempotency_key:
        existing = db.execute(
            select(ProviderUsageEvent).where(
                ProviderUsageEvent.tenant_id == tenant_id,
                ProviderUsageEvent.provider_id == provider_id,
                ProviderUsageEvent.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing, False

    event = ProviderUsageEvent(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        provider_id=provider_id,
        capability_id=capability_id,
        occurred_at=occurred_at,
        quantity=qty,
        unit=unit,
        idempotency_key=idempotency_key,
        metadata_json=metadata,
    )
    db.add(event)
    db.flush()
    return event, True


def ingest_cost_event(
    db: DbSession,
    *,
    tenant_id: str,
    provider_id: str,
    occurred_at: datetime,
    amount,
    currency: str,
    cost_type: str,
    usage_event_id: str | None = None,
    journal_entry_id: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[ProviderCostEvent, bool]:
    provider_id = (provider_id or "").strip().lower()
    if not provider_id or len(provider_id) > 64:
        raise EventError("provider_id is required (max 64 chars)")
    if not cost_type or len(cost_type) > 64:
        raise EventError("cost_type is required (max 64 chars)")

    money = Money(amount, currency)  # rejects floats, quantizes per ISO 4217
    if money.amount <= 0:
        raise EventError(
            f"amount must be > 0 after rounding to {money.exponent} place(s) (got {amount})"
        )

    if usage_event_id is not None:
        owns = db.execute(
            select(ProviderUsageEvent.id).where(
                ProviderUsageEvent.id == usage_event_id,
                ProviderUsageEvent.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()
        if owns is None:
            raise EventError("usage_event_id does not belong to this tenant")

    if journal_entry_id is not None:
        owns = db.execute(
            select(LedgerJournalEntry.id).where(
                LedgerJournalEntry.id == journal_entry_id,
                LedgerJournalEntry.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()
        if owns is None:
            raise EventError("journal_entry_id does not belong to this tenant")

    if idempotency_key:
        existing = db.execute(
            select(ProviderCostEvent).where(
                ProviderCostEvent.tenant_id == tenant_id,
                ProviderCostEvent.provider_id == provider_id,
                ProviderCostEvent.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            if Decimal(existing.amount) != money.amount or existing.currency != money.currency:
                raise EventError(
                    "idempotency_key already used with different cost content"
                )
            return existing, False

    event = ProviderCostEvent(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        provider_id=provider_id,
        occurred_at=occurred_at,
        amount=money.amount,
        currency=money.currency,
        cost_type=cost_type,
        usage_event_id=usage_event_id,
        journal_entry_id=journal_entry_id,
        idempotency_key=idempotency_key,
    )
    db.add(event)
    db.flush()
    return event, True


def list_usage_events(
    db: DbSession, tenant_id: str, *, limit: int = 50, offset: int = 0
) -> list[ProviderUsageEvent]:
    return list(
        db.execute(
            select(ProviderUsageEvent)
            .where(ProviderUsageEvent.tenant_id == tenant_id)
            .order_by(ProviderUsageEvent.occurred_at.desc(), ProviderUsageEvent.id)
            .limit(max(1, min(limit, 200)))
            .offset(max(0, offset))
        ).scalars()
    )


def list_cost_events(
    db: DbSession, tenant_id: str, *, limit: int = 50, offset: int = 0
) -> list[ProviderCostEvent]:
    return list(
        db.execute(
            select(ProviderCostEvent)
            .where(ProviderCostEvent.tenant_id == tenant_id)
            .order_by(ProviderCostEvent.occurred_at.desc(), ProviderCostEvent.id)
            .limit(max(1, min(limit, 200)))
            .offset(max(0, offset))
        ).scalars()
    )
