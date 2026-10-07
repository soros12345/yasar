"""Financial core contract schemas (V1A-2).

Amounts/quantities are STRICT decimal strings — JSON numbers are rejected
at the contract boundary (422) so no float can ever reach the ledger.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

AccountKind = Literal["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"]
Side = Literal["DEBIT", "CREDIT"]

DecimalString = Annotated[
    str,
    Field(strict=True, min_length=1, max_length=40, pattern=r"^-?\d{1,18}(\.\d{1,8})?$"),
]
AccountCode = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$")]
CurrencyCode = Annotated[str, Field(strict=True, min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")]


class AccountCreateRequest(BaseModel):
    code: AccountCode
    name: str = Field(min_length=1, max_length=128)
    kind: AccountKind
    currency: CurrencyCode


class AccountOut(BaseModel):
    id: str
    code: str
    name: str
    kind: str
    normal_balance: str
    currency: str
    status: str
    created_at: datetime


class EntryLineCreate(BaseModel):
    account_code: AccountCode
    side: Side
    amount: DecimalString
    description: str | None = Field(default=None, max_length=512)


class EntryCreateRequest(BaseModel):
    currency: CurrencyCode
    description: str = Field(min_length=1, max_length=512)
    reference: str | None = Field(default=None, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    source: str = Field(default="manual", min_length=1, max_length=64)
    lines: list[EntryLineCreate] = Field(min_length=2, max_length=200)


class EntryLineOut(BaseModel):
    line_number: int
    account_id: str
    account_code: str
    side: str
    amount: str
    currency: str
    description: str | None = None


class EntryOut(BaseModel):
    id: str
    currency: str
    description: str
    reference: str | None
    idempotency_key: str
    source: str
    posted_at: datetime
    total_debit: str
    total_credit: str
    balanced: bool
    lines: list[EntryLineOut]


class AccountBalanceOut(BaseModel):
    id: str
    code: str
    name: str
    kind: str
    normal_balance: str
    currency: str
    status: str
    debit_total: str
    credit_total: str
    balance: str


class UsageEventCreateRequest(BaseModel):
    provider_id: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$")]
    occurred_at: datetime
    quantity: DecimalString
    unit: str = Field(min_length=1, max_length=32)
    capability_id: str | None = Field(default=None, max_length=128)
    idempotency_key: str | None = Field(default=None, max_length=128)
    metadata: dict | None = None


class UsageEventOut(BaseModel):
    id: str
    provider_id: str
    capability_id: str | None
    occurred_at: datetime
    quantity: str
    unit: str
    idempotency_key: str | None
    created_at: datetime


class CostEventCreateRequest(BaseModel):
    provider_id: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$")]
    occurred_at: datetime
    amount: DecimalString
    currency: CurrencyCode
    cost_type: str = Field(min_length=1, max_length=64)
    usage_event_id: str | None = Field(default=None, max_length=36)
    journal_entry_id: str | None = Field(default=None, max_length=36)
    idempotency_key: str | None = Field(default=None, max_length=128)


class CostEventOut(BaseModel):
    id: str
    provider_id: str
    occurred_at: datetime
    amount: str
    currency: str
    cost_type: str
    usage_event_id: str | None
    journal_entry_id: str | None
    idempotency_key: str | None
    created_at: datetime
