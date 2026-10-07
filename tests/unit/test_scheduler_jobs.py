"""APScheduler job-set unit tests (no broker/service contact)."""

import pytest

from revenueos_shared.config import Settings
from revenueos_scheduler.jobs import HEARTBEAT_JOB_ID, TICK_JOB_ID, build_scheduler

pytestmark = pytest.mark.unit


def _ids(settings):
    sched = build_scheduler(settings=settings)
    return [job.id for job in sched.get_jobs()]


def test_default_job_set_contains_no_test_job():
    settings = Settings(_env_file=None, scheduler_test_job_enabled=False)
    ids = _ids(settings)
    assert HEARTBEAT_JOB_ID in ids
    assert TICK_JOB_ID not in ids


def test_enabled_creates_exactly_one_test_job():
    settings = Settings(_env_file=None, scheduler_test_job_enabled=True)
    ids = _ids(settings)
    assert ids.count(TICK_JOB_ID) == 1


def test_rebuild_after_restart_never_duplicates_jobs():
    settings = Settings(_env_file=None, scheduler_test_job_enabled=True)
    for _ in range(3):
        assert _ids(settings).count(TICK_JOB_ID) == 1
