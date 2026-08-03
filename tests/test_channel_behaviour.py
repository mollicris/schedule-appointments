"""What the agent may do on each channel, and how a social lead is captured."""

import json
from uuid import uuid4

import pytest

from src.domain.business.business import Business
from src.domain.client.client import Client
from src.domain.service.service import Service
from src.domain.shared.channel import Channel
from src.infrastructure.ai.agent_tools import ToolContext, execute_tool, tools_for_channel
from src.infrastructure.ai.system_prompt import build_system_prompt

TENANT_ID = uuid4()
BUSINESS_ID = uuid4()
CLIENT_ID = uuid4()

_BOOKING_TOOLS = {
    "book_appointment",
    "cancel_appointment",
    "reschedule_appointment",
}
_PERSONAL_DATA_TOOLS = {"get_my_appointments", "get_my_membership"}


# ── Toolset per channel ──────────────────────────────────────────────────────


@pytest.mark.parametrize("channel", [Channel.MESSENGER, Channel.INSTAGRAM])
def test_social_channels_cannot_book_or_read_personal_data(channel):
    names = {t["name"] for t in tools_for_channel(channel)}

    assert not (names & _BOOKING_TOOLS), "las redes no deben poder reservar"
    assert not (names & _PERSONAL_DATA_TOOLS), "en redes no se verifica quién escribe"
    assert "capture_lead" in names
    assert "get_membership_plans" in names   # informar precios sí


def test_whatsapp_keeps_every_tool():
    whatsapp = {t["name"] for t in tools_for_channel(Channel.WHATSAPP)}

    assert _BOOKING_TOOLS <= whatsapp
    assert _PERSONAL_DATA_TOOLS <= whatsapp


# ── Prompt per channel ───────────────────────────────────────────────────────


def _business() -> Business:
    return Business.create(
        tenant_id=TENANT_ID, name="Gimnasio", slug="gim", phone="+59171234567"
    )


def _service(business: Business) -> Service:
    return Service.create(
        tenant_id=TENANT_ID, business_id=business.id, name="Yoga", duration_minutes=60
    )


def test_social_prompt_forbids_booking_and_points_to_whatsapp():
    business = _business()

    prompt = build_system_prompt(
        business=business,
        services=[_service(business)],
        client_name="Ana",
        is_returning_client=False,
        channel=Channel.INSTAGRAM,
    )

    assert "Instagram" in prompt
    assert "NO puedes reservar" in prompt
    assert "capture_lead" in prompt
    assert business.phone in prompt


def test_whatsapp_prompt_has_no_channel_restrictions():
    business = _business()

    prompt = build_system_prompt(
        business=business,
        services=[_service(business)],
        client_name="Ana",
        is_returning_client=False,
        channel=Channel.WHATSAPP,
    )

    assert "NO puedes reservar" not in prompt


# ── capture_lead ─────────────────────────────────────────────────────────────


class MockClientRepository:
    def __init__(self, client: Client) -> None:
        self.client = client
        self.updated = False

    async def get_by_id(self, client_id):
        return self.client

    async def update(self, client) -> None:
        self.client = client
        self.updated = True


class MockHumanTransferRepository:
    def __init__(self) -> None:
        self.transfers = []

    async def add(self, transfer) -> None:
        self.transfers.append(transfer)


class MockWhatsAppNotifier:
    """Stands in for the WhatsApp provider used for staff alerts."""

    def __init__(self) -> None:
        self.sent = []

    @property
    def channel(self) -> Channel:
        return Channel.WHATSAPP

    async def send_text(self, *, to: str, body: str) -> bool:
        self.sent.append((to, body))
        return True

    async def send_buttons(self, *, to: str, body: str, buttons: list[dict]) -> bool:
        return True


def _social_context(clients, transfers, notifier) -> ToolContext:
    return ToolContext(
        tenant_id=TENANT_ID,
        business_id=BUSINESS_ID,
        client_id=CLIENT_ID,
        client_name="ig_user",
        client_whatsapp="psid_999",
        conversation_id=uuid4(),
        business_timezone="America/La_Paz",
        business_name="Gimnasio",
        services=None,
        appointments=None,
        professionals=None,
        business_hours=None,
        clients=clients,
        uow=None,
        human_transfers=transfers,
        channel=Channel.INSTAGRAM,
        staff_notifier=notifier,
        owner_whatsapp="59179559800",
    )


@pytest.mark.asyncio
async def test_capture_lead_stores_the_phone_queues_it_and_alerts_over_whatsapp():
    client = Client.create(
        tenant_id=TENANT_ID,
        name="ig_user",
        channel=Channel.INSTAGRAM,
        external_id="psid_999",
    )
    clients = MockClientRepository(client)
    transfers = MockHumanTransferRepository()
    notifier = MockWhatsAppNotifier()
    ctx = _social_context(clients, transfers, notifier)

    raw = await execute_tool(
        "capture_lead",
        {"nombre": "Ana", "telefono": "59171234567", "interes": "clases de yoga"},
        ctx,
    )
    result = json.loads(raw)

    # 1. the lead is reachable
    assert clients.client.phone == "59171234567"
    assert clients.client.name == "Ana"
    # 2. it lands in the follow-up queue, flagged as a lead, without escalating
    assert len(transfers.transfers) == 1
    assert transfers.transfers[0].kind == "lead"
    assert ctx.escalation_triggered is False
    # 3. reception is told over WhatsApp, not over Instagram
    assert notifier.sent and notifier.sent[0][0] == "59179559800"
    assert "Instagram" in notifier.sent[0][1]
    assert result["keep_talking"] is True


@pytest.mark.asyncio
async def test_capture_lead_without_phone_asks_for_it_instead_of_saving():
    clients = MockClientRepository(
        Client.create(
            tenant_id=TENANT_ID, name="ig", channel=Channel.INSTAGRAM, external_id="psid_1"
        )
    )
    transfers = MockHumanTransferRepository()
    ctx = _social_context(clients, transfers, MockWhatsAppNotifier())

    result = json.loads(
        await execute_tool("capture_lead", {"nombre": "Ana", "telefono": "  "}, ctx)
    )

    assert "error" in result
    assert transfers.transfers == []
