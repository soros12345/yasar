"""V1A-1 integration tests: authentication, Casbin RBAC, tenant isolation.

Requires the full native stack (API on :8000, PostgreSQL, Valkey).
Creates test-scoped tenants only — no fabricated production data.
"""

import hashlib
import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import delete, select

httpx = pytest.importorskip("httpx")

from revenueos_authorization.enforcer import bind_role, ensure_default_policies
from revenueos_identity.models import (
    ROLE_OPERATOR,
    ROLE_TENANT_ADMIN,
    ROLE_VIEWER,
    Tenant,
    User,
    UserSession,
)
from revenueos_identity.services import create_tenant, create_user
from revenueos_identity.sessions import create_session
from revenueos_shared.db import session_scope

BASE = "http://127.0.0.1:8000"
TIMEOUT = 30.0
PASSWORD = "IntegrationTestPass!99"

pytestmark = pytest.mark.integration


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def world():
    suffix = uuid.uuid4().hex[:8]
    slug_a, slug_b = f"ita-{suffix}", f"itb-{suffix}"
    email_a_admin = f"admin@{slug_a}.test"
    email_a_op = f"op@{slug_a}.test"
    email_a_viewer = f"viewer@{slug_a}.test"
    email_b_admin = f"admin@{slug_b}.test"

    with session_scope() as db:
        t_a = create_tenant(db, slug_a, "Isolation Tenant A")
        t_b = create_tenant(db, slug_b, "Isolation Tenant B")
        a_admin = create_user(db, t_a.id, email_a_admin, "A Admin", PASSWORD, ROLE_TENANT_ADMIN)
        a_op = create_user(db, t_a.id, email_a_op, "A Operator", PASSWORD, ROLE_OPERATOR)
        a_viewer = create_user(db, t_a.id, email_a_viewer, "A Viewer", PASSWORD, ROLE_VIEWER)
        b_admin = create_user(db, t_b.id, email_b_admin, "B Admin", PASSWORD, ROLE_TENANT_ADMIN)
        ids = {
            "t_a": t_a.id, "t_b": t_b.id, "slug_a": slug_a, "slug_b": slug_b,
            "a_admin": a_admin.id, "a_op": a_op.id, "a_viewer": a_viewer.id,
            "b_admin": b_admin.id, "suffix": suffix,
            "emails": {email_a_admin, email_a_op, email_a_viewer, email_b_admin},
        }

    for tid in (ids["t_a"], ids["t_b"]):
        ensure_default_policies(tid)
    bind_role(ids["a_admin"], ROLE_TENANT_ADMIN, ids["t_a"])
    bind_role(ids["a_op"], ROLE_OPERATOR, ids["t_a"])
    bind_role(ids["a_viewer"], ROLE_VIEWER, ids["t_a"])
    bind_role(ids["b_admin"], ROLE_TENANT_ADMIN, ids["t_b"])
    yield ids

    with session_scope() as db:
        db.execute(delete(UserSession).where(UserSession.tenant_id.in_([ids["t_a"], ids["t_b"]])))
        db.execute(delete(User).where(User.tenant_id.in_([ids["t_a"], ids["t_b"]])))
        db.execute(delete(Tenant).where(Tenant.id.in_([ids["t_a"], ids["t_b"]])))
    with session_scope() as db:
        pass  # ensure commit
    from revenueos_authorization.models import CasbinRule
    from revenueos_shared.db import get_session_factory

    s = get_session_factory()()
    all_ids = [ids["t_a"], ids["t_b"], ids["a_admin"], ids["a_op"], ids["a_viewer"], ids["b_admin"]]
    s.execute(delete(CasbinRule).where(
        CasbinRule.v0.in_(all_ids) | CasbinRule.v1.in_(all_ids) | CasbinRule.v2.in_(all_ids)
    ))
    s.commit()
    s.close()


def login(slug: str, email: str, password: str = PASSWORD) -> dict:
    r = httpx.post(
        f"{BASE}/api/v1/auth/login",
        json={"tenant_slug": slug, "email": email, "password": password},
        timeout=TIMEOUT,
    )
    return r


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------
# authentication
# --------------------------------------------------------------------------
def test_login_success(world):
    r = login(world["slug_a"], f"admin@{world['slug_a']}.test")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) >= 40
    assert body["user"]["role"] == ROLE_TENANT_ADMIN
    assert body["tenant"]["id"] == world["t_a"]
    assert PASSWORD not in r.text


def test_login_wrong_password_401(world):
    r = login(world["slug_a"], f"admin@{world['slug_a']}.test", "WrongPassword!123")
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_credentials"


def test_login_unknown_user_401(world):
    r = login(world["slug_a"], f"nobody@{world['slug_a']}.test")
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_credentials"


def test_login_unknown_tenant_401(world):
    r = login("does-not-exist-tenant", "x@y.z")
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_credentials"


def test_me_requires_authentication(world):
    assert httpx.get(f"{BASE}/api/v1/auth/me", timeout=TIMEOUT).status_code == 401
    assert (
        httpx.get(f"{BASE}/api/v1/auth/me", headers={"Authorization": "Bearer garbage"},
                  timeout=TIMEOUT).status_code
        == 401
    )
    assert (
        httpx.get(f"{BASE}/api/v1/auth/me", headers={"Authorization": "Token abc"},
                  timeout=TIMEOUT).status_code
        == 401
    )


def test_me_returns_principal_and_permissions(world):
    token = login(world["slug_a"], f"admin@{world['slug_a']}.test").json()["access_token"]
    r = httpx.get(f"{BASE}/api/v1/auth/me", headers=auth(token), timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert body["tenant"]["id"] == world["t_a"]
    assert body["user"]["id"] == world["a_admin"]
    assert "user" in body["permissions"] and "write" in body["permissions"]["user"]


def test_session_stored_hashed(world):
    token = login(world["slug_a"], f"viewer@{world['slug_a']}.test").json()["access_token"]
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with session_scope() as db:
        row = db.execute(
            select(UserSession).where(UserSession.token_hash == token_hash)
        ).scalar_one()
        assert row.token_hash != token
        assert row.user_id == world["a_viewer"]
        # raw token must not be stored anywhere on the row
        assert token not in str(row.__dict__)


def test_logout_revokes_session(world):
    token = login(world["slug_a"], f"op@{world['slug_a']}.test").json()["access_token"]
    assert httpx.get(f"{BASE}/api/v1/auth/me", headers=auth(token), timeout=TIMEOUT).status_code == 200
    r = httpx.post(f"{BASE}/api/v1/auth/logout", headers=auth(token), timeout=TIMEOUT)
    assert r.status_code == 200
    assert httpx.get(f"{BASE}/api/v1/auth/me", headers=auth(token), timeout=TIMEOUT).status_code == 401
    # second logout with revoked session also401
    assert httpx.post(f"{BASE}/api/v1/auth/logout", headers=auth(token), timeout=TIMEOUT).status_code == 401


def test_expired_session_rejected(world):
    with session_scope() as db:
        user = db.get(User, world["a_viewer"])
        token, _row = create_session(db, user, ttl_hours=-1)  # already expired
    assert httpx.get(f"{BASE}/api/v1/auth/me", headers=auth(token), timeout=TIMEOUT).status_code == 401


# --------------------------------------------------------------------------
# authorization (Casbin roles)
# --------------------------------------------------------------------------
def test_viewer_can_read_but_not_write(world):
    token = login(world["slug_a"], f"viewer@{world['slug_a']}.test").json()["access_token"]
    assert httpx.get(f"{BASE}/api/v1/users", headers=auth(token), timeout=TIMEOUT).status_code == 200
    r = httpx.post(
        f"{BASE}/api/v1/users",
        headers=auth(token),
        json={"email": "x@y.z", "display_name": "X", "password": PASSWORD, "role": ROLE_VIEWER},
        timeout=TIMEOUT,
    )
    assert r.status_code == 403
    assert httpx.get(f"{BASE}/api/v1/sessions", headers=auth(token), timeout=TIMEOUT).status_code == 403


def test_operator_sessions_read_but_no_user_write(world):
    token = login(world["slug_a"], f"op@{world['slug_a']}.test").json()["access_token"]
    assert httpx.get(f"{BASE}/api/v1/sessions", headers=auth(token), timeout=TIMEOUT).status_code == 200
    r = httpx.post(
        f"{BASE}/api/v1/users",
        headers=auth(token),
        json={"email": "x@y.z", "display_name": "X", "password": PASSWORD, "role": ROLE_VIEWER},
        timeout=TIMEOUT,
    )
    assert r.status_code == 403


def test_admin_creates_user_and_new_user_authenticates(world):
    admin_token = login(world["slug_a"], f"admin@{world['slug_a']}.test").json()["access_token"]
    email = f"newbie@{world['slug_a']}.test"
    r = httpx.post(
        f"{BASE}/api/v1/users",
        headers=auth(admin_token),
        json={"email": email, "display_name": "New Bie", "password": PASSWORD, "role": ROLE_VIEWER},
        timeout=TIMEOUT,
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["tenant_id"] == world["t_a"]
    assert "password" not in r.text and PASSWORD not in r.text

    token = login(world["slug_a"], email).json()["access_token"]
    me = httpx.get(f"{BASE}/api/v1/auth/me", headers=auth(token), timeout=TIMEOUT)
    assert me.status_code == 200
    assert me.json()["user"]["role"] == ROLE_VIEWER
    # new user is VIEWER: no write permission
    assert "write" not in me.json()["permissions"].get("user", [])


def test_create_user_validation_errors(world):
    admin_token = login(world["slug_a"], f"admin@{world['slug_a']}.test").json()["access_token"]
    # weak password
    r = httpx.post(f"{BASE}/api/v1/users", headers=auth(admin_token),
                   json={"email": "w@x.y", "display_name": "W", "password": "short", "role": ROLE_VIEWER},
                   timeout=TIMEOUT)
    assert r.status_code == 400
    # bad role
    r = httpx.post(f"{BASE}/api/v1/users", headers=auth(admin_token),
                   json={"email": "w@x.y", "display_name": "W", "password": PASSWORD, "role": "SUPERUSER"},
                   timeout=TIMEOUT)
    assert r.status_code == 400
    # duplicate email
    r = httpx.post(f"{BASE}/api/v1/users", headers=auth(admin_token),
                   json={"email": f"viewer@{world['slug_a']}.test", "display_name": "Dup",
                         "password": PASSWORD, "role": ROLE_VIEWER},
                   timeout=TIMEOUT)
    assert r.status_code == 400


# --------------------------------------------------------------------------
# tenant isolation (two accounts, zero cross-visibility)
# --------------------------------------------------------------------------
def test_isolation_user_lists_are_disjoint(world):
    a_token = login(world["slug_a"], f"admin@{world['slug_a']}.test").json()["access_token"]
    b_token = login(world["slug_b"], f"admin@{world['slug_b']}.test").json()["access_token"]

    a_users = httpx.get(f"{BASE}/api/v1/users", headers=auth(a_token), timeout=TIMEOUT).json()
    b_users = httpx.get(f"{BASE}/api/v1/users", headers=auth(b_token), timeout=TIMEOUT).json()

    a_emails = {u["email"] for u in a_users}
    b_emails = {u["email"] for u in b_users}
    assert a_emails and b_emails
    assert not a_emails & b_emails, "cross-tenant user visibility"
    assert all(u["tenant_id"] == world["t_a"] for u in a_users)
    assert all(u["tenant_id"] == world["t_b"] for u in b_users)
    assert f"admin@{world['slug_a']}.test" not in b_emails


def test_cross_tenant_resource_access_denied(world):
    a_token = login(world["slug_a"], f"admin@{world['slug_a']}.test").json()["access_token"]
    b_token = login(world["slug_b"], f"admin@{world['slug_b']}.test").json()["access_token"]

    # own tenant: ok
    assert httpx.get(f"{BASE}/api/v1/tenants/{world['t_a']}",
                     headers=auth(a_token), timeout=TIMEOUT).status_code == 200
    # cross-tenant:403 for both directions
    assert httpx.get(f"{BASE}/api/v1/tenants/{world['t_b']}",
                     headers=auth(a_token), timeout=TIMEOUT).status_code == 403
    assert httpx.get(f"{BASE}/api/v1/tenants/{world['t_a']}",
                     headers=auth(b_token), timeout=TIMEOUT).status_code == 403


def test_sessions_list_is_tenant_scoped(world):
    a_token = login(world["slug_a"], f"admin@{world['slug_a']}.test").json()["access_token"]
    rows = httpx.get(f"{BASE}/api/v1/sessions", headers=auth(a_token), timeout=TIMEOUT).json()
    assert rows
    with session_scope() as db:
        user_ids = {u.id for u in db.execute(
            select(User).where(User.tenant_id == world["t_a"])).scalars()}
    assert all(r["user_id"] in user_ids for r in rows)
    assert all("token_hash" not in r for r in rows)


# --------------------------------------------------------------------------
# security status gates
# --------------------------------------------------------------------------
def test_suspended_tenant_blocked(world):
    token = login(world["slug_a"], f"admin@{world['slug_a']}.test").json()["access_token"]
    try:
        with session_scope() as db:
            db.get(Tenant, world["t_a"]).status = "SUSPENDED"
        r = httpx.get(f"{BASE}/api/v1/auth/me", headers=auth(token), timeout=TIMEOUT)
        assert r.status_code == 403
        assert r.json()["detail"] == "tenant_suspended"
        # login with correct password also refused while suspended
        r2 = login(world["slug_a"], f"admin@{world['slug_a']}.test")
        assert r2.status_code == 403
        assert r2.json()["detail"] == "tenant_suspended"
    finally:
        with session_scope() as db:
            db.get(Tenant, world["t_a"]).status = "ACTIVE"
    # restored: works again
    assert httpx.get(f"{BASE}/api/v1/auth/me", headers=auth(token), timeout=TIMEOUT).status_code == 200


def test_disabled_user_blocked(world):
    email = f"disabled@{world['slug_a']}.test"
    with session_scope() as db:
        user = create_user(db, world["t_a"], email, "Disabled", PASSWORD, ROLE_VIEWER)
        user.status = "DISABLED"
        uid = user.id
    from revenueos_authorization.enforcer import bind_role as _bind
    _bind(uid, ROLE_VIEWER, world["t_a"])
    try:
        r = login(world["slug_a"], email)
        assert r.status_code == 403
        assert r.json()["detail"] == "account_disabled"
    finally:
        with session_scope() as db:
            u = db.get(User, uid)
            if u is not None:
                u.status = "ACTIVE"


# --------------------------------------------------------------------------
# route protection coverage (deny by default for every /api/v1 route)
# --------------------------------------------------------------------------
def test_openapi_path_inventory(world):
    r = httpx.get(f"{BASE}/openapi.json", timeout=TIMEOUT)
    assert r.status_code == 200
    paths = set(r.json()["paths"].keys())
    expected = {
        "/", "/health", "/health/live", "/health/ready",
        "/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/auth/me",
        "/api/v1/tenant", "/api/v1/tenants/{tenant_id}",
        "/api/v1/users", "/api/v1/sessions",
        # V1A-2 financial surface
        "/api/v1/ledger/accounts", "/api/v1/ledger/entries",
        "/api/v1/ledger/entries/{entry_id}", "/api/v1/ledger/balances",
        "/api/v1/provider-events/usage", "/api/v1/provider-events/cost",
        # V1A-3 execution authority surface
        "/api/v1/execution/decide",
        "/api/v1/execution/runs",
        "/api/v1/execution/runs/{run_id}",
        "/api/v1/execution/runs/{run_id}/execute",
        "/api/v1/execution/runs/{run_id}/verify",
        "/api/v1/execution/events",
        "/api/v1/execution/outbox/pending",
        "/api/v1/execution/workflows",
        "/api/v1/execution/workflows/{workflow_id}/verify",
        "/api/v1/approval-requests",
        "/api/v1/approval-requests/{request_id}/approve",
        "/api/v1/approval-requests/{request_id}/deny",
    }
    assert paths == expected, f"route inventory changed: {paths ^ expected}"


def test_every_protected_route_rejects_missing_token(world):
    probes = [
        ("GET", "/api/v1/auth/me", None),
        ("POST", "/api/v1/auth/logout", {}),
        ("GET", "/api/v1/tenant", None),
        ("GET", "/api/v1/tenants/some-id", None),
        ("GET", "/api/v1/users", None),
        ("POST", "/api/v1/users",
         {"email": "p@x.y", "display_name": "P", "password": PASSWORD, "role": "VIEWER"}),
        ("GET", "/api/v1/sessions", None),
        # V1A-2 financial surface
        ("GET", "/api/v1/ledger/accounts", None),
        ("POST", "/api/v1/ledger/accounts",
         {"code": "X", "name": "X", "kind": "ASSET", "currency": "USD"}),
        ("GET", "/api/v1/ledger/entries", None),
        ("POST", "/api/v1/ledger/entries",
         {"currency": "USD", "description": "x", "idempotency_key": "x",
          "lines": [{"account_code": "A", "side": "DEBIT", "amount": "1.00"},
                    {"account_code": "B", "side": "CREDIT", "amount": "1.00"}]}),
        ("GET", "/api/v1/ledger/entries/some-id", None),
        ("GET", "/api/v1/ledger/balances", None),
        ("GET", "/api/v1/provider-events/usage", None),
        ("POST", "/api/v1/provider-events/usage",
         {"provider_id": "p", "occurred_at": "2026-10-07T00:00:00Z",
          "quantity": "1", "unit": "request"}),
        ("GET", "/api/v1/provider-events/cost", None),
        ("POST", "/api/v1/provider-events/cost",
         {"provider_id": "p", "occurred_at": "2026-10-07T00:00:00Z",
          "amount": "1.00", "currency": "USD", "cost_type": "api_call"}),
        # V1A-3 execution authority surface
        ("POST", "/api/v1/execution/decide",
         {"intent": "outbox_flush", "correlation_id": "c", "payload": {}}),
        ("GET", "/api/v1/execution/runs", None),
        ("GET", "/api/v1/execution/runs/some-id", None),
        ("POST", "/api/v1/execution/runs/some-id/execute", None),
        ("POST", "/api/v1/execution/runs/some-id/verify", None),
        ("GET", "/api/v1/execution/events", None),
        ("GET", "/api/v1/execution/outbox/pending", None),
        ("POST", "/api/v1/execution/workflows", None),
        ("GET", "/api/v1/execution/workflows", None),
        ("POST", "/api/v1/execution/workflows/some-id/verify", None),
        ("GET", "/api/v1/approval-requests", None),
        ("POST", "/api/v1/approval-requests", None),
        ("POST", "/api/v1/approval-requests/some-id/approve", None),
        ("POST", "/api/v1/approval-requests/some-id/deny", None),
    ]
    for method, path, body in probes:
        r = httpx.request(method, f"{BASE}{path}", json=body, timeout=TIMEOUT)
        assert r.status_code == 401, f"{method} {path} accepted without token ({r.status_code})"
        assert r.json()["detail"] in ("not_authenticated", "invalid_token")

    # and with an invalid token
    for method, path, body in probes:
        r = httpx.request(method, f"{BASE}{path}", json=body,
                          headers={"Authorization": "Bearer not-a-real-token"}, timeout=TIMEOUT)
        assert r.status_code == 401, f"{method} {path} accepted invalid token"


def test_public_bootstrap_routes_remain_public(world):
    for path in ("/", "/health", "/health/live"):
        assert httpx.get(f"{BASE}{path}", timeout=TIMEOUT).status_code == 200
    r = httpx.get(f"{BASE}/health/ready", timeout=TIMEOUT)
    assert r.status_code == 200 and r.json()["ready"] is True


def test_correlation_id_on_protected_route(world):
    token = login(world["slug_a"], f"admin@{world['slug_a']}.test").json()["access_token"]
    r = httpx.get(f"{BASE}/api/v1/tenant", headers={**auth(token), "X-Correlation-ID": "v1a1-cid-77"},
                  timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.headers.get("x-correlation-id") == "v1a1-cid-77"


def test_api_log_contains_no_credentials(world):
    token = login(world["slug_a"], f"admin@{world['slug_a']}.test").json()["access_token"]
    log_path = Path(".runtime/logs/api.log")
    assert log_path.exists()
    tail = log_path.read_text(errors="replace")[-400_000:]
    assert token not in tail, "access token leaked into API log"
    assert PASSWORD not in tail, "password leaked into API log"
    # but successful login event IS logged (ids only)
    assert "login_succeeded" in tail
