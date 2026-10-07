"""Exact money value object. Floats are forbidden — always."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from revenueos_money.currencies import exponent_for


class MoneyError(ValueError):
    pass


class InvalidAmountError(MoneyError):
    pass


class CurrencyMismatchError(MoneyError):
    pass


def to_decimal(value, *, field: str = "amount") -> Decimal:
    """Convert str/int/Decimal to Decimal. Floats are rejected outright —
    binary floats cannot represent monetary values exactly."""
    if isinstance(value, float):
        raise InvalidAmountError(
            f"{field}: floats are forbidden for monetary values — use a decimal string"
        )
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise InvalidAmountError(f"{field}: boolean is not a monetary value")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except (InvalidOperation, ValueError) as exc:
            raise InvalidAmountError(f"{field}: {value!r} is not a decimal string") from exc
    raise InvalidAmountError(f"{field}: unsupported type {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class Money:
    """Immutable exact amount bound to a currency, always quantized to the
    currency's ISO 4217 minor units (ROUND_HALF_UP)."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if isinstance(self.amount, float):
            raise InvalidAmountError("floats are forbidden for monetary values")
        currency = self.currency.upper().strip() if isinstance(self.currency, str) else ""
        exponent = exponent_for(currency)  # raises UnknownCurrencyError
        amount = to_decimal(self.amount)
        quantized = amount.quantize(Decimal(1).scaleb(-exponent), rounding=ROUND_HALF_UP)
        object.__setattr__(self, "amount", quantized)
        object.__setattr__(self, "currency", currency)

    @classmethod
    def from_value(cls, value, currency: str) -> "Money":
        return cls(to_decimal(value), currency)

    @property
    def exponent(self) -> int:
        return exponent_for(self.currency)

    def _check(self, other: "Money") -> None:
        if not isinstance(other, Money):
            raise CurrencyMismatchError("operand is not Money")
        if other.currency != self.currency:
            raise CurrencyMismatchError(
                f"currency mismatch: {self.currency} vs {other.currency}"
            )

    def __add__(self, other: "Money") -> "Money":
        self._check(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._check(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount, self.currency)

    def __lt__(self, other: "Money") -> bool:
        self._check(other)
        return self.amount < other.amount

    def __le__(self, other: "Money") -> bool:
        self._check(other)
        return self.amount <= other.amount

    def is_zero(self) -> bool:
        return self.amount == 0

    def to_minor_units(self) -> int:
        """Integer count of the currency's minor units (e.g. cents)."""
        scaled = self.amount.scaleb(self.exponent)
        if scaled != scaled.to_integral_value():
            raise InvalidAmountError(f"{self} is not a whole number of minor units")
        return int(scaled)

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
