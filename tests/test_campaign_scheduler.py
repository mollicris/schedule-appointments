"""Safety properties of the proactive campaign engine.

The engine can write to clients outside a conversation, so the important thing
to pin down is when it must NOT do anything.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.client.client import Client
from src.infrastructure.messaging.whatsapp_client import WhatsAppClient
from src.infrastructure.scheduler.campaign_scheduler import (
    CAMPAIGN_MEMBERSHIP_EXPIRING,
    CAMPAIGN_WINBACK,
    run_campaigns_once,
)


class ExplodingSession:
    """Any database access is a failure: nothing should be queried."""

    async def scalars(self, *args, **kwargs):
        raise AssertionError("the campaign engine queried the database with no template configured")

    async def scalar(self, *args, **kwargs):
        raise AssertionError("the campaign engine queried the database with no template configured")

    async def get(self, *args, **kwargs):
        raise AssertionError("the campaign engine queried the database with no template configured")


@pytest.mark.asyncio
async def test_no_campaign_runs_without_a_configured_template(monkeypatch):
    """Templates must be approved in Meta first; until then this is a no-op."""
    from src.infrastructure.config import settings as settings_module

    real_settings = settings_module.get_settings()
    monkeypatch.setattr(
        real_settings, "whatsapp_template_membership_expiring", "", raising=False
    )
    monkeypatch.setattr(real_settings, "whatsapp_template_winback", "", raising=False)

    sent = await run_campaigns_once(ExplodingSession())

    assert sent == {CAMPAIGN_MEMBERSHIP_EXPIRING: 0, CAMPAIGN_WINBACK: 0}


@pytest.mark.asyncio
async def test_send_template_fails_closed_when_no_template_name():
    """A half-configured deployment must not silently send a broken payload."""
    client = WhatsAppClient(phone_number_id="123", access_token="fake")

    result = await client.send_template(to="59170000000", template_name="")

    assert result is False


def test_record_interaction_updates_last_interaction_at():
    """Inactivity segmentation reads this field, which used to be never written."""
    client = Client.create(tenant_id=uuid4(), whatsapp_number="59170000000", name="Cris")
    assert client.last_interaction_at is None

    moment = datetime.now(timezone.utc) - timedelta(minutes=5)
    client.record_interaction(moment)

    assert client.last_interaction_at == moment
