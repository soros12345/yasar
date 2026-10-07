"""Pure posting validation (no database, no I/O).

Rules enforced here (unit-tested in isolation):
  * at least two lines
  * every line: positive amount AFTER quantization to the currency's
    minor units (catches sub-minor-unit inputs like 0.001 USD)
  * single currency per entry, matching every account's currency
  * accounts exist in the tenant, are ACTIVE, codes unique per tenant
  * side ∈ {DEBIT, CREDIT}
  * Σ debits == Σ credits exactly (Decimal arithmetic, never float)
"""

from dataclasses import dataclass
from decimal import Decimal

from revenueos_money import Money, to_decimal  # type: ignore[attr-defined]


class PostingError(ValueError):
    """Base class for ledger posting rejections."""


class InsufficientLinesError(PostingError):
    pass


class InvalidLineError(PostingError):
    pass


class NonPositiveAmountError(PostingError):
    pass


class UnknownAccountError(PostingError):
    pass


class InactiveAccountError(PostingError):
    pass


class AccountCurrencyMismatchError(PostingError):
    pass


class EntryCurrencyMismatchError(PostingError):
    pass


class UnbalancedEntryError(PostingError):
    def __init__(self, debits: Decimal, credits: Decimal):
        self.debits = debits
        self.credits = credits
        super().__init__(
            f"entry does not balance: debits={debits} credits={credits} "
            f"difference={debits - credits}"
        )


class MissingIdempotencyKeyError(PostingError):
    pass


@dataclass(frozen=True, slots=True)
class LineInput:
    account_code: str
    side: str
    amount: Decimal | str | int
    description: str | None = None


@dataclass(frozen=True, slots=True)
class AccountInfo:
    id: str
    code: str
    currency: str
    status: str
    kind: str
    normal_balance: str


@dataclass(frozen=True, slots=True)
class NormalizedLine:
    account: AccountInfo
    side: str
    money: Money
    description: str | None


def entry_fingerprint(
    *, currency: str, description: str, reference: str | None, source: str, lines: list[NormalizedLine]
) -> str:
    """Canonical content hash for idempotency conflict detection."""
    import hashlib

    parts = [
        currency,
        description,
        reference or "",
        source,
        *(f"{ln.account.code}:{ln.side}:{ln.money.amount}" for ln in lines),
    ]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def validate_posting(
    *,
    tenant_id: str,
    currency: str,
    description: str,
    reference: str | None,
    source: str,
    lines: list[LineInput],
    accounts_by_code: dict[str, AccountInfo],
    idempotency_key: str | None,
) -> tuple[list[NormalizedLine], str]:
    """Validate a posting and return (normalized_lines, fingerprint).

    `tenant_id` is part of the contract even though accounts arrive
    pre-scoped: callers must only pass accounts loaded for this tenant.
    """
    if not idempotency_key:
        raise MissingIdempotencyKeyError("idempotency_key is required for every posting")
    if not description or not description.strip():
        raise InvalidLineError("description is required")
    if len(lines) < 2:
        raise InsufficientLinesError("a journal entry requires at least two lines")

    currency = (currency or "").upper().strip()
    if len(currency) != 3:
        raise EntryCurrencyMismatchError(f"invalid entry currency: {currency!r}")

    normalized: list[NormalizedLine] = []
    seen_side_counts = {"DEBIT": 0, "CREDIT": 0}

    for index, line in enumerate(lines, start=1):
        side = (line.side or "").upper().strip()
        if side not in ("DEBIT", "CREDIT"):
            raise InvalidLineError(f"line {index}: side must be DEBIT or CREDIT")

        raw = to_decimal(line.amount, field=f"line {index} amount")
        money = Money(raw, currency)  # quantized to currency minor units
        if money.amount <= 0:
            raise NonPositiveAmountError(
                f"line {index}: amount {raw} {currency} is non-positive after "
                f"rounding to {money.exponent} decimal place(s)"
            )

        account = accounts_by_code.get(line.account_code)
        if account is None:
            raise UnknownAccountError(f"line {index}: account {line.account_code!r} not found in tenant")
        if account.status != "ACTIVE":
            raise InactiveAccountError(f"line {index}: account {account.code} is {account.status}")
        if account.currency != currency:
            raise AccountCurrencyMismatchError(
                f"line {index}: account {account.code} is {account.currency}, entry is {currency}"
            )

        seen_side_counts[side] += 1
        normalized.append(
            NormalizedLine(
                account=account, side=side, money=money, description=line.description
            )
        )

    if seen_side_counts["DEBIT"] == 0 or seen_side_counts["CREDIT"] == 0:
        raise UnbalancedEntryError(
            sum((ln.money.amount for ln in normalized if ln.side == "DEBIT"), Decimal(0)),
            sum((ln.money.amount for ln in normalized if ln.side == "CREDIT"), Decimal(0)),
        )

    debits = sum(
        (ln.money.amount for ln in normalized if ln.side == "DEBIT"), Decimal(0)
    )
    credits = sum(
        (ln.money.amount for ln in normalized if ln.side == "CREDIT"), Decimal(0)
    )
    if debits != credits:
        raise UnbalancedEntryError(debits, credits)

    fingerprint = entry_fingerprint(
        currency=currency,
        description=description.strip(),
        reference=reference,
        source=source,
        lines=normalized,
    )
    return normalized, fingerprint
