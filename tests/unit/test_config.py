"""Structured configuration layer unit tests."""

import pytest

from revenueos_shared.config import Settings

pytestmark = pytest.mark.unit


def test_core_defaults():
    s = Settings(_env_file=None)
    assert s.project_name == "RevenueOS"
    assert s.postgres_db == "revenueos_core"
    assert s.postgres_user == "revenueos"
    assert s.phase == "V1A-0"
    assert s.api_port == 8000
    assert s.web_port == 3000


def test_test_job_disabled_in_production_bootstrap_config():
    """V1A-0 gate: test-only schedule removed from default configuration."""
    assert Settings(_env_file=None).scheduler_test_job_enabled is False


def test_secret_never_leaks_into_repr_or_str():
    s = Settings(_env_file=None, postgres_password="supersecretpw123")
    assert "supersecretpw123" not in repr(s)
    assert "supersecretpw123" not in str(s)
    assert "supersecretpw123" not in s.model_dump_json()
    assert s.postgres_password.get_secret_value() == "supersecretpw123"


def test_database_url_with_password():
    s = Settings(
        _env_file=None,
        postgres_password="pw",
        postgres_host="db.internal",
        postgres_port=5433,
    )
    assert s.database_url == "postgresql+psycopg://revenueos:pw@db.internal:5433/revenueos_core"


def test_database_url_without_password():
    s = Settings(_env_file=None, postgres_password="")
    assert s.database_url == "postgresql+psycopg://revenueos@127.0.0.1:5432/revenueos_core"


def test_environment_variable_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("POSTGRES_PORT", "5499")
    s = Settings(_env_file=None)
    assert s.postgres_port == 5499
