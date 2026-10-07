"""Casbin policy persistence table (owned by RevenueOS, not a third-party adapter package)."""

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from revenueos_shared.db import Base


class CasbinRule(Base):
    __tablename__ = "casbin_rule"
    __table_args__ = (
        Index("ix_casbin_rule_ptype_v0", "ptype", "v0"),
        Index("ix_casbin_rule_v1", "v1"),
    )

    id: Mapped[int] = mapped_column(String(36), primary_key=True)
    ptype: Mapped[str] = mapped_column(String(16), nullable=False)
    v0: Mapped[str] = mapped_column(String(128), nullable=False)
    v1: Mapped[str] = mapped_column(String(128), nullable=False)
    v2: Mapped[str | None] = mapped_column(String(128), nullable=True)
    v3: Mapped[str | None] = mapped_column(String(128), nullable=True)
