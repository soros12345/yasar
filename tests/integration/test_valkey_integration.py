"""Live Valkey integration tests (native service, no Docker)."""

import pytest

from revenueos_shared.config import get_settings
from revenueos_shared.valkey import get_redis, ping_valkey

pytestmark = pytest.mark.integration


def test_valkey_connection():
    ok, latency_ms = ping_valkey()
    assert ok, "Valkey connection failed"
    assert latency_ms >= 0


def test_set_get_delete_roundtrip():
    settings = get_settings()
    client = get_redis()
    key = "revenueos:test:integration"
    client.set(key, "value-1", ex=60)
    assert client.get(key) == "value-1"
    client.delete(key)
    assert client.get(key) is None


def test_counter_incr_for_scheduler_observations():
    settings = get_settings()
    client = get_redis()
    key = "revenueos:test:counter"
    client.delete(key)
    assert int(client.incr(key)) == 1
    assert int(client.incr(key)) == 2
    client.delete(key)
