"""Capability + decision-model enforcement stubs (V1A-3): deny-by-default, inert."""
import pytest

from revenueos_capabilities.service import CapabilityStub, is_within_scope_stub, lookup_stub
from revenueos_decision_model_adapter.service import DecisionStub, decide_stub

pytestmark = pytest.mark.unit


def test_capability_lookup_is_inert():
    assert lookup_stub("any-capability") is None


def test_capability_scope_is_deny_by_default():
    assert is_within_scope_stub("cap-1", "request", "1") is False
    assert is_within_scope_stub("cap-1", "usd", "0.00") is False


def test_capability_stub_state_is_unverified():
    stub = CapabilityStub(capability_id="cap-1", provider_id="prov-1")
    assert stub.state == "UNVERIFIED"
    assert stub.scope == "UNVERIFIED"


def test_decision_model_returns_unverified_recommendation():
    stub = decide_stub("post_journal_entry", {"tenant_id": "t1"})
    assert isinstance(stub, DecisionStub)
    assert stub.state == "UNVERIFIED"
    assert stub.recommendation is None
