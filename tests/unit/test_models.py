"""Bootstrap model + migration shape tests (no database)."""

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

import revenueos_ledger.models  # noqa: F401  (registers financial tables on Base)
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
    # V1A-2 financial core
    "ledger_accounts",
    "ledger_journal_entries",
    "ledger_journal_lines",
    "provider_usage_event",
    "provider_cost_event",
    # V1A-3 execution authority
    "execution_controller_runs",
    "execution_events",
    "outbox_events",
    "approval_requests",
    "workflow_instances",
    "spend_guard_decisions",
    # V1A-4 execution adapters (enforced guards)
    "provider_capabilities",
    "spend_guard_budgets",
    "execution_policies",
}


def test_exact_table_inventory():
    """Exactly bootstrap + security + financial-core tables. No offer/product/
    commission tables before their packets (V1A-5+)."""
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_first_migration_is_empty_safe_bootstrap():
    cfg = Config("apps/api/alembic.ini")
    cfg.set_main_option("script_location", str(Path("apps/api/alembic")))
    script = ScriptDirectory.from_config(cfg)
    revisions = list(script.walk_revisions())
    heads = list(script.get_heads())
    assert heads == ["0006_execution_adapters"]
    assert len(revisions) == 6
    by_id = {r.revision: r for r in revisions}
    assert by_id["0001_bootstrap"].down_revision is None
    assert by_id["0004_ledger_purge_path_fix"].down_revision == "0003_financial_core"
