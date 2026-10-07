"""Celery application factory.

V1 lock: APScheduler is the ONLY schedule authority. Celery Beat is not
used in V1 — beat_schedule is explicitly forced empty here and asserted
by the unit test suite.
"""

from celery import Celery

from revenueos_shared.config import Settings, get_settings


def make_celery(name: str, settings: Settings | None = None) -> Celery:
    settings = settings or get_settings()
    app = Celery(name, broker=settings.celery_broker_url, backend=settings.celery_result_backend)
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        task_track_started=True,
        worker_prefetch_multiplier=1,
        result_expires=3600,
        broker_connection_retry_on_startup=True,
        # CELERY BEAT MUST NOT BE USED IN V1 (one scheduler authority: APScheduler)
        beat_schedule={},
    )
    return app
