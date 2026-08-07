from __future__ import annotations

import json
from typing import Annotated

import structlog
from fastapi import APIRouter, Header, Query, Request, status
from fastapi.responses import PlainTextResponse

from src.application.conversation.process_inbound_message import (
    InboundMessage,
    ProcessInboundMessageInput,
    ProcessInboundMessageUseCase,
)
from src.application.shared.tenant_context import TenantContext, set_current_tenant
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.business.business import Business
from src.domain.shared.channel import Channel
from src.infrastructure.config.settings import get_settings
from src.infrastructure.messaging.meta_messaging_client import meta_client_for_business
from src.infrastructure.messaging.whatsapp_client import whatsapp_client_for_business
from src.infrastructure.persistence.database import get_session_factory
from src.infrastructure.persistence.repositories.appointment_repository import AppointmentRepositoryImpl
from src.infrastructure.persistence.repositories.business_hour_repository import BusinessHourRepositoryImpl
from src.infrastructure.persistence.repositories.business_repository import BusinessRepositoryImpl
from src.infrastructure.persistence.repositories.client_repository import ClientRepositoryImpl
from src.infrastructure.persistence.repositories.conversation_repository import ConversationRepositoryImpl
from src.infrastructure.persistence.repositories.human_transfer_repository import HumanTransferRepositoryImpl
from src.infrastructure.persistence.repositories.membership_repository import (
    MembershipPlanRepositoryImpl,
    MembershipRepositoryImpl,
)
from src.infrastructure.persistence.repositories.professional_repository import ProfessionalRepositoryImpl
from src.infrastructure.persistence.repositories.service_repository import ServiceRepositoryImpl
from src.infrastructure.persistence.repositories.tenant_repository import TenantRepositoryImpl
from src.presentation.webhooks.router import _get_booking_agent, _verify_signature

log = structlog.get_logger(__name__)
meta_webhooks_router = APIRouter()


# ── Verification handshake (GET) ──────────────────────────────────────────────

@meta_webhooks_router.get("/meta")
async def verify_meta_webhook(
    hub_mode: Annotated[str, Query(alias="hub.mode")],
    hub_verify_token: Annotated[str, Query(alias="hub.verify_token")],
    hub_challenge: Annotated[str, Query(alias="hub.challenge")],
) -> PlainTextResponse:
    """Meta challenge handshake, shared by the Messenger and Instagram products.

    Both can point their callback URL at this same path.
    """
    settings = get_settings()
    expected = settings.meta_verify_token or settings.whatsapp_verify_token
    if hub_mode == "subscribe" and hub_verify_token == expected:
        log.info("meta_webhook_verified")
        return PlainTextResponse(hub_challenge)

    log.warning("meta_webhook_verification_failed", token=hub_verify_token[:8])
    return PlainTextResponse("Forbidden", status_code=status.HTTP_403_FORBIDDEN)


# ── Message ingestion (POST) ──────────────────────────────────────────────────

@meta_webhooks_router.post("/meta", status_code=status.HTTP_200_OK)
async def receive_meta_message(
    request: Request,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    """Receive Messenger and Instagram Direct messages.

    One endpoint for both products: the payload shape is identical and only the
    top-level ``object`` differs ("page" vs "instagram"). Always answers 200 —
    Meta retries anything else.
    """
    raw_body = await request.body()

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        log.error("meta_invalid_json")
        return {"status": "ok"}

    channel = _channel_for_object(payload.get("object", ""))
    if channel is None:
        log.info("meta_ignored_object", object=payload.get("object"))
        return {"status": "ok"}

    for entry in payload.get("entry", []):
        # entry.id is the Page ID (Messenger) or the Instagram account id
        recipient_id = str(entry.get("id", ""))
        events = entry.get("messaging") or entry.get("standby") or []
        inbound_events = [e for e in events if _is_inbound_message(e)]
        if not recipient_id or not inbound_events:
            continue

        await _handle_entry(
            channel=channel,
            recipient_id=recipient_id,
            events=inbound_events,
            raw_body=raw_body,
            signature_header=x_hub_signature_256,
        )

    return {"status": "ok"}


def _channel_for_object(meta_object: str) -> Channel | None:
    if meta_object == "page":
        return Channel.MESSENGER
    if meta_object == "instagram":
        return Channel.INSTAGRAM
    return None


def _is_inbound_message(event: dict) -> bool:
    """Keep only real inbound messages.

    Meta also delivers delivery receipts, read receipts and — critically —
    ``is_echo`` copies of everything the page itself sends. Replying to those
    would make the bot answer its own messages forever.
    """
    message = event.get("message")
    if message is not None:
        if message.get("is_echo"):
            return False
        return bool(message.get("text") or message.get("attachments") or message.get("quick_reply"))
    return "postback" in event


async def _handle_entry(
    *,
    channel: Channel,
    recipient_id: str,
    events: list[dict],
    raw_body: bytes,
    signature_header: str | None,
) -> None:
    """Resolve the business, verify the signature and process each message."""
    factory = get_session_factory()
    async with factory() as session:
        business_repo = BusinessRepositoryImpl(session)
        if channel == Channel.MESSENGER:
            business = await business_repo.get_by_facebook_page_id(recipient_id)
        else:
            business = await business_repo.get_by_instagram_account_id(recipient_id)

        if business is None:
            log.warning(
                "meta_unknown_recipient",
                channel=channel.value,
                recipient_id=recipient_id,
                hint="Configura el Page ID / Instagram account ID con PATCH /api/v1/businesses/{id}/channels",
            )
            return

        set_current_tenant(TenantContext(tenant_id=business.tenant_id))

        settings = get_settings()
        app_secret = business.meta_app_secret or settings.meta_app_secret or settings.whatsapp_app_secret
        if not _verify_signature(raw_body, app_secret, signature_header):
            log.warning("meta_signature_invalid", business_id=str(business.id), channel=channel.value)
            return

        if not business.facebook_page_access_token:
            log.warning("meta_no_page_token", business_id=str(business.id))
            return

        messaging = meta_client_for_business(
            page_id=business.facebook_page_id or recipient_id,
            page_access_token=business.facebook_page_access_token,
            channel=channel,
        )
        staff_notifier = _staff_notifier_for(business, settings)

        use_case = _build_use_case(session)
        services = await ServiceRepositoryImpl(session).list_by_business(business.id)
        tenant = await TenantRepositoryImpl(session).get_by_id(business.tenant_id)
        industry = tenant.industry if tenant else ""

        for event in events:
            content, extra, message_type = _extract_content(event)
            if content is None:
                continue

            sender_id = str(event.get("sender", {}).get("id", ""))
            if not sender_id:
                continue

            inbound = InboundMessage(
                external_message_id=_event_id(event, sender_id),
                from_number=sender_id,
                sender_name="",   # Meta needs a separate Graph call for the profile name
                content=content,
                message_type=message_type,
                extra_data=extra,
                channel=channel,
            )

            try:
                await use_case.execute(
                    ProcessInboundMessageInput(
                        tenant_id=business.tenant_id,
                        business_id=business.id,
                        message=inbound,
                        messaging=messaging,
                        business=business,
                        services=services,
                        industry=industry,
                        staff_notifier=staff_notifier,
                    )
                )
            except Exception:
                log.exception(
                    "meta_message_processing_error",
                    channel=channel.value,
                    business_id=str(business.id),
                )


def _staff_notifier_for(business: Business, settings):
    """WhatsApp provider used for owner alerts, or None when not configured.

    Staff alerts never go back through Messenger or Instagram: the recipient
    would have to be a page-scoped user, and the owner is not one.
    """
    if not business.whatsapp_phone_number_id:
        return None
    return whatsapp_client_for_business(
        phone_number_id=business.whatsapp_phone_number_id,
        access_token=business.whatsapp_access_token or settings.whatsapp_access_token,
    )


def _event_id(event: dict, sender_id: str) -> str:
    """Stable id for idempotency: Meta's `mid`, or a timestamp-based fallback."""
    message = event.get("message") or {}
    mid = message.get("mid")
    if mid:
        return str(mid)
    return f"pb_{sender_id}_{event.get('timestamp', '')}"


# What the agent sees when a DM carries something other than text. A bare
# "[template]" told it nothing, so it re-ran its previous action and queued the
# same lead twice; a sentence it can read keeps the conversation on track.
# "template" and "share" are what Instagram sends for a shared post or reel —
# by far the most common non-text DM there.
_ATTACHMENT_DESCRIPTIONS = {
    "template": "[el cliente compartió una publicación]",
    "share": "[el cliente compartió una publicación]",
    "story_mention": "[el cliente te mencionó en su historia]",
    "image": "[el cliente envió una imagen]",
    "video": "[el cliente envió un video]",
    "audio": "[el cliente envió un audio]",
    "file": "[el cliente envió un archivo]",
    "location": "[el cliente compartió su ubicación]",
    "fallback": "[el cliente envió un enlace]",
}


def _extract_content(event: dict) -> tuple[str | None, dict | None, str]:
    """Turn one Meta event into (content, extra_data, message_type).

    Quick replies and postbacks are mapped to the same ``button_id`` the
    WhatsApp flow already understands, so downstream code needs no changes.
    """
    if postback := event.get("postback"):
        title = postback.get("title") or postback.get("payload") or ""
        return title, {"button_id": postback.get("payload", "")}, "interactive"

    message = event.get("message") or {}

    if quick_reply := message.get("quick_reply"):
        return (
            message.get("text") or quick_reply.get("payload", ""),
            {"button_id": quick_reply.get("payload", "")},
            "interactive",
        )

    if text := message.get("text"):
        return text, None, "text"

    attachments = message.get("attachments") or []
    if attachments:
        kind = attachments[0].get("type", "file")
        return (
            _ATTACHMENT_DESCRIPTIONS.get(kind, f"[el cliente envió un archivo: {kind}]"),
            {"attachment_type": kind},
            kind if kind in ("image", "audio") else "text",
        )

    return None, None, "text"


def _build_use_case(session) -> ProcessInboundMessageUseCase:
    class _SessionUoW(UnitOfWork):
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                await session.commit()
            else:
                await session.rollback()
        async def commit(self): await session.commit()
        async def rollback(self): await session.rollback()

    return ProcessInboundMessageUseCase(
        conversations=ConversationRepositoryImpl(session),
        clients=ClientRepositoryImpl(session),
        services=ServiceRepositoryImpl(session),
        appointments=AppointmentRepositoryImpl(session),
        professionals=ProfessionalRepositoryImpl(session),
        business_hours=BusinessHourRepositoryImpl(session),
        human_transfers=HumanTransferRepositoryImpl(session),
        agent=_get_booking_agent(),
        uow=_SessionUoW(),
        membership_plans=MembershipPlanRepositoryImpl(session),
        memberships=MembershipRepositoryImpl(session),
    )
