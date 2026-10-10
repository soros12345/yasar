"""Provider capability registry (V1A-4).

A capability is an externally observable effect a provider can perform (for
example an Awin publisher redirect). RevenueOS may only perform a capability
that is explicitly VERIFIED and enabled; anything else is deny-by-default.

The V1A-3 ``CapabilityStub`` interface is retained in ``service`` for the
records-only hook-point; this table is the real registry.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, JSON, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from revenueos_shared.db import Base

VERIFICATION_VERIFIED = "VERIFIED"
VERIFICATION_UNVERIFIED = "UNVERIFIED"
VERIFICATION_NOT_APPLICABLE = "NOT_APPLICABLE"


class ProviderCapability(Base):
    __tablename__ = "provider_capabilities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    verification_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default=VERIFICATION_UNVERIFIED
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scope_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_provider_capabilities_provider", "provider_id"),
        Index("ix_provider_capabilities_state", "verification_state", "enabled"),
    )
