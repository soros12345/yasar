"""Awin credential readiness by reference (V1A-5 skeleton).

Credentials are resolved by *reference* — the environment variable NAME, never
its value. RevenueOS never stores, returns, or logs a credential; readiness is
a presence check against operator-provided configuration. Unknown values stay
UNKNOWN: nothing here invents an endpoint or a credential.
"""
import os
from dataclasses import dataclass

AWIN_BASE_URL_ENV = "AWIN_API_BASE_URL"
AWIN_TOKEN_ENV = "AWIN_API_TOKEN"

STATE_NOT_CONFIGURED = "NOT_CONFIGURED"
STATE_CONFIGURED_UNVERIFIED = "CONFIGURED_UNVERIFIED"
STATE_VERIFIED = "VERIFIED"


@dataclass(frozen=True)
class AwinConfig:
    """Readiness of the Awin publisher credential. Holds NO secret value."""

    base_url: str | None
    has_credential: bool
    base_url_env: str = AWIN_BASE_URL_ENV
    token_env: str = AWIN_TOKEN_ENV

    @property
    def configured(self) -> bool:
        return bool(self.base_url) and bool(self.has_credential)


def load_awin_config(env=None) -> AwinConfig:
    """Build readiness from the environment (or a mapping supplied for tests).

    Only presence is inspected; the token value is never read into the result.
    """
    env = os.environ if env is None else env
    raw_base = (env.get(AWIN_BASE_URL_ENV) or "").strip()
    return AwinConfig(
        base_url=raw_base or None,
        has_credential=bool(env.get(AWIN_TOKEN_ENV)),
    )
