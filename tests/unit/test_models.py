"""Bootstrap model + migration shape tests (no database)."""

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from revenueos_api.models import Base

pytestmark = pytest.mark.unit

EXPECTED_TABLES = {
    "schema_version_metadata",
    "service_health_events",
    "application_builds",
    # V1A-1 adds security tables only (registered via revenueos_identity /
    # revenueos_authorization imports in alembic/env.py)
    "tenants",
    "users",
    "user_sessions",
    "casbin_rule",
}


def test_no_business_tables_before_v1a2():
    """Only bootstrap + security tables may exist. No ledger/offer/product
    tables before their packets."""
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_first_migration_is_empty_safe_bootstrap():
    cfg = Config("apps/api/alembic.ini")
    cfg.set_main_option("script_location", str(Path("apps/api/alembic")))
    script = ScriptDirectory.from_config(cfg)
    revisions = list(script.walk_revisions())
    heads = list(script.get_heads())
    assert heads == ["0002_multitenant_security"]
    assert len(revisions) == 2
    by_id = {r.revision: r for r in revisions}
    assert by_id["0001_bootstrap"].down_revision is None
