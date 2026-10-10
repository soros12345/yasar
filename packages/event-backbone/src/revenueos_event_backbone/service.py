"""Event backbone service: append-only event log + outbox.

The event log is immutable by convention and by DB trigger (V1A-3 migration).
Outbox events are durable dispatch intentions; they are flushed by the
ExecutionController into Valkey/PostgreSQL and marked dispatched atomically.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from revenueos_event_backbone.models import ExecutionEvent, OutboxEvent


def append_event(
    db: DbSession,
    *,
    tenant_id: str,
    correlation_id: str,
    causation_id: str | None,
    event_type: str,
    payload: dict | None = None,
) -> ExecutionEvent:
    """Append an immutable event. Caller supplies correlation_id (deterministic
    replay anchor). causation_id links to the parent event that caused this one."""
    if not tenant_id or not correlation_id or not event_type:
        raise ValueError("tenant_id, correlation_id and event_type are required")
    event = ExecutionEvent(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        event_type=event_type,
        payload_json=payload,
    )
    db.add(event)
    db.flush()
    return event


def list_events(
    db: DbSession,
    tenant_id: str,
    *,
    correlation_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ExecutionEvent]:
    q = (
        select(ExecutionEvent)
        .where(ExecutionEvent.tenant_id == tenant_id)
        .order_by(ExecutionEvent.occurred_at.desc(), ExecutionEvent.id)
    )
    if correlation_id:
        q = q.where(ExecutionEvent.correlation_id == correlation_id)
    if event_type:
        q = q.where(ExecutionEvent.event_type == event_type)
    q = q.limit(max(1, min(limit, 200))).offset(max(0, offset))
    return list(db.execute(q).scalars())


def enqueue_outbox(
    db: DbSession,
    *,
    tenant_id: str,
    correlation_id: str,
    destination: str,
    payload: dict | None = None,
) -> OutboxEvent:
    """Enqueue a deterministic outbox dispatch. Idempotent by correlation_id."""
    existing = db.execute(
        select(OutboxEvent).where(
            OutboxEvent.tenant_id == tenant_id,
            OutboxEvent.correlation_id == correlation_id,
            OutboxEvent.destination == destination,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    event = OutboxEvent(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        destination=destination,
        payload_json=payload,
    )
    db.add(event)
    db.flush()
    return event


def list_pending_outbox(
    db: DbSession,
    tenant_id: str,
    *,
    limit: int = 100,
) -> list[OutboxEvent]:
    return list(
        db.execute(
            select(OutboxEvent)
            .where(OutboxEvent.tenant_id == tenant_id, OutboxEvent.state == "pending")
            .order_by(OutboxEvent.created_at)
            .limit(max(1, min(limit, 500)))
        ).scalars()
    )


def mark_outbox_dispatched(db: DbSession, outbox_id: str, tenant_id: str) -> OutboxEvent:
    """Atomically mark an outbox event dispatched (tenant-scoped)."""
    row = db.execute(
        select(OutboxEvent).where(
            OutboxEvent.id == outbox_id, OutboxEvent.tenant_id == tenant_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("outbox event not found in tenant")
    if row.state != "pending":
        return row
    row.state = "dispatched"
    row.dispatched_at = datetime.now(timezone.utc)
    db.flush()
    return row
