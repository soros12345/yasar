"""Money package unit tests (V1A-2): no floats, exact decimals, ISO rounding."""

from decimal import Decimal

import pytest

from revenueos_money import (
    CurrencyMismatchError,
    InvalidAmountError,
    Money,
    UnknownCurrencyError,
    exponent_for,
    register_currency,
)

pytestmark = pytest.mark.unit


def test_floats_are_forbidden_everywhere():
    with pytest.raises(InvalidAmountError):
        Money.from_value(1.005, "USD")
    with pytest.raises(InvalidAmountError):
        Money(Decimal("1.00") if False else 0.10, "USD")  # float literal rejected


def test_decimal_string_exact():
    m = Money.from_value("10.005", "USD")
    assert m.amount == Decimal("10.01")  # ROUND_HALF_UP to 2dp
    assert str(m) == "10.01 USD"


def test_rounding_rules_per_currency():
    assert Money.from_value("100.6", "JPY").amount == Decimal("101")   # 0dp
    assert Money.from_value("1.2345678", "KWD").amount == Decimal("1.235")  # 3dp
    assert Money.from_value("99.999", "USD").amount == Decimal("100.00")
    assert Money.from_value("1", "USD").to_minor_units() == 100
    assert Money.from_value("5", "JPY").to_minor_units() == 5


def test_unknown_currency_rejected_not_guessed():
    with pytest.raises(UnknownCurrencyError):
        Money.from_value("1", "XYZ")
    with pytest.raises(UnknownCurrencyError):
        exponent_for("NOPE")


def test_explicit_registration_only():
    register_currency("XTS", 2)  # ISO 4217 test code, explicit registration
    assert Money.from_value("1.5", "xts").amount == Decimal("1.50")


def test_currency_mismatch_rejected():
    with pytest.raises(CurrencyMismatchError):
        Money.from_value("1", "USD") + Money.from_value("1", "EUR")


def test_exact_arithmetic():
    total = Money.from_value("0.10", "USD") + Money.from_value("0.20", "USD")
    assert total.amount == Decimal("0.30")
    diff = Money.from_value("1.00", "USD") - Money.from_value("0.99", "USD")
    assert diff.amount == Decimal("0.01")
    assert not diff.is_zero()


def test_invalid_strings_rejected():
    with pytest.raises(InvalidAmountError):
        Money.from_value("abc", "USD")
    with pytest.raises(InvalidAmountError):
        Money.from_value(True, "USD")
