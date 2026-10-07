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
}


def test_only_bootstrap_tables_declared():
    """No V1A-1/V1A-2 business tables may exist yet."""
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_single_empty_safe_migration():
    cfg = Config("apps/api/alembic.ini")
    cfg.set_main_option("script_location", str(Path("apps/api/alembic")))
    script = ScriptDirectory.from_config(cfg)
    revisions = list(script.walk_revisions())
    assert len(revisions) == 1
    rev = revisions[0]
    assert rev.revision == "0001_bootstrap"
    assert rev.down_revision is None
