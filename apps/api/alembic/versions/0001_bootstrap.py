"""V1A-0 bootstrap tables (empty-safe).

Revision ID: 0001_bootstrap
Revises:
Create Date: 2026-10-07

Creates only bootstrap-safe tables. No V1A-1/V1A-2 business tables.
Safe to run against an empty revenueos_core database and reversible.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_bootstrap"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schema_version_metadata",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version_tag", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_tag"),
    )

    op.create_table(
        "service_health_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("service_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_service_health_events_service_occurred",
        "service_health_events",
        ["service_id", "occurred_at"],
    )

    op.create_table(
        "application_builds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("app_name", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("git_commit", sa.String(length=64), nullable=True),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Record the bootstrap schema milestone (idempotent, empty-safe).
    op.execute(
        "INSERT INTO schema_version_metadata (version_tag, description) "
        "VALUES ('0001_bootstrap', 'V1A-0 bootstrap schema') "
        "ON CONFLICT (version_tag) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("application_builds")
    op.drop_index("ix_service_health_events_service_occurred", table_name="service_health_events")
    op.drop_table("service_health_events")
    op.drop_table("schema_version_metadata")
