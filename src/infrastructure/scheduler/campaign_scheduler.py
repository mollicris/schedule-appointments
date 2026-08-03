"""Background scheduler for proactive WhatsApp campaigns (gym module).

Two campaigns, both template-only because they write outside Meta's 24-hour
customer service window:

  membership_expiring  Members whose plan ends within CAMPAIGN_EXPIRING_DAYS.
  winback              Clients with no activity for CAMPAIGN_INACTIVE_DAYS.

Disabled by default (``CAMPAIGNS_ENABLED=false``) and, even when enabled, each
campaign is skipped unless its template name is configured — a template must be
approved in the Meta dashboard first, otherwise Meta rejects the send.

Like the reminder scheduler, this is a privileged process: it queries across
tenants with no tenant context, so every query filters explicitly by business.

Idempotency: a row is inserted in ``campaign_sends`` BEFORE sending. The unique
index on (tenant_id, dedupe_key) means a restart, an overlapping cycle or a
second instance cannot message the same client twice about the same thing.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import structlog
from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.config.settings import get_settings
from src.infrastructure.messaging.whatsapp_client import WhatsAppClient
from src.infrastructure.persistence.database import get_session_factory
from src.infrastructure.persistence.models.business import BusinessModel
from src.infrastructure.persistence.models.client import ClientModel
from src.infrastructure.persistence.models.membership import CampaignSendModel, MembershipModel

log = structlog.get_logger(__name__)

CAMPAIGN_MEMBERSHIP_EXPIRING = "membership_expiring"
CAMPAIGN_WINBACK = "winback"


# ── Public entry point ────────────────────────────────────────────────────────


async def run_campaign_scheduler() -> None:
    """Poll loop started from the FastAPI lifespan when campaigns are enabled."""
    settings = get_settings()
    log.info(
        "campaign_scheduler_started",
        interval_seconds=settings.campaign_poll_interval_seconds,
        expiring_days=settings.campaign_expiring_days,
        inactive_days=settings.campaign_inactive_days,
    )

    while True:
        try:
            factory = get_session_factory()
            async with factory() as session:
                await run_campaigns_once(session)
        except asyncio.CancelledError:
            log.info("campaign_scheduler_stopped")
            raise
        except Exception:
            log.exception("campaign_scheduler_cycle_failed")

        await asyncio.sleep(settings.campaign_poll_interval_seconds)


async def run_campaigns_once(session: AsyncSession) -> dict[str, int]:
    """Single pass over both campaigns. Returns how many messages were sent."""
    settings = get_settings()
    sent = {CAMPAIGN_MEMBERSHIP_EXPIRING: 0, CAMPAIGN_WINBACK: 0}

    if settings.whatsapp_template_membership_expiring:
        sent[CAMPAIGN_MEMBERSHIP_EXPIRING] = await _run_expiring_memberships(session, settings)
    else:
        log.debug("campaign_skipped_no_template", campaign=CAMPAIGN_MEMBERSHIP_EXPIRING)

    if settings.whatsapp_template_winback:
        sent[CAMPAIGN_WINBACK] = await _run_winback(session, settings)
    else:
        log.debug("campaign_skipped_no_template", campaign=CAMPAIGN_WINBACK)

    return sent


# ── Campaign: memberships about to expire ─────────────────────────────────────


async def _run_expiring_memberships(session: AsyncSession, settings) -> int:
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(days=settings.campaign_expiring_days)

    rows = await session.scalars(
        select(MembershipModel).where(
            and_(
                MembershipModel.status == "active",
                MembershipModel.ends_at > now,
                MembershipModel.ends_at <= deadline,
            )
        )
    )
    memberships = list(rows)
    if not memberships:
        return 0

    log.info("campaign_expiring_found", count=len(memberships))

    sent = 0
    per_business: dict[UUID, int] = {}
    for membership in memberships:
        if per_business.get(membership.business_id, 0) >= settings.campaign_daily_send_cap:
            continue
        try:
            days_left = max(0, (membership.ends_at - now).days)
            was_sent = await _send_campaign_message(
                session=session,
                settings=settings,
                tenant_id=membership.tenant_id,
                business_id=membership.business_id,
                client_id=membership.client_id,
                campaign_key=CAMPAIGN_MEMBERSHIP_EXPIRING,
                dedupe_key=(
                    f"{CAMPAIGN_MEMBERSHIP_EXPIRING}:{membership.id}:"
                    f"{membership.ends_at.date().isoformat()}"
                ),
                template_name=settings.whatsapp_template_membership_expiring,
                body_params_builder=lambda client, business: [
                    client.name or "socio",
                    business.name,
                    str(days_left),
                ],
            )
            if was_sent:
                sent += 1
                per_business[membership.business_id] = per_business.get(membership.business_id, 0) + 1
        except Exception:
            log.exception("campaign_expiring_failed", membership_id=str(membership.id))

    return sent


# ── Campaign: inactive clients ────────────────────────────────────────────────


async def _run_winback(session: AsyncSession, settings) -> int:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.campaign_inactive_days)

    # A client counts as inactive when neither their last visit nor their last
    # message is recent. COALESCE order matters: interaction is the freshest
    # signal, then the last appointment, then when they were created.
    last_activity = ClientModel.last_interaction_at
    rows = await session.scalars(
        select(ClientModel).where(
            and_(
                ClientModel.is_active.is_(True),
                or_(
                    and_(last_activity.is_not(None), last_activity < cutoff),
                    and_(
                        last_activity.is_(None),
                        or_(
                            and_(
                                ClientModel.last_appointment_at.is_not(None),
                                ClientModel.last_appointment_at < cutoff,
                            ),
                            and_(
                                ClientModel.last_appointment_at.is_(None),
                                ClientModel.created_at < cutoff,
                            ),
                        ),
                    ),
                ),
            )
        )
    )
    clients = list(rows)
    if not clients:
        return 0

    log.info("campaign_winback_found", count=len(clients))

    sent = 0
    per_business: dict[UUID, int] = {}
    week_stamp = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"

    for client in clients:
        business = await _business_for_client(session, client)
        if business is None:
            continue
        if per_business.get(business.id, 0) >= settings.campaign_daily_send_cap:
            continue
        try:
            was_sent = await _send_campaign_message(
                session=session,
                settings=settings,
                tenant_id=client.tenant_id,
                business_id=business.id,
                client_id=client.id,
                campaign_key=CAMPAIGN_WINBACK,
                # One attempt per client per ISO week: a win-back that repeats
                # daily reads as spam and gets the number blocked.
                dedupe_key=f"{CAMPAIGN_WINBACK}:{client.id}:{week_stamp}",
                template_name=settings.whatsapp_template_winback,
                body_params_builder=lambda c, b: [c.name or "socio", b.name],
            )
            if was_sent:
                sent += 1
                per_business[business.id] = per_business.get(business.id, 0) + 1
        except Exception:
            log.exception("campaign_winback_failed", client_id=str(client.id))

    return sent


# ── Shared send path ──────────────────────────────────────────────────────────


async def _send_campaign_message(
    *,
    session: AsyncSession,
    settings,
    tenant_id: UUID,
    business_id: UUID,
    client_id: UUID,
    campaign_key: str,
    dedupe_key: str,
    template_name: str,
    body_params_builder,
) -> bool:
    """Claim the send, then send. Returns False when already claimed or unsendable."""
    claimed = await _claim_send(
        session=session,
        tenant_id=tenant_id,
        business_id=business_id,
        client_id=client_id,
        campaign_key=campaign_key,
        dedupe_key=dedupe_key,
    )
    if not claimed:
        return False   # already messaged about this

    client = await session.get(ClientModel, client_id)
    business = await session.get(BusinessModel, business_id)
    if client is None or business is None or not business.whatsapp_phone_number_id:
        log.warning("campaign_send_skipped_incomplete", dedupe_key=dedupe_key)
        return False

    wa_client = WhatsAppClient(
        phone_number_id=business.whatsapp_phone_number_id,
        access_token=business.whatsapp_access_token or settings.whatsapp_access_token,
    )
    ok = await wa_client.send_template(
        to=client.whatsapp_number,
        template_name=template_name,
        language_code=settings.whatsapp_template_language,
        body_params=body_params_builder(client, business),
    )

    if ok:
        claimed.sent_at = datetime.now(timezone.utc)
        await session.commit()
        log.info("campaign_sent", campaign=campaign_key, dedupe_key=dedupe_key)
    else:
        # Keep the claim row without sent_at: it is the audit trail of a failed
        # attempt and still prevents a retry storm against Meta.
        log.warning("campaign_send_failed", campaign=campaign_key, dedupe_key=dedupe_key)

    return ok


async def _claim_send(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    business_id: UUID,
    client_id: UUID,
    campaign_key: str,
    dedupe_key: str,
) -> CampaignSendModel | None:
    """Insert the idempotency row. None when another cycle already claimed it."""
    stmt = (
        pg_insert(CampaignSendModel)
        .values(
            id=uuid4(),
            tenant_id=tenant_id,
            business_id=business_id,
            client_id=client_id,
            campaign_key=campaign_key,
            dedupe_key=dedupe_key,
        )
        .on_conflict_do_nothing(constraint="uq_campaign_sends_tenant_dedupe")
        .returning(CampaignSendModel.id)
    )
    inserted_id = await session.scalar(stmt)
    if inserted_id is None:
        return None
    await session.commit()
    return await session.get(CampaignSendModel, inserted_id)


async def _business_for_client(session: AsyncSession, client: ClientModel) -> BusinessModel | None:
    """The client's business. Clients belong to a tenant, so pick its active business."""
    return await session.scalar(
        select(BusinessModel)
        .where(
            and_(
                BusinessModel.tenant_id == client.tenant_id,
                BusinessModel.is_active.is_(True),
            )
        )
        .limit(1)
    )
