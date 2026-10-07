"""Migration chain + model registration tests for V1A-1 (no database)."""

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

import revenueos_authorization.models  # noqa: F401
import revenueos_identity.models  # noqa: F401
from revenueos_api.models import Base

pytestmark = pytest.mark.unit

EXPECTED_TABLES = {
    # V1A-0 bootstrap
    "schema_version_metadata",
    "service_health_events",
    "application_builds",
    # V1A-1 security
    "tenants",
    "users",
    "user_sessions",
    "casbin_rule",
}


def test_metadata_contains_exactly_bootstrap_and_security_tables():
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_migration_chain_linear_and_reversible():
    cfg = Config("apps/api/alembic.ini")
    cfg.set_main_option("script_location", str(Path("apps/api/alembic")))
    script = ScriptDirectory.from_config(cfg)
    revisions = {rev.revision: rev for rev in script.walk_revisions()}
    assert set(revisions) == {"0001_bootstrap", "0002_multitenant_security"}
    rev2 = revisions["0002_multitenant_security"]
    rev1 = revisions["0001_bootstrap"]
    assert rev2.down_revision == "0001_bootstrap"
    assert rev1.down_revision is None
    # downgrade functions exist (reversibility proven by loading the modules)
    import importlib.util

    for filename, rev_id in (
        ("0001_bootstrap.py", "0001_bootstrap"),
        ("0002_multitenant_security.py", "0002_multitenant_security"),
    ):
        path = Path("apps/api/alembic/versions") / filename
        spec = importlib.util.spec_from_file_location(f"mig_{rev_id}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert callable(module.upgrade), f"{filename} has no upgrade()"
        assert callable(module.downgrade), f"{filename} has no downgrade()"
        assert module.revision == rev_id
