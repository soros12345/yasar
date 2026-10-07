"""Scheduler entrypoint: run APScheduler forever.

Start: python -m revenueos_scheduler.main
There is exactly one scheduler authority (APScheduler). Celery Beat is
never started by RevenueOS in V1.
"""

import logging
import signal
import time

from revenueos_shared.config import get_settings
from revenueos_shared.logging import configure_logging

from revenueos_scheduler.jobs import build_scheduler, write_heartbeat

logger = logging.getLogger("revenueos.scheduler")


def run() -> None:
    settings = get_settings()
    configure_logging(settings, service="scheduler")

    scheduler = build_scheduler(settings)
    job_ids = [job.id for job in scheduler.get_jobs()]
    scheduler.start()
    # Heartbeat immediately so /health/ready sees the scheduler at once.
    try:
        write_heartbeat(settings)
    except Exception:
        logger.warning("initial heartbeat failed", extra={"event": "heartbeat_failed"})

    logger.info(
        "scheduler started",
        extra={"event": "scheduler_started", "component": "scheduler", "detail": f"jobs={job_ids}"},
    )

    stop = {"flag": False}

    def _shutdown(signum, frame):
        logger.info("scheduler stopping", extra={"event": "scheduler_stopping"})
        stop["flag"] = True

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    while not stop["flag"]:
        time.sleep(1)

    scheduler.shutdown(wait=False)


if __name__ == "__main__":
    run()
