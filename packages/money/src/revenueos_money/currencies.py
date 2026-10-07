"""ISO 4217 currency exponent registry.

V1A-2 ships an explicitly registered subset of real ISO 4217 currencies and
their official minor-unit exponents. Unknown currencies are REJECTED — they
are never guessed. New currencies are added explicitly (register_currency),
following the official standard.
"""

from typing import Final


class UnknownCurrencyError(ValueError):
    """Currency not in the registered ISO 4217 subset."""


# code -> minor unit exponent (ISO 4217 official)
CURRENCY_EXPONENTS: Final[dict[str, int]] = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "TRY": 2,
    "CHF": 2,
    "CAD": 2,
    "AUD": 2,
    "NZD": 2,
    "CNY": 2,
    "HKD": 2,
    "SGD": 2,
    "INR": 2,
    "SEK": 2,
    "NOK": 2,
    "DKK": 2,
    "PLN": 2,
    "BRL": 2,
    "ZAR": 2,
    "MXN": 2,
    "SAR": 2,
    "AED": 2,
    "ILS": 2,
    "PHP": 2,
    "MYR": 2,
    "IDR": 2,
    "JPY": 0,
    "KRW": 0,
    "CLP": 0,
    "VND": 0,
    "KWD": 3,
    "BHD": 3,
    "TND": 3,
    "OMR": 3,
    "JOD": 3,
}


def register_currency(code: str, exponent: int) -> None:
    """Explicitly register a currency (audited change — never guessed)."""
    code = code.upper().strip()
    if len(code) != 3 or not code.isalpha():
        raise UnknownCurrencyError(f"invalid ISO 4217 code: {code!r}")
    if not (0 <= exponent <= 6):
        raise UnknownCurrencyError(f"invalid exponent: {exponent}")
    CURRENCY_EXPONENTS[code] = exponent


def exponent_for(currency: str) -> int:
    code = currency.upper().strip() if isinstance(currency, str) else ""
    exponent = CURRENCY_EXPONENTS.get(code)
    if exponent is None:
        raise UnknownCurrencyError(
            f"currency {code!r} is not registered — register it explicitly per ISO 4217"
        )
    return exponent
