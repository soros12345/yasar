"""Fix the ledger append-only purge path (V1A-2 hardening).

Revision ID: 0004_ledger_purge_path_fix
Revises: 0003_financial_core
Create Date: 2026-10-07

0003's escape hatch returned NULL, which CANCELS the row operation in a
BEFORE trigger: GUC-on deletes became silent no-ops (DELETE 0) while parent
deletes cascaded, producing orphaned ledger rows. Correct semantics:
GUC-on must RETURN the row (OLD for DELETE, NEW for UPDATE) so the operation
proceeds; GUC-off continues to RAISE. Verified by controlled experiment.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004_ledger_purge_path_fix"
down_revision: Union[str, None] = "0003_financial_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FIXED_FUNCTION = """
CREATE OR REPLACE FUNCTION revenueos_ledger_append_only() RETURNS trigger AS $$
BEGIN
  IF current_setting('revenueos.allow_ledger_purge', true) = 'on' THEN
    IF TG_OP = 'DELETE' THEN
      RETURN OLD;   -- controlled purge: allow the delete
    ELSE
      RETURN NEW;   -- controlled purge: allow the update
    END IF;
  END IF;
  RAISE EXCEPTION
    'RevenueOS ledger is append-only: % on % is forbidden', TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql
"""


def upgrade() -> None:
    op.execute(FIXED_FUNCTION)


def downgrade() -> None:
    # Downgrading restores the 0003 semantics (known-buggy purge path).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION revenueos_ledger_append_only() RETURNS trigger AS $$
        BEGIN
          IF current_setting('revenueos.allow_ledger_purge', true) = 'on' THEN
            RETURN NULL;
          END IF;
          RAISE EXCEPTION
            'RevenueOS ledger is append-only: % on % is forbidden', TG_OP, TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql
        """
    )
