"""V1A-5 skeleton: fail-closed Awin publisher connector (no network, no secrets).

Covers: credential readiness resolved by reference only, the refusal ladder
DISABLED -> NOT_CONFIGURED -> CONFIGURED_UNVERIFIED -> VERIFIED, and the
guarantee that a refused dispatch never touches a transport.
"""
import pytest

from revenueos_affiliate import (
    AwinConfig,
    AwinPublisherConnector,
    ConnectorNotConfiguredError,
    ConnectorNotVerifiedError,
    load_awin_config,
)
from revenueos_affiliate.connector import ConnectorError
from revenueos_execution_controller.adapters import AdapterDeniedError, LocalTransport, get_adapter

pytestmark = pytest.mark.unit

SECRET = "super-secret-awin-token"


# --------------------------------------------------------------------------
# configuration by reference
# --------------------------------------------------------------------------
def test_empty_environment_is_not_configured():
    cfg = load_awin_config(env={})
    assert cfg.configured is False
    assert cfg.base_url is None
    assert cfg.has_credential is False


def test_configured_requires_both_base_url_and_credential():
    assert load_awin_config(env={"AWIN_API_BASE_URL": "https://api.example"}).configured is False
    assert load_awin_config(env={"AWIN_API_TOKEN": SECRET}).configured is False
    cfg = load_awin_config(
        env={"AWIN_API_BASE_URL": "https://api.example", "AWIN_API_TOKEN": SECRET}
    )
    assert cfg.configured is True
    assert cfg.base_url == "https://api.example"


def test_credential_value_never_survives_configuration():
    cfg = load_awin_config(
        env={"AWIN_API_BASE_URL": "https://api.example", "AWIN_API_TOKEN": SECRET}
    )
    # only presence is captured: the value must not be reachable from the config
    assert cfg.has_credential is True
    assert SECRET not in repr(cfg)
    assert SECRET not in str(cfg)
    assert not [v for v in vars(cfg).values() if isinstance(v, str) and v == SECRET]


def test_blank_base_url_is_treated_as_missing():
    cfg = load_awin_config(env={"AWIN_API_BASE_URL": "   ", "AWIN_API_TOKEN": SECRET})
    assert cfg.configured is False


# --------------------------------------------------------------------------
# readiness ladder
# --------------------------------------------------------------------------
def test_readiness_ladder_fails_closed():
    connector = AwinPublisherConnector(adapter_enabled=True)

    # 1. disabled wins over everything else
    disabled = AwinPublisherConnector(adapter_enabled=False).readiness(
        enabled=False, capability_state="VERIFIED",
        config=AwinConfig(base_url="https://api.example", has_credential=True),
    )
    assert disabled.state == "DISABLED"

    # 2. enabled but no credential
    unconfigured = connector.readiness(
        enabled=True, capability_state="VERIFIED", config=load_awin_config(env={})
    )
    assert unconfigured.state == "NOT_CONFIGURED"
    assert "AWIN_API_BASE_URL" in unconfigured.reason

    # 3. credential present but capability not VERIFIED
    unverified = connector.readiness(
        enabled=True, capability_state="UNVERIFIED",
        config=AwinConfig(base_url="https://api.example", has_credential=True),
    )
    assert unverified.state == "CONFIGURED_UNVERIFIED"

    # 4. everything satisfied
    ready = connector.readiness(
        enabled=True, capability_state="VERIFIED",
        config=AwinConfig(base_url="https://api.example", has_credential=True),
    )
    assert ready.state == "VERIFIED"


# --------------------------------------------------------------------------
# dispatch refuses before any transport work
# --------------------------------------------------------------------------
def test_dispatch_never_touches_transport_when_not_configured():
    transport = LocalTransport()
    connector = AwinPublisherConnector(adapter_enabled=True)
    with pytest.raises(ConnectorNotConfiguredError):
        connector.dispatch(transport, "/v1/publisher/redirect", capability_state="VERIFIED")
    assert transport.calls == []


def _configured() -> AwinConfig:
    return AwinConfig(base_url="https://api.example", has_credential=True)


def test_dispatch_never_touches_transport_when_capability_unverified():
    transport = LocalTransport()
    connector = AwinPublisherConnector(adapter_enabled=True)
    with pytest.raises(ConnectorNotVerifiedError):
        connector.dispatch(
            transport, "/v1/publisher/redirect", config=_configured()
        )
    assert transport.calls == []


def test_dispatch_requires_a_caller_supplied_absolute_path():
    transport = LocalTransport()
    connector = AwinPublisherConnector(adapter_enabled=True)
    with pytest.raises(ConnectorError, match="path"):
        connector.dispatch(
            transport, "v1/publisher/redirect",
            capability_state="VERIFIED", config=_configured(),
        )
    assert transport.calls == []


def test_dispatch_succeeds_only_when_everything_is_satisfied():
    transport = LocalTransport()
    connector = AwinPublisherConnector(adapter_enabled=True)
    result = connector.dispatch(
        transport, "/v1/publisher/redirect",
        capability_state="VERIFIED", config=_configured(),
    )
    assert result["echo"]["adapter_id"] == "awin_publisher"
    assert len(transport.calls) == 1


# --------------------------------------------------------------------------
# adapter surface
# --------------------------------------------------------------------------
def test_awin_adapter_readiness_is_disabled_by_default():
    awin = get_adapter("awin_publisher")
    assert awin is not None
    assert awin.enabled is False
    assert awin.readiness() == "DISABLED"


def test_disabled_adapter_refuses_invocation():
    awin = get_adapter("awin_publisher")
    transport = LocalTransport()
    with pytest.raises(AdapterDeniedError):
        awin.invoke(transport, "publisher_redirect", {})
    assert transport.calls == []
