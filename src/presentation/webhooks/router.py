from __future__ import annotations

from fastapi import APIRouter, Header, Query, Request, status

webhooks_router = APIRouter()


@webhooks_router.get("/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> str:
    """Meta verification handshake for WhatsApp Cloud API webhook.

    Returns ``hub.challenge`` if ``hub.verify_token`` matches the configured
    secret. Each tenant has its own webhook secret resolved at request time.
    """
    raise NotImplementedError("Wire VerifyWebhookUseCase here")


@webhooks_router.post("/whatsapp", status_code=status.HTTP_200_OK)
async def receive_whatsapp_message(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
) -> dict[str, str]:
    """Receive inbound WhatsApp message and route to the agent.

    Signature verification: validates ``X-Hub-Signature-256`` against the
    raw payload using HMAC-SHA256 with the tenant's app secret.

    Tenant resolution: derived from the recipient phone_number_id in the
    payload — each tenant connects their own WhatsApp Business Account
    during onboarding.
    """
    raise NotImplementedError("Wire ProcessInboundMessageUseCase here")


@webhooks_router.post("/instagram", status_code=status.HTTP_200_OK)
async def receive_instagram_message() -> dict[str, str]:
    raise NotImplementedError
