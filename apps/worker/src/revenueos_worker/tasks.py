"""V1A-0 worker tasks (bootstrap/verification only)."""

import logging
import socket
from datetime import datetime, timezone

from revenueos_shared.config import get_settings
from revenueos_shared.valkey import get_redis

from revenueos_worker.celery_app import celery

logger = logging.getLogger("revenueos.worker.tasks")


@celery.task(name="revenueos.echo_health", bind=True)
def echo_health(self) -> dict:
    """Round-trip verification task: proves worker executes and Valkey carries results."""
    logger.info("echo_health executed", extra={"event": "task_executed", "task": "echo_health"})
    return {
        "ok": True,
        "task_id": self.request.id,
        "node": socket.gethostname(),
        "time": datetime.now(timezone.utc).isoformat(),
    }


@celery.task(name="revenueos.scheduler_test_tick", bind=True)
def scheduler_test_tick(self) -> dict:
    """Executed when APScheduler dispatches the (disabled-by-default) test job.

    The logical execution count is stored in Valkey so duplicate scheduling
    would be observable.
    """
    settings = get_settings()
    client = get_redis()
    count = client.incr(settings.test_tick_counter_key)
    client.expire(settings.test_tick_counter_key, 3600)
    logger.info(
        "scheduler_test_tick executed",
        extra={"event": "task_executed", "task": "scheduler_test_tick"},
    )
    return {
        "ok": True,
        "executed_count": int(count),
        "task_id": self.request.id,
        "node": socket.gethostname(),
        "time": datetime.now(timezone.utc).isoformat(),
    }
