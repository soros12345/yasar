"""SpendGuard hook-point models (V1A-3 stub).

SpendGuard is deny-by-default. The real policy engine is deferred. Today this
package documents the hook-point and the UNVERIFIED state contract.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from revenueos_shared.db import Base

SPendGuardState_UNVERIFIED = "UNVERIFIED"
SPendGuardState_DENIED = "DENIED"
SPendGuardState_ALLOWED = "ALLOWED"
SPendGuardState_DEFERRED = "DEFERRED"


class SpendGuardDecision(Base):
    __tablename__ = "spend_guard_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    intent: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SPendGuardState_UNVERIFIED
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_spendguard_tenant_state", "tenant_id", "state"),
        Index("ix_spendguard_correlation", "correlation_id"),
    )
