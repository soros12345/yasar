"""RevenueOS affiliate connectors (V1A-5 skeleton).

Awin publisher credentials are UNPROVISIONED, so the connector is fail-closed:
readiness is reported honestly and dispatch is refused until an operator both
provisions the credential and verifies the capability.
"""
from revenueos_affiliate.config import AwinConfig, load_awin_config
from revenueos_affiliate.connector import (
    AwinConnectorState,
    AwinPublisherConnector,
    ConnectorNotConfiguredError,
    ConnectorNotVerifiedError,
)

__all__ = [
    "AwinConfig",
    "load_awin_config",
    "AwinConnectorState",
    "AwinPublisherConnector",
    "ConnectorNotConfiguredError",
    "ConnectorNotVerifiedError",
]
