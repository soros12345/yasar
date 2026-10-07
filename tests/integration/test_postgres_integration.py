"""Live PostgreSQL integration tests (native service, no Docker)."""

import pytest
from sqlalchemy import inspect, text

from revenueos_api.models import Base, ApplicationBuild, ServiceHealthEvent
from revenueos_shared.db import get_engine, ping_database, session_scope

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "schema_version_metadata",
    "service_health_events",
    "application_builds",
    "tenants",
    "users",
    "user_sessions",
    "casbin_rule",
    "alembic_version",
}


def test_database_connection():
    ok, latency_ms = ping_database()
    assert ok, "PostgreSQL connection failed"
    assert latency_ms >= 0


def test_migrations_applied_and_current():
    with get_engine().connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == "0002_multitenant_security"


def test_exact_schema_inventory():
    names = set(inspect(get_engine()).get_table_names())
    assert names == EXPECTED_TABLES, f"unexpected schema objects: {names}"
    assert set(Base.metadata.tables) | {"alembic_version"} == EXPECTED_TABLES


def test_schema_milestone_recorded():
    with get_engine().connect() as conn:
        tags = {r[0] for r in conn.execute(text("SELECT version_tag FROM schema_version_metadata"))}
    assert "0001_bootstrap" in tags


def test_orm_roundtrip_service_health_event():
    with session_scope() as session:
        event = ServiceHealthEvent(service_id="integration-test", status="HEALTHY", detail="pytest")
        session.add(event)
        session.flush()
        event_id = event.id
    try:
        with session_scope() as session:
            row = session.get(ServiceHealthEvent, event_id)
            assert row is not None
            assert row.service_id == "integration-test"
            assert row.status == "HEALTHY"
            assert row.occurred_at is not None
    finally:
        with session_scope() as session:
            row = session.get(ServiceHealthEvent, event_id)
            if row is not None:
                session.delete(row)


def test_orm_roundtrip_application_build():
    with session_scope() as session:
        build = ApplicationBuild(
            app_name="api", version="0.1.0+v1a0", git_commit=None, environment="test"
        )
        session.add(build)
        session.flush()
        build_id = build.id
    try:
        with session_scope() as session:
            row = session.get(ApplicationBuild, build_id)
            assert row is not None
            assert row.app_name == "api"
    finally:
        with session_scope() as session:
            row = session.get(ApplicationBuild, build_id)
            if row is not None:
                session.delete(row)
