"""Live Next.js web shell integration tests."""

import os

import pytest

httpx = pytest.importorskip("httpx")

BASE = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:3000")
TIMEOUT = 20.0

pytestmark = pytest.mark.integration


def test_web_boots_and_serves_shell():
    r = httpx.get(f"{BASE}/", timeout=TIMEOUT)
    assert r.status_code == 200, r.status_code
    assert "text/html" in r.headers.get("content-type", "")
    assert "RevenueOS" in r.text
    assert "V1A-0" in r.text or "V1A" in r.text  # environment/phase indicator present


def test_web_serves_css_asset():
    r = httpx.get(f"{BASE}/", timeout=TIMEOUT)
    hrefs = [part.split('"')[0] for part in r.text.split('href="')[1:]]
    css = [h for h in hrefs if h.endswith(".css")]
    assert css, "no stylesheet linked"
    asset = httpx.get(f"{BASE}{css[0]}", timeout=TIMEOUT)
    assert asset.status_code == 200
    assert "text/css" in asset.headers.get("content-type", "")


def test_web_proxies_api_readiness_same_origin():
    r = httpx.get(f"{BASE}/api/health/ready", timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ready"] is True
    names = {c["name"] for c in body["checks"]}
    assert {"postgres", "valkey", "worker", "scheduler"} <= names
