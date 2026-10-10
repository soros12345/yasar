"""Shared pytest fixtures for the RevenueOS V1A-0 suite."""

import os

import pytest

# Force all package models to be registered against Base.metadata so
# shared fixtures and the integration inventory assertion see the full schema.
import revenueos_identity.models  # noqa: F401
import revenueos_authorization.models  # noqa: F401
import revenueos_capabilities.models  # noqa: F401
import revenueos_ledger.models  # noqa: F401
import revenueos_execution_controller.models  # noqa: F401
import revenueos_event_backbone.models  # noqa: F401
import revenueos_spendguard.models  # noqa: F401
import revenueos_execution_controller.policy  # noqa: F401
import revenueos_workflow_state.models  # noqa: F401

os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture(autouse=True)
def _clear_settings_caches():
    """Re-read configuration and drop cached clients around every test."""
    from revenueos_shared.config import get_settings
    from revenueos_shared.db import dispose_engine, get_engine, get_session_factory
    from revenueos_shared.valkey import get_redis

    def _reset():
        get_settings.cache_clear()
        get_session_factory.cache_clear()
        get_redis.cache_clear()
        try:
            dispose_engine()
        except Exception:
            pass
        get_engine.cache_clear()

    _reset()
    yield
    _reset()
