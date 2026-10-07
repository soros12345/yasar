"""Ledger endpoints (V1A-2). All reads/writes are tenant-scoped and
Casbin-checked; posting happens exclusively through the
CanonicalFinancialLedger service."""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from revenueos_ledger.models import LedgerAccount
from revenueos_ledger.service import (
    IdempotencyConflictError,
    account_balances,
    create_account,
    entry_totals,
    get_entry,
    list_accounts,
    list_entries,
    post_entry,
)
from revenueos_ledger.validation import LineInput, PostingError
from revenueos_money import Money, MoneyError, UnknownCurrencyError
from revenueos_schemas import ledger as ls
from revenueos_shared.db import session_scope

from revenueos_api.deps import Principal, permission

logger = logging.getLogger("revenueos.api.ledger")
router = APIRouter(prefix="/api/v1/ledger", tags=["ledger"])


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _code_by_account_id(principal: Principal) -> dict[str, str]:
    with session_scope() as db:
        return {
            a.id: a.code
            for a in db.execute(
                select(LedgerAccount).where(LedgerAccount.tenant_id == principal.tenant_id)
            ).scalars()
        }


def _entry_out(entry, code_by_id: dict[str, str]) -> ls.EntryOut:
    debits, credits = entry_totals(entry)
    return ls.EntryOut(
        id=entry.id,
        currency=entry.currency,
        description=entry.description,
        reference=entry.reference,
        idempotency_key=entry.idempotency_key,
        source=entry.source,
        posted_at=entry.posted_at,
        total_debit=str(debits),
        total_credit=str(credits),
        balanced=debits == credits,
        lines=[
            ls.EntryLineOut(
                line_number=line.line_number,
                account_id=line.account_id,
                account_code=code_by_id.get(line.account_id, "UNKNOWN"),
                side=line.side,
                amount=str(Money(Decimal(line.amount), line.currency).amount),
                currency=line.currency,
                description=line.description,
            )
            for line in entry.lines
        ],
    )


@router.post("/accounts", response_model=ls.AccountOut, status_code=201)
def create_account_route(
    payload: ls.AccountCreateRequest,
    principal: Principal = Depends(permission("ledger_account", "write")),
) -> ls.AccountOut:
    with session_scope() as db:
        try:
            account = create_account(
                db,
                tenant_id=principal.tenant_id,
                code=payload.code,
                name=payload.name,
                kind=payload.kind,
                currency=payload.currency,
            )
        except (PostingError, UnknownCurrencyError, MoneyError) as exc:
            raise _bad_request(exc)
        return ls.AccountOut(
            id=account.id,
            code=account.code,
            name=account.name,
            kind=account.kind,
            normal_balance=account.normal_balance,
            currency=account.currency,
            status=account.status,
            created_at=account.created_at,
        )


@router.get("/accounts", response_model=list[ls.AccountOut])
def list_accounts_route(
    principal: Principal = Depends(permission("ledger_account", "read")),
) -> list[ls.AccountOut]:
    with session_scope() as db:
        return [
            ls.AccountOut(
                id=a.id,
                code=a.code,
                name=a.name,
                kind=a.kind,
                normal_balance=a.normal_balance,
                currency=a.currency,
                status=a.status,
                created_at=a.created_at,
            )
            for a in list_accounts(db, principal.tenant_id)
        ]


@router.post("/entries", response_model=ls.EntryOut, status_code=201)
def post_entry_route(
    payload: ls.EntryCreateRequest,
    principal: Principal = Depends(permission("journal_entry", "write")),
) -> ls.EntryOut:
    lines = [
        LineInput(
            account_code=line.account_code,
            side=line.side,
            amount=Decimal(line.amount),
            description=line.description,
        )
        for line in payload.lines
    ]
    with session_scope() as db:
        try:
            entry, _created = post_entry(
                db,
                tenant_id=principal.tenant_id,
                currency=payload.currency,
                description=payload.description,
                idempotency_key=payload.idempotency_key,
                lines=lines,
                reference=payload.reference,
                source=payload.source,
            )
            entry_id = entry.id
        except IdempotencyConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except (PostingError, UnknownCurrencyError, MoneyError) as exc:
            raise _bad_request(exc)
    code_by_id = _code_by_account_id(principal)
    with session_scope() as db:
        fresh = get_entry(db, principal.tenant_id, entry_id)
        assert fresh is not None
        return _entry_out(fresh, code_by_id)


@router.get("/entries", response_model=list[ls.EntryOut])
def list_entries_route(
    limit: int = 50,
    offset: int = 0,
    principal: Principal = Depends(permission("journal_entry", "read")),
) -> list[ls.EntryOut]:
    code_by_id = _code_by_account_id(principal)
    with session_scope() as db:
        return [
            _entry_out(e, code_by_id)
            for e in list_entries(db, principal.tenant_id, limit=limit, offset=offset)
        ]


@router.get("/entries/{entry_id}", response_model=ls.EntryOut)
def get_entry_route(
    entry_id: str,
    principal: Principal = Depends(permission("journal_entry", "read")),
) -> ls.EntryOut:
    code_by_id = _code_by_account_id(principal)
    with session_scope() as db:
        entry = get_entry(db, principal.tenant_id, entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="not_found")
        return _entry_out(entry, code_by_id)


@router.get("/balances", response_model=list[ls.AccountBalanceOut])
def balances_route(
    principal: Principal = Depends(permission("journal_entry", "read")),
) -> list[ls.AccountBalanceOut]:
    with session_scope() as db:
        rows = account_balances(db, principal.tenant_id)
        from decimal import Decimal as D

        def _q(value, currency: str) -> str:
            return str(Money(D(value), currency).amount)

        return [
            ls.AccountBalanceOut(
                id=account.id,
                code=account.code,
                name=account.name,
                kind=account.kind,
                normal_balance=account.normal_balance,
                currency=account.currency,
                status=account.status,
                debit_total=_q(debit_total, account.currency),
                credit_total=_q(credit_total, account.currency),
                balance=_q(balance, account.currency),
            )
            for account, debit_total, credit_total, balance in rows
        ]
