"""Health contract schema tests."""

import pytest
from pydantic import ValidationError

from revenueos_schemas.health import LivenessResponse, ReadinessResponse, ServiceCheck

pytestmark = pytest.mark.unit


def test_service_check_defaults_to_not_required():
    c = ServiceCheck(name="postgres", status="up")
    assert c.required_for_ready is False
    assert c.latency_ms is None


def test_service_check_rejects_bad_status():
    with pytest.raises(ValidationError):
        ServiceCheck(name="x", status="maybe")  # type: ignore[arg-type]


def test_readiness_requires_boolean_ready_and_status():
    with pytest.raises(ValidationError):
        ReadinessResponse(
            status="ready",
            ready="yes",  # type: ignore[arg-type]
            service="api",
            version="0.1.0",
            environment="test",
            phase="V1A-0",
            time="not-a-date",  # type: ignore[arg-type]
        )


def test_liveness_roundtrip():
    r = LivenessResponse(
        status="ok",
        service="api",
        version="0.1.0+v1a0",
        environment="test",
        phase="V1A-0",
        time="2026-10-07T00:00:00Z",
    )
    assert r.status == "ok"
    assert r.model_dump()["service"] == "api"
