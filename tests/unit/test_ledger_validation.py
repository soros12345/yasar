"""Ledger posting validation unit tests (pure, no database)."""

from decimal import Decimal

import pytest

from revenueos_ledger.validation import (
    AccountInfo,
    InactiveAccountError,
    InsufficientLinesError,
    LineInput,
    MissingIdempotencyKeyError,
    NonPositiveAmountError,
    UnknownAccountError,
    UnbalancedEntryError,
    entry_fingerprint,
    validate_posting,
)

pytestmark = pytest.mark.unit


def _accounts():
    return {
        "CASH": AccountInfo(id="a1", code="CASH", currency="USD", status="ACTIVE",
                            kind="ASSET", normal_balance="DEBIT"),
        "REV": AccountInfo(id="a2", code="REV", currency="USD", status="ACTIVE",
                           kind="REVENUE", normal_balance="CREDIT"),
        "OLD": AccountInfo(id="a3", code="OLD", currency="USD", status="CLOSED",
                           kind="ASSET", normal_balance="DEBIT"),
        "EURCASH": AccountInfo(id="a4", code="EURCASH", currency="EUR", status="ACTIVE",
                               kind="ASSET", normal_balance="DEBIT"),
    }


def _base(**overrides):
    kwargs = dict(
        tenant_id="t1",
        currency="USD",
        description="test posting",
        reference=None,
        source="manual",
        accounts_by_code=_accounts(),
        idempotency_key="key-1",
    )
    kwargs.update(overrides)
    return kwargs


def test_balanced_posting_accepted():
    lines = [LineInput("CASH", "DEBIT", "10.00"), LineInput("REV", "CREDIT", "10.00")]
    normalized, fingerprint = validate_posting(lines=lines, **_base())
    assert len(normalized) == 2
    assert len(fingerprint) == 64


def test_unbalanced_rejected():
    lines = [LineInput("CASH", "DEBIT", "10.00"), LineInput("REV", "CREDIT", "9.99")]
    with pytest.raises(UnbalancedEntryError) as exc:
        validate_posting(lines=lines, **_base())
    assert exc.value.debits == Decimal("10.00")
    assert exc.value.credits == Decimal("9.99")


def test_single_line_rejected():
    with pytest.raises(InsufficientLinesError):
        validate_posting(lines=[LineInput("CASH", "DEBIT", "1")], **_base())


def test_sub_minor_unit_amount_rejected_after_rounding():
    lines = [LineInput("CASH", "DEBIT", "0.001"), LineInput("REV", "CREDIT", "0.001")]
    with pytest.raises(NonPositiveAmountError):
        validate_posting(lines=lines, **_base())


def test_rounding_applies_to_both_sides():
    lines = [LineInput("CASH", "DEBIT", "10.005"), LineInput("REV", "CREDIT", "10.005")]
    normalized, _ = validate_posting(lines=lines, **_base())
    assert all(ln.money.amount == Decimal("10.01") for ln in normalized)


def test_unknown_account_rejected():
    lines = [LineInput("NOPE", "DEBIT", "1"), LineInput("REV", "CREDIT", "1")]
    with pytest.raises(UnknownAccountError):
        validate_posting(lines=lines, **_base())


def test_closed_account_rejected():
    lines = [LineInput("OLD", "DEBIT", "1"), LineInput("REV", "CREDIT", "1")]
    with pytest.raises(InactiveAccountError):
        validate_posting(lines=lines, **_base())


def test_account_currency_mismatch_rejected():
    lines = [LineInput("EURCASH", "DEBIT", "1"), LineInput("REV", "CREDIT", "1")]
    with pytest.raises(Exception):
        validate_posting(lines=lines, **_base())


def test_idempotency_key_required():
    lines = [LineInput("CASH", "DEBIT", "1"), LineInput("REV", "CREDIT", "1")]
    with pytest.raises(MissingIdempotencyKeyError):
        validate_posting(lines=lines, **_base(idempotency_key=None))


def test_fingerprint_deterministic_and_content_sensitive():
    lines = [LineInput("CASH", "DEBIT", "10.00"), LineInput("REV", "CREDIT", "10.00")]
    _, fp1 = validate_posting(lines=lines, **_base())
    _, fp2 = validate_posting(lines=lines, **_base())
    _, fp3 = validate_posting(lines=lines, **_base(description="other"))
    _, fp4 = validate_posting(
        lines=[LineInput("CASH", "DEBIT", "10.01"), LineInput("REV", "CREDIT", "10.01")],
        **_base()
    )
    assert fp1 == fp2
    assert fp1 != fp3
    assert fp1 != fp4


def test_one_sided_entry_rejected():
    lines = [LineInput("CASH", "DEBIT", "5"), LineInput("CASH", "DEBIT", "5")]
    with pytest.raises(UnbalancedEntryError):
        validate_posting(lines=lines, **_base())
