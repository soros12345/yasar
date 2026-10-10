"""Structured configuration layer.

All runtime configuration flows through this layer. Secrets are held as
pydantic SecretStr so their values never appear in logs, tracebacks or
repr output. No secret values are defined here; they come from environment
variables / .env (gitignored). See .env.example for the contract.
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- identity / build ---
    project_name: str = "RevenueOS"
    environment: str = "development"
    app_version: str = "0.1.0+v1a3"
    phase: str = "V1A-3"
    log_level: str = "INFO"
    log_format: str = "json"

    # --- service endpoints ---
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_base_url: str = "http://127.0.0.1:8000"
    web_host: str = "0.0.0.0"
    web_port: int = 3000

    # --- PostgreSQL (revenueos_core) ---
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "revenueos_core"
    postgres_user: str = "revenueos"
    postgres_password: SecretStr = SecretStr("")

    # --- Valkey ---
    valkey_url: str = "redis://127.0.0.1:6379/0"
    celery_broker_url: str = "redis://127.0.0.1:6379/1"
    celery_result_backend: str = "redis://127.0.0.1:6379/2"

    # --- sessions / credentials (V1A-1) ---
    session_ttl_hours: int = 12
    pbkdf2_iterations: int = 600000

    # --- readiness / probes ---
    readiness_timeout_seconds: float = 1.5
    worker_ping_timeout_seconds: float = 1.5

    # --- scheduler (APScheduler = WHEN; Celery = EXECUTE) ---
    scheduler_heartbeat_key: str = "revenueos:scheduler:heartbeat"
    scheduler_heartbeat_interval_seconds: int = 10
    scheduler_heartbeat_ttl_seconds: int = 45
    scheduler_lock_key: str = "revenueos:scheduler:lock:v1a0_test_tick"
    scheduler_lock_ttl_seconds: int = 60
    # Test-only schedule is DISABLED in production bootstrap configuration (V1A-0 gate).
    scheduler_test_job_enabled: bool = False
    scheduler_test_job_interval_seconds: int = 30
    test_tick_counter_key: str = "revenueos:scheduler:test_tick:count"

    @property
    def database_url(self) -> str:
        password = self.postgres_password.get_secret_value()
        auth = f"{self.postgres_user}:{password}@" if password else f"{self.postgres_user}@"
        return (
            f"postgresql+psycopg://{auth}"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings singleton (clear caches in tests: get_settings.cache_clear())."""
    return Settings()
