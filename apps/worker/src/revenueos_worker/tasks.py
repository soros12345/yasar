"""V1A-3 worker tasks (bootstrap/verification + execution-channel tasks).

Celery is the internal execution channel only. APScheduler decides WHEN.
Every task carries a correlation_id (query-verify-retry boundary) and is
idempotent by correlation_id where applicable. No blind retry.
"""
import logging
import socket
from datetime import datetime, timezone

from revenueos_shared.celery import make_celery
from revenueos_shared.config import get_settings
from revenueos_shared.valkey import get_redis
from revenueos_shared.correlation import get_correlation_id

from revenueos_worker.celery_app import celery

logger = logging.getLogger("revenueos.worker.tasks")


@celery.task(name="revenueos.echo_health", bind=True)
def echo_health(self) -> dict:
    """Round-trip verification task: proves worker executes and Valkey carries results."""
    logger.info(
        "echo_health executed",
        extra={"event": "task_executed", "task": "echo_health", "correlation_id": get_correlation_id()},
    )
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
        extra={"event": "task_executed", "task": "scheduler_test_tick", "correlation_id": get_correlation_id()},
    )
    return {
        "ok": True,
        "executed_count": int(count),
        "task_id": self.request.id,
        "node": socket.gethostname(),
        "time": datetime.now(timezone.utc).isoformat(),
    }


@celery.task(name="revenueos.execution.outbox_flush", bind=True)
def execution_outbox_flush(self, tenant_id: str, correlation_id: str) -> dict:
    """Internal execution-channel task: flush pending outbox events for a tenant.

    Idempotent by correlation_id — the outbox flush service is idempotent, so
    retrying the same correlation_id is safe (query-verify-retry boundary).
    """
    from revenueos_shared.db import session_scope
    from revenueos_event_backbone.service import list_pending_outbox, mark_outbox_dispatched

    logger.info(
        "execution.outbox_flush started",
        extra={"event": "outbox_flush_started", "tenant_id": tenant_id, "correlation_id": correlation_id},
    )
    dispatched = 0
    with session_scope() as db:
        pending = list_pending_outbox(db, tenant_id, limit=100)
        for outbox in pending:
            mark_outbox_dispatched(db, outbox.id, tenant_id)
            dispatched += 1
    logger.info(
        "execution.outbox_flush completed",
        extra={"event": "outbox_flush_completed", "tenant_id": tenant_id, "correlation_id": correlation_id, "dispatched": dispatched},
    )
    return {"ok": True, "tenant_id": tenant_id, "dispatched": dispatched, "correlation_id": correlation_id}
