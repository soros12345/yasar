"""Celery worker executes tasks carried by Valkey (broker/backend)."""

import pytest

from revenueos_shared.celery import make_celery

pytestmark = pytest.mark.integration


def test_echo_health_roundtrip():
    app = make_celery("integration_probe")
    result = app.send_task("revenueos.echo_health").get(timeout=30)
    assert result["ok"] is True
    assert "node" in result
    assert "time" in result


def test_task_result_stored_in_backend():
    app = make_celery("integration_probe")
    async_result = app.send_task("revenueos.echo_health")
    payload = async_result.get(timeout=30)
    assert app.AsyncResult(payload["task_id"]).successful() is True
