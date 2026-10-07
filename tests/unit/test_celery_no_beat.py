"""V1A-0 gate: Celery Beat must not exist anywhere in V1."""

import pathlib
import re

import pytest

from revenueos_shared.celery import make_celery
from revenueos_shared.config import Settings

pytestmark = pytest.mark.unit


def test_shared_factory_forces_empty_beat_schedule():
    app = make_celery("unit_probe", Settings(_env_file=None))
    assert app.conf.beat_schedule == {}


def test_worker_app_has_no_beat_schedule():
    from revenueos_worker.celery_app import celery

    assert celery.conf.beat_schedule == {}
    assert celery.conf.imports == ["revenueos_worker.tasks"]


def test_scripts_never_start_celery_beat():
    for path in sorted(pathlib.Path("scripts").glob("*.sh")):
        text = path.read_text()
        assert not re.search(r"celery[^#\n]*\bbeat\b", text), f"celery beat start found in {path}"


def test_worker_package_contains_no_beat_module():
    worker_root = pathlib.Path("apps/worker/src/revenueos_worker")
    assert not (worker_root / "beat.py").exists()
    assert not (worker_root / "schedules.py").exists()
