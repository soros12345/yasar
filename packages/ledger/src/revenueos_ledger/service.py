"""CanonicalFinancialLedger posting service — THE financial truth.

All writes go through post_entry(): validated, balanced, idempotent,
single-transaction, with a post-write balance re-check read back from the
database before commit. Nothing else may write journal tables directly.
"""

import logging
import uuid
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session as DbSession

from revenueos_ledger.models import (
    ACCOUNT_STATUS_ACTIVE,
    NORMAL_BALANCE_BY_KIND,
    LedgerAccount,
    LedgerJournalEntry,
    LedgerJournalLine,
)
from revenueos_ledger.validation import (
    AccountInfo,
    LineInput,
    NormalizedLine,
    PostingError,
    UnknownAccountError,
    validate_posting,
)
from revenueos_money import Money, UnknownCurrencyError, exponent_for

logger = logging.getLogger("revenueos.ledger")

DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200


class IdempotencyConflictError(PostingError):
    """Same idempotency key with different content — reject, never merge."""


class EntryNotFoundError(PostingError):
    pass


# --------------------------------------------------------------------------
# accounts
# --------------------------------------------------------------------------
def create_account(
    db: DbSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    kind: str,
    currency: str,
) -> LedgerAccount:
    kind = kind.upper().strip()
    if kind not in NORMAL_BALANCE_BY_KIND:
        raise PostingError(f"invalid account kind: {kind!r}")
    currency = currency.upper().strip()
    exponent_for(currency)  # raises UnknownCurrencyError if unregistered
    code = code.strip()
    if not code or len(code) > 64:
        raise PostingError("account code is required (max 64 chars)")
    exists = db.execute(
        select(LedgerAccount).where(
            LedgerAccount.tenant_id == tenant_id, LedgerAccount.code == code
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise PostingError(f"account code already exists in tenant: {code}")
    account = LedgerAccount(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        code=code,
        name=name.strip() or code,
        kind=kind,
        normal_balance=NORMAL_BALANCE_BY_KIND[kind],
        currency=currency,
        status=ACCOUNT_STATUS_ACTIVE,
    )
    db.add(account)
    db.flush()
    return account


def list_accounts(db: DbSession, tenant_id: str) -> list[LedgerAccount]:
    return list(
        db.execute(
            select(LedgerAccount)
            .where(LedgerAccount.tenant_id == tenant_id)
            .order_by(LedgerAccount.code)
        ).scalars()
    )


def close_account(db: DbSession, tenant_id: str, account_id: str) -> LedgerAccount:
    account = db.execute(
        select(LedgerAccount).where(
            LedgerAccount.id == account_id, LedgerAccount.tenant_id == tenant_id
        )
    ).scalar_one_or_none()
    if account is None:
        raise EntryNotFoundError("account not found")
    account.status = "CLOSED"
    return account


# --------------------------------------------------------------------------
# posting
# --------------------------------------------------------------------------
def post_entry(
    db: DbSession,
    *,
    tenant_id: str,
    currency: str,
    description: str,
    idempotency_key: str,
    lines: list[LineInput],
    reference: str | None = None,
    source: str = "manual",
) -> tuple[LedgerJournalEntry, bool]:
    """Post a balanced, idempotent journal entry.

    Returns (entry, created). Re-posting identical content with the same
    idempotency key returns the existing entry (created=False); different
    content with the same key raises IdempotencyConflictError (409).
    """
    if not idempotency_key or len(idempotency_key) > 128:
        raise PostingError("idempotency_key is required (max 128 chars)")

    existing = db.execute(
        select(LedgerJournalEntry).where(
            LedgerJournalEntry.tenant_id == tenant_id,
            LedgerJournalEntry.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()

    # accounts pre-scoped to THIS tenant (isolation at the data-access layer)
    accounts = {
        a.code: AccountInfo(
            id=a.id, code=a.code, currency=a.currency, status=a.status,
            kind=a.kind, normal_balance=a.normal_balance,
        )
        for a in list_accounts(db, tenant_id)
    }

    normalized, fingerprint = validate_posting(
        tenant_id=tenant_id,
        currency=currency,
        description=description,
        reference=reference,
        source=source,
        lines=lines,
        accounts_by_code=accounts,
        idempotency_key=idempotency_key,
    )

    if existing is not None:
        if existing.fingerprint != fingerprint:
            raise IdempotencyConflictError(
                "idempotency_key already used with different content"
            )
        logger.info(
            "idempotent posting reuse",
            extra={"event": "posting_reused", "component": "ledger",
                   "detail": f"entry_id={existing.id}"},
        )
        return existing, False

    entry = LedgerJournalEntry(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        currency=normalized[0].money.currency,
        description=description.strip(),
        reference=reference,
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
        source=source,
    )
    db.add(entry)
    db.flush()

    for number, line in enumerate(normalized, start=1):
        db.add(
            LedgerJournalLine(
                id=str(uuid.uuid4()),
                entry_id=entry.id,
                line_number=number,
                account_id=line.account.id,
                side=line.side,
                amount=line.money.amount,
                currency=line.money.currency,
                description=line.description,
            )
        )
    db.flush()

    # Post-write reconciliation: read the sums back from the database
    # inside the same transaction and re-verify the invariant.
    db_debits, db_credits = _entry_sums(db, entry.id)
    if db_debits != db_credits:
        raise PostingError(
            f"reconciliation failed inside transaction: {db_debits} != {db_credits}"
        )

    logger.info(
        "journal entry posted",
        extra={"event": "entry_posted", "component": "ledger",
               "detail": f"entry_id={entry.id} amount={db_debits} {entry.currency}"},
    )
    return entry, True


def _entry_sums(db: DbSession, entry_id: str) -> tuple[Decimal, Decimal]:
    row = db.execute(
        select(
            func.coalesce(
                func.sum(
                    case((LedgerJournalLine.side == "DEBIT", LedgerJournalLine.amount),
                         else_=Decimal(0))
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case((LedgerJournalLine.side == "CREDIT", LedgerJournalLine.amount),
                         else_=Decimal(0))
                ),
                0,
            ),
        ).where(LedgerJournalLine.entry_id == entry_id)
    ).one()
    return Decimal(row[0]), Decimal(row[1])


def entry_totals(entry: LedgerJournalEntry) -> tuple[Decimal, Decimal]:
    """Totals quantized to the entry currency's minor units (DB stores
    NUMERIC(20,6); output must respect ISO 4217 exponents)."""
    from revenueos_money import Money as _Money

    debits = sum(
        (Decimal(l.amount) for l in entry.lines if l.side == "DEBIT"), Decimal(0)
    )
    credits = sum(
        (Decimal(l.amount) for l in entry.lines if l.side == "CREDIT"), Decimal(0)
    )
    return (
        _Money(debits, entry.currency).amount,
        _Money(credits, entry.currency).amount,
    )


# --------------------------------------------------------------------------
# reads (tenant-scoped)
# --------------------------------------------------------------------------
def list_entries(
    db: DbSession, tenant_id: str, *, limit: int = DEFAULT_LIST_LIMIT, offset: int = 0
) -> list[LedgerJournalEntry]:
    limit = max(1, min(limit, MAX_LIST_LIMIT))
    offset = max(0, offset)
    return list(
        db.execute(
            select(LedgerJournalEntry)
            .where(LedgerJournalEntry.tenant_id == tenant_id)
            .order_by(LedgerJournalEntry.posted_at.desc(), LedgerJournalEntry.id)
            .limit(limit)
            .offset(offset)
        ).scalars()
    )


def get_entry(db: DbSession, tenant_id: str, entry_id: str) -> LedgerJournalEntry | None:
    """Tenant-scoped fetch: an entry from another tenant behaves as absent."""
    return db.execute(
        select(LedgerJournalEntry).where(
            LedgerJournalEntry.id == entry_id,
            LedgerJournalEntry.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()


def account_balances(
    db: DbSession, tenant_id: str
) -> list[tuple[LedgerAccount, Decimal, Decimal, Decimal]]:
    """Per-account (account, debit_total, credit_total, balance) for one tenant."""
    rows = db.execute(
        select(
            LedgerAccount,
            func.coalesce(
                func.sum(
                    case((LedgerJournalLine.side == "DEBIT", LedgerJournalLine.amount),
                         else_=Decimal(0))
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case((LedgerJournalLine.side == "CREDIT", LedgerJournalLine.amount),
                         else_=Decimal(0))
                ),
                0,
            ),
        )
        .select_from(LedgerAccount)
        .outerjoin(LedgerJournalLine, LedgerJournalLine.account_id == LedgerAccount.id)
        .where(LedgerAccount.tenant_id == tenant_id)
        .group_by(LedgerAccount.id)
        .order_by(LedgerAccount.code)
    ).all()
    return [
        (row[0], Decimal(row[1]), Decimal(row[2]), Decimal(row[1]) - Decimal(row[2]))
        for row in rows
    ]
