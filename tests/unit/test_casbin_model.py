"""Casbin model + policy semantics unit tests (no database: in-memory)."""

import pytest
from casbin import Enforcer

from revenueos_authorization.enforcer import DEFAULT_ROLE_POLICIES, _model_path

pytestmark = pytest.mark.unit


def _mem_enforcer() -> Enforcer:
    e = Enforcer(_model_path())  # model only, no adapter
    assert e.model is not None
    for sec in ("r", "p", "e", "m", "g"):
        assert sec in e.model.keys(), f"model section {sec} missing"
    return e


def test_model_sections_parse():
    _mem_enforcer()


def test_admin_wildcard_within_domain():
    e = _mem_enforcer()
    e.add_policy("TENANT_ADMIN", "t1", "*", "*")
    e.add_role_for_user_in_domain("u1", "TENANT_ADMIN", "t1")
    assert e.enforce("u1", "t1", "user", "write") is True
    assert e.enforce("u1", "t1", "ledger", "read") is True  # admin wildcard, own domain


def test_domain_isolation():
    e = _mem_enforcer()
    e.add_policy("TENANT_ADMIN", "t1", "*", "*")
    e.add_role_for_user_in_domain("u1", "TENANT_ADMIN", "t1")
    assert e.enforce("u1", "t2", "user", "read") is False


def test_viewer_deny_by_default_including_unknown_objects():
    e = _mem_enforcer()
    e.add_policy("VIEWER", "t1", "user", "read")
    e.add_role_for_user_in_domain("v1", "VIEWER", "t1")
    assert e.enforce("v1", "t1", "user", "read") is True
    assert e.enforce("v1", "t1", "user", "write") is False
    assert e.enforce("v1", "t1", "session", "read") is False
    assert e.enforce("v1", "t1", "unknown-object", "read") is False


def test_unbound_user_denied_everywhere():
    e = _mem_enforcer()
    e.add_policy("VIEWER", "t1", "user", "read")
    assert e.enforce("nobody", "t1", "user", "read") is False


def test_default_role_policies_shape():
    roles = {p[0] for p in DEFAULT_ROLE_POLICIES}
    assert roles == {"TENANT_ADMIN", "OPERATOR", "VIEWER"}
    from revenueos_identity.models import ROLES

    assert roles == set(ROLES), "authorization roles must mirror identity roles"
    for _role, placeholder, obj, act in DEFAULT_ROLE_POLICIES:
        assert placeholder == "*"
        assert obj in ("*", "tenant", "user", "session")
        assert act in ("*", "read", "write")
