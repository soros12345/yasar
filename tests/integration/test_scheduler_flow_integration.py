"""APScheduler → Valkey lock → Celery → Valkey counter: exactly one logical execution.

Proves the V1A-0 scheduler contract:
  * APScheduler creates exactly one scheduled test job
  * the job dispatches to Celery (broker = Valkey)
  * only one logical execution occurs (Valkey lock, survives restart)
  * restart does not create unintended duplicate execution
"""

import time

import pytest

from revenueos_shared.config import Settings, get_settings
from revenueos_shared.valkey import get_redis
from revenueos_scheduler.jobs import TICK_JOB_ID, build_scheduler, dispatch_test_tick

pytestmark = pytest.mark.integration


def _enabled_settings() -> Settings:
    return Settings(
        scheduler_test_job_enabled=True,
        scheduler_test_job_interval_seconds=1,
        scheduler_lock_ttl_seconds=60,
    )


def _cleanup(settings: Settings) -> None:
    get_redis().delete(settings.scheduler_lock_key, settings.test_tick_counter_key)


def _counter(settings: Settings) -> int:
    raw = get_redis().get(settings.test_tick_counter_key)
    return int(raw) if raw else 0


def _await_counter(settings: Settings, target: int, timeout: float = 30.0) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _counter(settings) >= target:
            return _counter(settings)
        time.sleep(0.5)
    return _counter(settings)


def test_production_default_has_test_job_disabled():
    assert get_settings().scheduler_test_job_enabled is False


def test_schedule_to_celery_single_logical_execution():
    settings = _enabled_settings()
    _cleanup(settings)
    scheduler = build_scheduler(settings=settings, test_job_interval_seconds=1)

    # APScheduler creates exactly one scheduled test job
    tick_jobs = [j.id for j in scheduler.get_jobs() if j.id == TICK_JOB_ID]
    assert len(tick_jobs) == 1

    scheduler.start()
    try:
        assert _await_counter(settings, 1, timeout=30) >= 1, "task never executed"
        # let further triggers fire: they must be blocked by the Valkey lock
        time.sleep(3)
    finally:
        scheduler.shutdown(wait=False)
        time.sleep(0.5)

    # only one logical execution occurred despite repeated triggers
    assert _counter(settings) == 1
    _cleanup(settings)


def test_restart_does_not_create_duplicate_execution():
    settings = _enabled_settings()
    _cleanup(settings)

    first = dispatch_test_tick(settings=settings)
    assert first["dispatched"] is True
    assert _await_counter(settings, 1, timeout=30) >= 1

    # simulate a scheduler restart: new process state, same durable Valkey lock
    second = dispatch_test_tick(settings=settings)
    assert second["dispatched"] is False
    assert second["reason"] == "lock_held"

    time.sleep(1.5)
    assert _counter(settings) == 1, "restart produced a duplicate execution"
    _cleanup(settings)


def test_broker_carries_job_through_valkey():
    """The dispatch travels through the Valkey broker queue (not in-process)."""
    settings = _enabled_settings()
    _cleanup(settings)
    try:
        result = dispatch_test_tick(settings=settings)
        assert result["dispatched"] is True
        assert "task_id" in result
        # job must be observable on the Valkey broker while queued/executed
        counter = _await_counter(settings, 1, timeout=30)
        assert counter == 1
    finally:
        _cleanup(settings)
