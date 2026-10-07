"""SQLAlchemy engine/session foundation (revenueos_core)."""

from contextlib import contextmanager
from functools import lru_cache
from time import perf_counter
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for RevenueOS core ORM models."""


@lru_cache
def get_engine() -> Engine:
    from revenueos_shared.config import get_settings

    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        future=True,
    )


@lru_cache
def get_session_factory() -> sessionmaker:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ping_database(timeout_seconds: float = 2.0) -> tuple[bool, float]:
    """Health probe: SELECT 1. Returns (ok, latency_ms). Never raises."""
    start = perf_counter()
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, (perf_counter() - start) * 1000
    except Exception:
        return False, (perf_counter() - start) * 1000


def dispose_engine() -> None:
    if get_engine.cache_info().hits is not None and get_engine.cache_info().currsize:
        get_engine().dispose()
