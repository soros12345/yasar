"""Celery application for the RevenueOS worker.

CELERY BEAT IS NOT USED IN V1. The only scheduler authority is APScheduler
(apps/scheduler). This module intentionally never defines beat_schedule
beyond the empty default enforced in revenueos_shared.celery.
"""

from revenueos_shared.celery import make_celery
from revenueos_shared.config import get_settings

celery = make_celery("revenueos_worker", get_settings())
celery.conf.imports = ["revenueos_worker.tasks"]
