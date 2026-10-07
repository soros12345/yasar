"""V1A-2 integration tests: CanonicalFinancialLedger + provider events.

Covers: balanced posting, idempotency, immutability (DB triggers),
rounding rules, tenant isolation, reconciliation, RBAC, ingestion contract.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete, text

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
from revenueos_shared.db import get_session_factory, session_scope

BASE = "http://127.0.0.1:8000"
TIMEOUT = 30.0
PASSWORD = "LedgerTestPass!42"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def world():
    """Two isolated tenants with admin/operator/viewer users."""
    suffix = uuid.uuid4().hex[:8]
    slug_a, slug_b = f"lta-{suffix}", f"ltb-{suffix}"
    with session_scope() as db:
        t_a = create_tenant(db, slug_a, "Ledger Tenant A")
        t_b = create_tenant(db, slug_b, "Ledger Tenant B")
        a_admin = create_user(db, t_a.id, f"admin@{slug_a}.test", "A Admin", PASSWORD, ROLE_TENANT_ADMIN)
        a_op = create_user(db, t_a.id, f"op@{slug_a}.test", "A Op", PASSWORD, ROLE_OPERATOR)
        a_viewer = create_user(db, t_a.id, f"viewer@{slug_a}.test", "A Viewer", PASSWORD, ROLE_VIEWER)
        b_admin = create_user(db, t_b.id, f"admin@{slug_b}.test", "B Admin", PASSWORD, ROLE_TENANT_ADMIN)
        data = {
            "t_a": t_a.id, "t_b": t_b.id, "slug_a": slug_a, "slug_b": slug_b,
            "a_admin": a_admin.id, "a_op": a_op.id, "a_viewer": a_viewer.id,
            "b_admin": b_admin.id, "suffix": suffix,
        }
    for tid in (data["t_a"], data["t_b"]):
        ensure_default_policies(tid)
    bind_role(data["a_admin"], ROLE_TENANT_ADMIN, data["t_a"])
    bind_role(data["a_op"], ROLE_OPERATOR, data["t_a"])
    bind_role(data["a_viewer"], ROLE_VIEWER, data["t_a"])
    bind_role(data["b_admin"], ROLE_TENANT_ADMIN, data["t_b"])
    yield data

    # Controlled purge: ledger is append-only; teardown uses the documented
    # operator GUC escape hatch (never used in normal operation).
    from revenueos_ledger.models import (
        LedgerAccount,
        LedgerJournalEntry,
        LedgerJournalLine,
        ProviderCostEvent,
        ProviderUsageEvent,
    )

    with session_scope() as db:
        db.execute(text("SET LOCAL revenueos.allow_ledger_purge = 'on'"))
        tenants = [data["t_a"], data["t_b"]]
        db.execute(delete(ProviderCostEvent).where(ProviderCostEvent.tenant_id.in_(tenants)))
        db.execute(delete(ProviderUsageEvent).where(ProviderUsageEvent.tenant_id.in_(tenants)))
        db.execute(text(
            "DELETE FROM ledger_journal_lines WHERE entry_id IN "
            "(SELECT id FROM ledger_journal_entries WHERE tenant_id = ANY(:tids))"
        ), {"tids": tenants})
        db.execute(delete(LedgerJournalEntry).where(LedgerJournalEntry.tenant_id.in_(tenants)))
        db.execute(delete(LedgerAccount).where(LedgerAccount.tenant_id.in_(tenants)))
        db.execute(delete(UserSession).where(UserSession.tenant_id.in_(tenants)))
        db.execute(delete(User).where(User.tenant_id.in_(tenants)))
        db.execute(delete(Tenant).where(Tenant.id.in_(tenants)))
    from revenueos_authorization.models import CasbinRule

    s = get_session_factory()()
    s.execute(text("SET revenueos.allow_ledger_purge = 'on'"))
    s.execute(delete(CasbinRule).where(
        CasbinRule.v0.in_([data["t_a"], data["t_b"], data["a_admin"],
                           data["a_op"], data["a_viewer"], data["b_admin"]])
    ))
    s.commit()
    s.close()


def login(slug: str, email: str, password: str = PASSWORD) -> str:
    r = httpx.post(f"{BASE}/api/v1/auth/login",
                   json={"tenant_slug": slug, "email": email, "password": password},
                   timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def H(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_accounts(token: str, codes: tuple[tuple[str, str, str, str], ...] = ()):
    """codes: (code, name, kind, currency)"""
    out = {}
    for code, name, kind, currency in codes:
        r = httpx.post(f"{BASE}/api/v1/ledger/accounts", headers=H(token),
                       json={"code": code, "name": name, "kind": kind, "currency": currency},
                       timeout=TIMEOUT)
        assert r.status_code == 201, r.text
        out[code] = r.json()
    return out


def post(token: str, payload: dict):
    return httpx.post(f"{BASE}/api/v1/ledger/entries", headers=H(token),
                      json=payload, timeout=TIMEOUT)


# --------------------------------------------------------------------------
# accounts + RBAC
# --------------------------------------------------------------------------
def test_account_creation_and_rbac(world):
    admin = login(world["slug_a"], f"admin@{world['slug_a']}.test")
    viewer = login(world["slug_a"], f"viewer@{world['slug_a']}.test")
    operator = login(world["slug_a"], f"op@{world['slug_a']}.test")

    accounts = make_accounts(admin, (
        ("CASH", "Cash", "ASSET", "USD"),
        ("REV", "Commission Revenue", "REVENUE", "USD"),
    ))
    assert accounts["CASH"]["normal_balance"] == "DEBIT"
    assert accounts["REV"]["normal_balance"] == "CREDIT"

    # reads allowed for operator + viewer
    assert httpx.get(f"{BASE}/api/v1/ledger/accounts", headers=H(operator),
                     timeout=TIMEOUT).status_code == 200
    assert httpx.get(f"{BASE}/api/v1/ledger/accounts", headers=H(viewer),
                     timeout=TIMEOUT).status_code == 200
    # writes forbidden for non-admin
    for tok in (viewer, operator):
        r = httpx.post(f"{BASE}/api/v1/ledger/accounts", headers=H(tok),
                       json={"code": "EVIL", "name": "x", "kind": "ASSET", "currency": "USD"},
                       timeout=TIMEOUT)
        assert r.status_code == 403

    # duplicate code rejected; unknown currency rejected (never guessed)
    r = httpx.post(f"{BASE}/api/v1/ledger/accounts", headers=H(admin),
                   json={"code": "CASH", "name": "dup", "kind": "ASSET", "currency": "USD"},
                   timeout=TIMEOUT)
    assert r.status_code == 400
    r = httpx.post(f"{BASE}/api/v1/ledger/accounts", headers=H(admin),
                   json={"code": "XYZACC", "name": "x", "kind": "ASSET", "currency": "XYZ"},
                   timeout=TIMEOUT)
    assert r.status_code == 400


# --------------------------------------------------------------------------
# posting: balance, rounding, contract strictness
# --------------------------------------------------------------------------
def test_balanced_posting_roundtrip(world):
    admin = login(world["slug_a"], f"admin@{world['slug_a']}.test")
    r = post(admin, {
        "currency": "USD",
        "description": "provider commission 10.00",
        "idempotency_key": "test-balanced-1",
        "lines": [
            {"account_code": "CASH", "side": "DEBIT", "amount": "10.00"},
            {"account_code": "REV", "side": "CREDIT", "amount": "10.00"},
        ],
    })
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["balanced"] is True
    assert entry["total_debit"] == "10.00"
    assert entry["total_credit"] == "10.00"
    assert len(entry["lines"]) == 2

    # fetch + list
    fetched = httpx.get(f"{BASE}/api/v1/ledger/entries/{entry['id']}", headers=H(admin),
                        timeout=TIMEOUT)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == entry["id"]
    listing = httpx.get(f"{BASE}/api/v1/ledger/entries", headers=H(admin),
                        timeout=TIMEOUT).json()
    assert any(e["id"] == entry["id"] for e in listing)


def test_unbalanced_posting_rejected_and_nothing_persisted(world):
    admin = login(world["slug_a"], f"admin@{world['slug_a']}.test")
    before = len(httpx.get(f"{BASE}/api/v1/ledger/entries", headers=H(admin),
                           timeout=TIMEOUT).json())
    r = post(admin, {
        "currency": "USD",
        "description": "does not balance",
        "idempotency_key": "test-unbalanced-1",
        "lines": [
            {"account_code": "CASH", "side": "DEBIT", "amount": "9.99"},
            {"account_code": "REV", "side": "CREDIT", "amount": "10.00"},
        ],
    })
    assert r.status_code == 400
    assert "balance" in r.json()["detail"]
    after = len(httpx.get(f"{BASE}/api/v1/ledger/entries", headers=H(admin),
                          timeout=TIMEOUT).json())
    assert after == before, "failed posting must persist nothing"


def test_json_numbers_rejected_at_contract_boundary(world):
    admin = login(world["slug_a"], f"admin@{world['slug_a']}.test")
    r = post(admin, {
        "currency": "USD",
        "description": "float amounts forbidden",
        "idempotency_key": "test-float-1",
        "lines": [
            {"account_code": "CASH", "side": "DEBIT", "amount": 10.005},
            {"account_code": "REV", "side": "CREDIT", "amount": 10.005},
        ],
    })
    assert r.status_code == 422, r.text  # strict schema: JSON numbers are not amounts


def test_rounding_rules_applied(world):
    admin = login(world["slug_a"], f"admin@{world['slug_a']}.test")
    make_accounts(admin, (("JPYCASH", "JPY Cash", "ASSET", "JPY"),
                          ("JPYREV", "JPY Revenue", "REVENUE", "JPY")))
    r = post(admin, {
        "currency": "JPY",
        "description": "jpy rounding",
        "idempotency_key": "test-jpy-1",
        "lines": [
            {"account_code": "JPYCASH", "side": "DEBIT", "amount": "100.6"},
            {"account_code": "JPYREV", "side": "CREDIT", "amount": "100.6"},
        ],
    })
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["total_debit"] == "101"
    assert entry["total_credit"] == "101"

    # sub-minor-unit input for USD -> non-positive after rounding -> 400
    r = post(admin, {
        "currency": "USD",
        "description": "too small",
        "idempotency_key": "test-tiny-1",
        "lines": [
            {"account_code": "CASH", "side": "DEBIT", "amount": "0.001"},
            {"account_code": "REV", "side": "CREDIT", "amount": "0.001"},
        ],
    })
    assert r.status_code == 400


def test_idempotency_reuse_and_conflict(world):
    admin = login(world["slug_a"], f"admin@{world['slug_a']}.test")
    payload = {
        "currency": "USD",
        "description": "idempotent posting",
        "idempotency_key": "test-idem-1",
        "lines": [
            {"account_code": "CASH", "side": "DEBIT", "amount": "3.50"},
            {"account_code": "REV", "side": "CREDIT", "amount": "3.50"},
        ],
    }
    first = post(admin, payload)
    assert first.status_code == 201
    second = post(admin, payload)
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"], "same key must reuse the entry"
    entries = httpx.get(f"{BASE}/api/v1/ledger/entries", headers=H(admin),
                        timeout=TIMEOUT).json()
    matches = [e for e in entries if e["idempotency_key"] == "test-idem-1"]
    assert len(matches) == 1, "idempotent repost must not duplicate"

    # same key, different content -> 409
    conflict = dict(payload)
    conflict["lines"] = [
        {"account_code": "CASH", "side": "DEBIT", "amount": "99.00"},
        {"account_code": "REV", "side": "CREDIT", "amount": "99.00"},
    ]
    r = post(admin, conflict)
    assert r.status_code == 409


# --------------------------------------------------------------------------
# immutability (database-enforced)
# --------------------------------------------------------------------------
def test_ledger_is_append_only_in_database(world):
    admin = login(world["slug_a"], f"admin@{world['slug_a']}.test")
    listing = httpx.get(f"{BASE}/api/v1/ledger/entries", headers=H(admin),
                        timeout=TIMEOUT).json()
    assert listing, "need at least one posted entry for the immutability probe"
    entry_id = listing[0]["id"]

    engine = get_session_factory()()
    try:
        with pytest.raises(Exception) as exc_info:
            engine.execute(text(
                "UPDATE ledger_journal_entries SET description='tampered' WHERE id = :id"
            ), {"id": entry_id})
        engine.rollback()
        assert "append-only" in str(exc_info.value)

        with pytest.raises(Exception) as exc_info:
            engine.execute(text(
                "DELETE FROM ledger_journal_lines WHERE entry_id = :id"
            ), {"id": entry_id})
        engine.rollback()
        assert "append-only" in str(exc_info.value)

        with pytest.raises(Exception) as exc_info:
            engine.execute(text("DELETE FROM ledger_accounts WHERE code = 'CASH'"))
        engine.rollback()
        assert "append-only" in str(exc_info.value)
    finally:
        engine.close()


# --------------------------------------------------------------------------
# reconciliation + isolation
# --------------------------------------------------------------------------
def test_balances_reconcile_to_zero(world):
    admin = login(world["slug_a"], f"admin@{world['slug_a']}.test")
    balances = httpx.get(f"{BASE}/api/v1/ledger/balances", headers=H(admin),
                         timeout=TIMEOUT).json()
    assert balances, "tenant A must have accounts"
    # Global invariant: Σ debits == Σ credits across every account
    total_debits = sum(Decimal(b["debit_total"]) for b in balances)
    total_credits = sum(Decimal(b["credit_total"]) for b in balances)
    assert total_debits == total_credits
    # every returned balance is internally consistent
    for b in balances:
        assert Decimal(b["balance"]) == Decimal(b["debit_total"]) - Decimal(b["credit_total"])


def test_tenant_isolation_financial_data(world):
    admin_a = login(world["slug_a"], f"admin@{world['slug_a']}.test")
    admin_b = login(world["slug_b"], f"admin@{world['slug_b']}.test")

    # tenant B: empty ledger (owns nothing of A's)
    assert httpx.get(f"{BASE}/api/v1/ledger/entries", headers=H(admin_b),
                     timeout=TIMEOUT).json() == []
    b_accounts = httpx.get(f"{BASE}/api/v1/ledger/accounts", headers=H(admin_b),
                           timeout=TIMEOUT).json()
    assert all(a["code"] not in {"CASH", "REV", "JPYCASH", "JPYREV"} for a in b_accounts)
    b_balances = httpx.get(f"{BASE}/api/v1/ledger/balances", headers=H(admin_b),
                           timeout=TIMEOUT).json()
    assert all(Decimal(b["debit_total"]) == 0 for b in b_balances)

    # direct cross-tenant entry fetch -> 404 (behaves as absent)
    a_entries = httpx.get(f"{BASE}/api/v1/ledger/entries", headers=H(admin_a),
                          timeout=TIMEOUT).json()
    assert a_entries
    foreign_id = a_entries[0]["id"]
    assert httpx.get(f"{BASE}/api/v1/ledger/entries/{foreign_id}", headers=H(admin_b),
                     timeout=TIMEOUT).status_code == 404

    # tenant B can create its OWN cash/rev accounts (own domain only)
    make_accounts(admin_b, (("BCASH", "B Cash", "ASSET", "USD"),))
    b_accounts = httpx.get(f"{BASE}/api/v1/ledger/accounts", headers=H(admin_b),
                           timeout=TIMEOUT).json()
    codes = {a["code"] for a in b_accounts}
    assert "BCASH" in codes and "CASH" not in codes


def test_accounting_equation_per_tenant_in_sql(world):
    """Independent DB-level reconciliation for tenant A."""
    engine = get_session_factory()()
    try:
        row = engine.execute(text("""
            SELECT COALESCE(SUM(CASE WHEN l.side='DEBIT' THEN l.amount ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN l.side='CREDIT' THEN l.amount ELSE 0 END), 0)
            FROM ledger_journal_lines l
            JOIN ledger_journal_entries e ON e.id = l.entry_id
            WHERE e.tenant_id = :tid
        """), {"tid": world["t_a"]}).one()
        engine.rollback()
        assert Decimal(row[0]) == Decimal(row[1])
        assert Decimal(row[0]) > 0
    finally:
        engine.close()


# --------------------------------------------------------------------------
# provider events ingestion contract
# --------------------------------------------------------------------------
def test_provider_usage_and_cost_ingestion(world):
    admin = login(world["slug_a"], f"admin@{world['slug_a']}.test")
    now = datetime.now(timezone.utc).isoformat()

    r = httpx.post(f"{BASE}/api/v1/provider-events/usage", headers=H(admin),
                   json={"provider_id": "awin", "occurred_at": now, "quantity": "3",
                         "unit": "request", "idempotency_key": "usage-1"},
                   timeout=TIMEOUT)
    assert r.status_code == 201, r.text
    usage = r.json()
    assert usage["provider_id"] == "awin"

    # idempotent reuse
    r2 = httpx.post(f"{BASE}/api/v1/provider-events/usage", headers=H(admin),
                    json={"provider_id": "awin", "occurred_at": now, "quantity": "3",
                          "unit": "request", "idempotency_key": "usage-1"},
                    timeout=TIMEOUT)
    assert r2.status_code == 201 and r2.json()["id"] == usage["id"]

    # float quantity rejected (strict contract)
    r = httpx.post(f"{BASE}/api/v1/provider-events/usage", headers=H(admin),
                   json={"provider_id": "awin", "occurred_at": now, "quantity": 1.5,
                         "unit": "request"},
                   timeout=TIMEOUT)
    assert r.status_code == 422

    # cost event linked to an actual posted entry
    entries = httpx.get(f"{BASE}/api/v1/ledger/entries", headers=H(admin),
                        timeout=TIMEOUT).json()
    linked_entry = entries[0]["id"]
    r = httpx.post(f"{BASE}/api/v1/provider-events/cost", headers=H(admin),
                   json={"provider_id": "awin", "occurred_at": now, "amount": "2.345",
                         "currency": "KWD", "cost_type": "api_call",
                         "usage_event_id": usage["id"],
                         "journal_entry_id": linked_entry,
                         "idempotency_key": "cost-1"},
                   timeout=TIMEOUT)
    assert r.status_code == 201, r.text
    cost = r.json()
    assert cost["amount"] == "2.345"  # KWD 3dp rounding preserved
    assert cost["journal_entry_id"] == linked_entry

    # linking to a foreign tenant's entry rejected
    admin_b = login(world["slug_b"], f"admin@{world['slug_b']}.test")
    r = httpx.post(f"{BASE}/api/v1/provider-events/cost", headers=H(admin_b),
                   json={"provider_id": "awin", "occurred_at": now, "amount": "1.00",
                         "currency": "USD", "cost_type": "api_call",
                         "journal_entry_id": linked_entry},
                   timeout=TIMEOUT)
    assert r.status_code == 400

    # zero/negative amounts rejected
    for bad in ("0", "-1.00"):
        r = httpx.post(f"{BASE}/api/v1/provider-events/cost", headers=H(admin),
                       json={"provider_id": "awin", "occurred_at": now, "amount": bad,
                             "currency": "USD", "cost_type": "x"},
                       timeout=TIMEOUT)
        assert r.status_code == 400

    # listings are tenant-scoped
    b_usage = httpx.get(f"{BASE}/api/v1/provider-events/usage", headers=H(admin_b),
                        timeout=TIMEOUT).json()
    assert all(u["id"] != usage["id"] for u in b_usage)


def test_viewer_can_read_but_not_write_events(world):
    viewer = login(world["slug_a"], f"viewer@{world['slug_a']}.test")
    assert httpx.get(f"{BASE}/api/v1/provider-events/usage", headers=H(viewer),
                     timeout=TIMEOUT).status_code == 200
    r = httpx.post(f"{BASE}/api/v1/provider-events/usage", headers=H(viewer),
                   json={"provider_id": "x", "occurred_at": "2026-10-07T00:00:00Z",
                         "quantity": "1", "unit": "request"},
                   timeout=TIMEOUT)
    assert r.status_code == 403
