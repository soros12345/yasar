"""Live API integration tests against the running FastAPI service."""

import os

import pytest

httpx = pytest.importorskip("httpx")

BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
TIMEOUT = 15.0

pytestmark = pytest.mark.integration


def test_liveness():
    r = httpx.get(f"{BASE}/health", timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "api"
    assert body["phase"] == "V1A-2"
    assert body["environment"]


def test_liveness_alias():
    r = httpx.get(f"{BASE}/health/live", timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_readiness_ready_and_bootstrap_checks():
    r = httpx.get(f"{BASE}/health/ready", timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ready"] is True
    assert body["status"] == "ready"
    checks = {c["name"]: c for c in body["checks"]}
    assert {"api", "postgres", "valkey", "worker", "scheduler"} <= set(checks)
    # Readiness covers only required bootstrap dependencies (API, PostgreSQL, Valkey)
    required = {name for name, c in checks.items() if c["required_for_ready"]}
    assert required == {"api", "postgres", "valkey"}
    assert checks["postgres"]["status"] == "up"
    assert checks["valkey"]["status"] == "up"


def test_readiness_worker_and_scheduler_components_up():
    r = httpx.get(f"{BASE}/health/ready", timeout=TIMEOUT)
    checks = {c["name"]: c for c in r.json()["checks"]}
    assert checks["worker"]["status"] == "up", checks["worker"]
    assert checks["scheduler"]["status"] == "up", checks["scheduler"]


def test_correlation_id_propagated():
    r = httpx.get(
        f"{BASE}/health", timeout=TIMEOUT, headers={"X-Correlation-ID": "integration-cid-1"}
    )
    assert r.headers.get("x-correlation-id") == "integration-cid-1"


def test_correlation_id_generated_when_missing():
    r = httpx.get(f"{BASE}/health", timeout=TIMEOUT)
    cid = r.headers.get("x-correlation-id")
    assert cid and len(cid) == 32


def test_root_meta():
    r = httpx.get(f"{BASE}/", timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "revenueos-api"
    assert body["docs"] == "/docs"
