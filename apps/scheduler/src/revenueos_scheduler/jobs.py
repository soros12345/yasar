"""APScheduler = WHEN, Celery = EXECUTE, Valkey = queue/broker/cache.

One logical scheduler authority only. Duplicate scheduled execution is
prevented by a Valkey lock (SET NX EX) that survives scheduler restarts,
and Celery Beat is never started.
"""

import logging
import time
import uuid

from apscheduler.schedulers.background import BackgroundScheduler

from revenueos_shared.celery import make_celery
from revenueos_shared.config import Settings, get_settings
from revenueos_shared.valkey import get_redis

logger = logging.getLogger("revenueos.scheduler")

TICK_JOB_ID = "v1a0_test_tick"
HEARTBEAT_JOB_ID = "scheduler_heartbeat"
TICK_TASK_NAME = "revenueos.scheduler_test_tick"


def write_heartbeat(settings: Settings | None = None) -> float:
    """Record scheduler liveness in Valkey (consumed by /health/ready)."""
    settings = settings or get_settings()
    now = time.time()
    client = get_redis()
    client.set(settings.scheduler_heartbeat_key, str(now), ex=settings.scheduler_heartbeat_ttl_seconds)
    return now


def dispatch_test_tick(settings: Settings | None = None, celery=None) -> dict:
    """Dispatch the test tick to Celery — exactly once per lock window.

    Returns {"dispatched": bool, "reason": str}.
    """
    settings = settings or get_settings()
    celery = celery or make_celery("revenueos_scheduler", settings)
    client = get_redis()

    acquired = bool(
        client.set(
            settings.scheduler_lock_key,
            uuid.uuid4().hex,
            nx=True,
            ex=settings.scheduler_lock_ttl_seconds,
        )
    )
    if not acquired:
        logger.warning(
            "duplicate schedule dispatch prevented",
            extra={"event": "duplicate_schedule_prevented", "component": "scheduler"},
        )
        return {"dispatched": False, "reason": "lock_held"}

    try:
        async_result = celery.send_task(TICK_TASK_NAME)
    except Exception:
        # Do not keep the lock if the broker rejected the dispatch.
        client.delete(settings.scheduler_lock_key)
        raise

    logger.info(
        "test tick dispatched",
        extra={"event": "tick_dispatched", "component": "scheduler", "task": TICK_TASK_NAME},
    )
    return {"dispatched": True, "reason": "ok", "task_id": async_result.id}


def build_scheduler(
    settings: Settings | None = None,
    celery=None,
    test_job_interval_seconds: int | None = None,
) -> BackgroundScheduler:
    """Build the scheduler job set (not started).

    The test-only schedule is registered only when
    settings.scheduler_test_job_enabled is true (disabled in production
    bootstrap configuration; V1A-0 gate removes it from default config).
    """
    settings = settings or get_settings()
    scheduler = BackgroundScheduler(timezone="UTC")

    scheduler.add_job(
        write_heartbeat,
        trigger="interval",
        seconds=settings.scheduler_heartbeat_interval_seconds,
        id=HEARTBEAT_JOB_ID,
        args=(settings,),
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )

    if settings.scheduler_test_job_enabled:
        interval = test_job_interval_seconds or settings.scheduler_test_job_interval_seconds
        scheduler.add_job(
            dispatch_test_tick,
            trigger="interval",
            seconds=interval,
            id=TICK_JOB_ID,
            kwargs={"settings": settings, "celery": celery},
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        logger.warning(
            "test-only schedule ENABLED (not for production bootstrap)",
            extra={"event": "test_job_enabled", "component": "scheduler"},
        )

    return scheduler
