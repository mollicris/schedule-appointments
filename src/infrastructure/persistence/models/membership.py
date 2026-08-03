from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.database import Base


class MembershipPlanModel(Base):
    __tablename__ = "membership_plans"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    business_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(127), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # in cents
    billing_period: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MembershipPlanServiceModel(Base):
    """Services included in a membership plan. No rows = every service."""

    __tablename__ = "membership_plan_services"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    membership_plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("membership_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("membership_plan_id", "service_id", name="uq_membership_plan_services_plan_service"),
    )


class CampaignSendModel(Base):
    """One row per proactive message already sent, for idempotency.

    ``dedupe_key`` encodes what the message was about (e.g.
    ``membership_expiring:<membership_id>:2026-08-15``), so re-running the job
    cannot message the same client twice about the same thing.
    """

    __tablename__ = "campaign_sends"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    business_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_key: Mapped[str] = mapped_column(String(50), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "dedupe_key", name="uq_campaign_sends_tenant_dedupe"),
    )


class MembershipModel(Base):
    __tablename__ = "memberships"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    business_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)
    membership_plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("membership_plans.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    billing_period: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    price_paid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # in cents
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    frozen_days_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    renewal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
