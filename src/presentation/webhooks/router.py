from __future__ import annotations

import hashlib
import hmac
import json
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Header, Query, Request, status
from fastapi.responses import PlainTextResponse

from src.application.conversation.process_inbound_message import (
    InboundMessage,
    ProcessInboundMessageInput,
    ProcessInboundMessageUseCase,
)
from src.application.shared.unit_of_work import UnitOfWork
from src.infrastructure.ai.booking_agent import BookingAgent
from src.infrastructure.config.settings import get_settings
from src.infrastructure.messaging.whatsapp_client import whatsapp_client_for_business
from src.infrastructure.persistence.database import get_session_factory
from src.infrastructure.persistence.repositories.appointment_repository import AppointmentRepositoryImpl
from src.infrastructure.persistence.repositories.business_hour_repository import BusinessHourRepositoryImpl
from src.infrastructure.persistence.repositories.business_repository import BusinessRepositoryImpl
from src.infrastructure.persistence.repositories.client_repository import ClientRepositoryImpl
from src.infrastructure.persistence.repositories.conversation_repository import ConversationRepositoryImpl
from src.infrastructure.persistence.repositories.professional_repository import ProfessionalRepositoryImpl
from src.infrastructure.persistence.repositories.service_repository import ServiceRepositoryImpl

log = structlog.get_logger(__name__)
webhooks_router = APIRouter()

# Single BookingAgent shared across requests (stateless — only holds an API client)
_booking_agent: BookingAgent | None = None


def _get_booking_agent() -> BookingAgent:
    global _booking_agent
    if _booking_agent is None:
        _booking_agent = BookingAgent()
    return _booking_agent


# ── Verification handshake (GET) ──────────────────────────────────────────────

@webhooks_router.get("/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: Annotated[str, Query(alias="hub.mode")],
    hub_verify_token: Annotated[str, Query(alias="hub.verify_token")],
    hub_challenge: Annotated[str, Query(alias="hub.challenge")],
) -> PlainTextResponse:
    """Meta challenge handshake: called once when registering the webhook URL."""
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        log.info("whatsapp_webhook_verified")
        return PlainTextResponse(hub_challenge)

    log.warning("whatsapp_webhook_verification_failed", token=hub_verify_token[:8])
    return PlainTextResponse("Forbidden", status_code=status.HTTP_403_FORBIDDEN)


# ── Message ingestion (POST) ──────────────────────────────────────────────────

@webhooks_router.post("/whatsapp", status_code=status.HTTP_200_OK)
async def receive_whatsapp_message(
    request: Request,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    """Receive inbound WhatsApp messages from Meta's Cloud API.

    Meta requires a 200 response within 20 s; any error must still return 200
    so Meta does not retry endlessly.
    """
    raw_body = await request.body()

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        log.error("whatsapp_invalid_json")
        return {"status": "ok"}

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if change.get("field") != "messages":
                continue

            phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
            messages = value.get("messages", [])
            contacts = {c["wa_id"]: c for c in value.get("contacts", [])}

            if not messages or not phone_number_id:
                continue

            await _handle_change(
                phone_number_id=phone_number_id,
                messages=messages,
                contacts=contacts,
                raw_body=raw_body,
                signature_header=x_hub_signature_256,
            )

    return {"status": "ok"}


async def _handle_change(
    *,
    phone_number_id: str,
    messages: list[dict],
    contacts: dict[str, Any],
    raw_body: bytes,
    signature_header: str | None,
) -> None:
    """Resolve tenant, verify HMAC, and process each message."""
    factory = get_session_factory()
    async with factory() as session:
        # 1. Resolve business by phone_number_id (global lookup, no tenant scope)
        business_repo = BusinessRepositoryImpl(session)
        business = await business_repo.get_by_whatsapp_phone_number_id(phone_number_id)

        if business is None:
            log.warning("whatsapp_unknown_phone_number_id", phone_number_id=phone_number_id)
            return

        # 2. Verify HMAC-SHA256 signature
        app_secret = business.whatsapp_app_secret or get_settings().whatsapp_app_secret
        if not _verify_signature(raw_body, app_secret, signature_header):
            log.warning("whatsapp_signature_invalid", business_id=str(business.id))
            return

        # 3. Build all per-request repositories
        conversation_repo = ConversationRepositoryImpl(session)
        client_repo = ClientRepositoryImpl(session)
        service_repo = ServiceRepositoryImpl(session)
        appointment_repo = AppointmentRepositoryImpl(session)
        professional_repo = ProfessionalRepositoryImpl(session)
        business_hour_repo = BusinessHourRepositoryImpl(session)

        # 4. Load services list once (used in system prompt + ToolContext)
        services = await service_repo.list_by_business(business.id)

        class _SessionUoW(UnitOfWork):
            async def __aenter__(self): return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    await session.commit()
                else:
                    await session.rollback()
            async def commit(self): await session.commit()
            async def rollback(self): await session.rollback()

        uow = _SessionUoW()
        settings = get_settings()

        wa_client = whatsapp_client_for_business(
            phone_number_id=phone_number_id,
            access_token=settings.whatsapp_access_token,
        )

        use_case = ProcessInboundMessageUseCase(
            conversations=conversation_repo,
            clients=client_repo,
            services=service_repo,
            appointments=appointment_repo,
            professionals=professional_repo,
            business_hours=business_hour_repo,
            agent=_get_booking_agent(),
            uow=uow,
        )

        # 5. Process each individual message
        for msg in messages:
            msg_type = msg.get("type", "text")
            content, extra = _extract_content(msg, msg_type)
            if content is None:
                continue

            contact = contacts.get(msg.get("from", ""), {})
            sender_name = contact.get("profile", {}).get("name", "")

            inbound = InboundMessage(
                whatsapp_message_id=msg["id"],
                from_number=msg["from"],
                sender_name=sender_name,
                content=content,
                message_type=msg_type,
                extra_data=extra,
            )

            try:
                await use_case.execute(
                    ProcessInboundMessageInput(
                        tenant_id=business.tenant_id,
                        business_id=business.id,
                        message=inbound,
                        whatsapp_client=wa_client,
                        business=business,
                        services=services,
                    )
                )
            except Exception:
                log.exception(
                    "whatsapp_message_processing_error",
                    wamid=msg["id"],
                    business_id=str(business.id),
                )


def _verify_signature(raw_body: bytes, app_secret: str, header: str | None) -> bool:
    """Validate X-Hub-Signature-256: sha256=<hex> using HMAC-SHA256."""
    if not header or not header.startswith("sha256="):
        return False
    expected_sig = header[len("sha256="):]
    computed = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, expected_sig)


def _extract_content(msg: dict, msg_type: str) -> tuple[str | None, dict | None]:
    """Extract text content and optional metadata from a WhatsApp message."""
    if msg_type == "text":
        return msg.get("text", {}).get("body"), None

    if msg_type == "interactive":
        interactive = msg.get("interactive", {})
        if interactive.get("type") == "button_reply":
            reply = interactive.get("button_reply", {})
            return reply.get("title"), {"button_id": reply.get("id")}
        if interactive.get("type") == "list_reply":
            reply = interactive.get("list_reply", {})
            return reply.get("title"), {"list_id": reply.get("id")}

    if msg_type == "audio":
        audio_id = msg.get("audio", {}).get("id")
        return f"[audio:{audio_id}]", {"audio_id": audio_id}

    if msg_type == "image":
        image_id = msg.get("image", {}).get("id")
        caption = msg.get("image", {}).get("caption", "")
        return caption or f"[image:{image_id}]", {"image_id": image_id}

    log.info("whatsapp_unsupported_message_type", msg_type=msg_type)
    return None, None
