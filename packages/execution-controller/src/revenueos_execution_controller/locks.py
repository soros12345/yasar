"""Execution lock engine (V1A-4).

Serializes a tenant's execution of the same intent using a PostgreSQL
transaction-scoped advisory lock. On non-PostgreSQL engines (the SQLite unit
fixture) no durable lock is taken and the state is NOT_APPLICABLE rather than a
fabricated ALLOWED.
"""
import hashlib

from sqlalchemy import text

GUARD_ALLOWED = "ALLOWED"
GUARD_DENIED = "DENIED"
GUARD_NOT_APPLICABLE = "NOT_APPLICABLE"


def _advisory_key(tenant_id: str, resource: str) -> int:
    digest = hashlib.sha256(f"{tenant_id}:{resource}".encode()).digest()[:8]
    # signed 64-bit key for pg_try_advisory_xact_lock(bigint)
    return int.from_bytes(digest, "big", signed=True)


def acquire_execution_lock(db, tenant_id: str, resource: str) -> tuple[str, str]:
    """Return ``(state, reason)``. ALLOWED when the lock is held for this txn."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return GUARD_NOT_APPLICABLE, "advisory locks require PostgreSQL; no lock taken"
    key = _advisory_key(tenant_id, resource)
    acquired = bool(db.execute(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": key}).scalar())
    if acquired:
        return GUARD_ALLOWED, f"advisory lock acquired for {resource!r}"
    return GUARD_DENIED, f"advisory lock contended for {resource!r}"
