"""Health endpoints.

GET /health        — liveness
GET /health/live   — liveness (k8s-style alias)
GET /health/ready  — readiness: required bootstrap dependencies only
                     (API, PostgreSQL, Valkey). Worker and scheduler status
                     are reported as non-required components: readiness never
                     claims future systems are healthy, and a non-required
                     component never flips readiness to false.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Response
from revenueos_schemas.health import LivenessResponse, ReadinessResponse, ServiceCheck
from revenueos_shared.celery import make_celery
from revenueos_shared.config import get_settings
from revenueos_shared.db import ping_database
from revenueos_shared.valkey import get_redis, ping_valkey

logger = logging.getLogger("revenueos.api.health")
router = APIRouter(tags=["health"])


def _liveness() -> LivenessResponse:
    settings = get_settings()
    return LivenessResponse(
        status="ok",
        service="api",
        version=settings.app_version,
        environment=settings.environment,
        phase=settings.phase,
        time=datetime.now(timezone.utc),
    )


@router.get("/health", response_model=LivenessResponse)
def health_root() -> LivenessResponse:
    return _liveness()


@router.get("/health/live", response_model=LivenessResponse)
def health_live() -> LivenessResponse:
    return _liveness()


def _check_worker(settings) -> ServiceCheck:
    """Worker status via Celery control ping (non-required for readiness)."""
    try:
        celery = make_celery("revenueos_api_probe", settings)
        replies = celery.control.ping(timeout=settings.worker_ping_timeout_seconds)
        nodes = len(replies) if replies else 0
        return ServiceCheck(
            name="worker",
            status="up" if nodes > 0 else "down",
            required_for_ready=False,
            detail=f"celery_nodes={nodes}",
        )
    except Exception as exc:  # probe must never raise
        return ServiceCheck(
            name="worker",
            status="down",
            required_for_ready=False,
            detail=f"{type(exc).__name__}",
        )


def _check_scheduler(settings) -> ServiceCheck:
    """Scheduler status via Valkey heartbeat (non-required for readiness)."""
    try:
        raw = get_redis().get(settings.scheduler_heartbeat_key)
        if raw is None:
            return ServiceCheck(
                name="scheduler",
                status="down",
                required_for_ready=False,
                detail="no heartbeat recorded",
            )
        age = datetime.now(timezone.utc).timestamp() - float(raw)
        fresh = age <= settings.scheduler_heartbeat_ttl_seconds
        return ServiceCheck(
            name="scheduler",
            status="up" if fresh else "down",
            required_for_ready=False,
            detail=f"heartbeat_age_seconds={age:.1f}",
        )
    except Exception as exc:
        return ServiceCheck(
            name="scheduler",
            status="down",
            required_for_ready=False,
            detail=f"{type(exc).__name__}",
        )


@router.get("/health/ready", response_model=ReadinessResponse)
def health_ready(response: Response) -> ReadinessResponse:
    settings = get_settings()

    checks: list[ServiceCheck] = [
        ServiceCheck(name="api", status="up", latency_ms=0.0, required_for_ready=True)
    ]

    pg_ok, pg_ms = ping_database(settings.readiness_timeout_seconds)
    checks.append(
        ServiceCheck(
            name="postgres",
            status="up" if pg_ok else "down",
            latency_ms=round(pg_ms, 2),
            required_for_ready=True,
            detail=f"database={settings.postgres_db}" if pg_ok else "connection failed",
        )
    )

    vk_ok, vk_ms = ping_valkey(settings.readiness_timeout_seconds)
    checks.append(
        ServiceCheck(
            name="valkey",
            status="up" if vk_ok else "down",
            latency_ms=round(vk_ms, 2),
            required_for_ready=True,
            detail="PING ok" if vk_ok else "connection failed",
        )
    )

    # Non-required bootstrap components (informational only)
    checks.append(_check_worker(settings))
    checks.append(_check_scheduler(settings))

    ready = all(c.status == "up" for c in checks if c.required_for_ready)
    response.status_code = 200 if ready else 503

    logger.info(
        "readiness probe",
        extra={"event": "readiness", "status": "ready" if ready else "not_ready"},
    )

    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        ready=ready,
        service="api",
        version=settings.app_version,
        environment=settings.environment,
        phase=settings.phase,
        checks=checks,
        time=datetime.now(timezone.utc),
    )
