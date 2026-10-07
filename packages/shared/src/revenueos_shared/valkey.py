"""Valkey (Redis-compatible) client foundation."""

from functools import lru_cache
from time import perf_counter

import redis


@lru_cache
def get_redis() -> redis.Redis:
    from revenueos_shared.config import get_settings

    settings = get_settings()
    return redis.Redis.from_url(
        settings.valkey_url,
        socket_timeout=1.5,
        socket_connect_timeout=1.5,
        decode_responses=True,
    )


def ping_valkey(timeout_seconds: float = 1.5) -> tuple[bool, float]:
    """Health probe: PING. Returns (ok, latency_ms). Never raises."""
    start = perf_counter()
    try:
        client = get_redis()
        client.socket_timeout = timeout_seconds
        client.ping()
        return True, (perf_counter() - start) * 1000
    except Exception:
        return False, (perf_counter() - start) * 1000
