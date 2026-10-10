"""Awin publisher connector (V1A-5 skeleton) — fail-closed.

The real Awin publisher API contract is UNKNOWN and no credential has been
provisioned, so this connector deliberately assumes **no endpoint paths**. The
caller supplies the path; the connector only enforces the fail-closed ladder:

    disabled                  -> refuse (adapter not enabled)
    credential not configured -> refuse (NOT_CONFIGURED)
    capability not VERIFIED   -> refuse (CONFIGURED_UNVERIFIED)
    everything satisfied       -> dispatch through the caller's transport

Nothing here fabricates an endpoint, a credential, or a VERIFIED state.
"""
from dataclasses import dataclass

from revenueos_affiliate.config import (
    AwinConfig,
    STATE_CONFIGURED_UNVERIFIED,
    STATE_NOT_CONFIGURED,
    STATE_VERIFIED,
    load_awin_config,
)

AWIN_CAPABILITY_ID = "awin_publisher_redirect"


class ConnectorError(RuntimeError):
    """Base class for fail-closed connector refusals."""


class ConnectorNotConfiguredError(ConnectorError):
    """No Awin credential/base URL has been provisioned."""


class ConnectorNotVerifiedError(ConnectorError):
    """A capability is required and is not VERIFIED."""


@dataclass(frozen=True)
class AwinConnectorState:
    state: str
    reason: str


@dataclass(frozen=True)
class AwinPublisherConnector:
    """Readiness + dispatch for the Awin publisher API.

    ``ready`` is the single source of truth: it is VERIFIED only when the
    adapter is enabled, the credential is provisioned, and the capability is
    VERIFIED. Everything else is an explicit, auditable refusal.
    """

    adapter_enabled: bool = False
    capability_id: str = AWIN_CAPABILITY_ID

    def readiness(
        self, *, enabled: bool | None = None, capability_state: str = "UNVERIFIED",
        config: AwinConfig | None = None,
    ) -> AwinConnectorState:
        cfg = config if config is not None else load_awin_config()
        is_enabled = self.adapter_enabled if enabled is None else enabled
        if not is_enabled:
            return AwinConnectorState("DISABLED", "awin_publisher adapter is not enabled")
        if not cfg.configured:
            missing = cfg.base_url_env if not cfg.base_url else cfg.token_env
            return AwinConnectorState(
                STATE_NOT_CONFIGURED,
                f"Awin credential not provisioned ({missing} unset)",
            )
        if capability_state != STATE_VERIFIED:
            return AwinConnectorState(
                STATE_CONFIGURED_UNVERIFIED,
                f"capability {self.capability_id!r} is {capability_state}, not VERIFIED",
            )
        return AwinConnectorState(
            STATE_VERIFIED,
            "credential provisioned and capability VERIFIED",
        )

    def dispatch(
        self,
        transport,
        path: str,
        *,
        method: str = "GET",
        params: dict | None = None,
        capability_state: str = "UNVERIFIED",
        enabled: bool | None = None,
        config: AwinConfig | None = None,
    ) -> dict:
        """Fail-closed request. Refuses before touching the transport."""
        state = self.readiness(
            enabled=enabled, capability_state=capability_state, config=config
        )
        if state.state != STATE_VERIFIED:
            if state.state in (STATE_NOT_CONFIGURED, "DISABLED"):
                raise ConnectorNotConfiguredError(state.reason)
            raise ConnectorNotVerifiedError(state.reason)
        if not path or not path.startswith("/"):
            raise ConnectorError("an absolute path must be supplied by the caller")
        return transport.send(
            "awin_publisher", f"{method} {path}", {"params": params or {}}
        )
