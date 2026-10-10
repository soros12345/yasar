from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from revenueos_api.models import Base  # noqa: F401  (target metadata)
import revenueos_identity.models  # noqa: F401  (registers tenants/users/sessions)
import revenueos_authorization.models  # noqa: F401  (registers casbin_rule)
import revenueos_ledger.models  # noqa: F401  (registers financial core tables)
import revenueos_execution_controller.models  # noqa: F401  (registers execution_controller_runs/approval_requests)
import revenueos_event_backbone.models  # noqa: F401  (registers execution_events/outbox_events)
import revenueos_spendguard.models  # noqa: F401  (registers spend_guard_decisions)
import revenueos_workflow_state.models  # noqa: F401  (registers workflow_instances)
from revenueos_shared.config import get_settings

config = context.config

if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:  # pragma: no cover - logging config is best effort
        pass

# Authoritative connection string comes from the structured config layer.
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
