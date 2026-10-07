"""RevenueOS money package (V1A-2).

Hard rules:
  * NO FLOATS — binary floats are rejected at every entry point.
  * Exact Decimal arithmetic only.
  * Amounts are always quantized to the currency's ISO 4217 minor units.
"""

from revenueos_money.currencies import (
    CURRENCY_EXPONENTS,
    UnknownCurrencyError,
    exponent_for,
    register_currency,
)
from revenueos_money.money import (
    CurrencyMismatchError,
    InvalidAmountError,
    Money,
    MoneyError,
    to_decimal,
)

__version__ = "0.1.0"
