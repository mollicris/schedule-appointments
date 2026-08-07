"""Parsing of Messenger and Instagram webhook events.

The echo test is the important one: Meta redelivers every message the page
sends as an event with ``is_echo``. Treating those as inbound makes the bot
answer its own replies, forever.
"""

from src.domain.shared.channel import Channel
from src.presentation.webhooks.meta_router import (
    _channel_for_object,
    _event_id,
    _extract_content,
    _is_inbound_message,
)


def _text_event(text: str = "hola") -> dict:
    return {
        "sender": {"id": "psid_123"},
        "recipient": {"id": "page_456"},
        "timestamp": 1_900_000_000,
        "message": {"mid": "m_abc", "text": text},
    }


# ── Which object maps to which channel ───────────────────────────────────────


def test_object_page_is_messenger_and_instagram_is_instagram():
    assert _channel_for_object("page") == Channel.MESSENGER
    assert _channel_for_object("instagram") == Channel.INSTAGRAM


def test_unknown_object_is_ignored():
    """A WhatsApp payload reaching this endpoint must not be processed here."""
    assert _channel_for_object("whatsapp_business_account") is None
    assert _channel_for_object("") is None


# ── Inbound vs everything else ───────────────────────────────────────────────


def test_a_text_message_is_inbound():
    assert _is_inbound_message(_text_event()) is True


def test_echo_of_our_own_message_is_not_inbound():
    """Without this the bot replies to itself in a loop."""
    event = _text_event()
    event["message"]["is_echo"] = True

    assert _is_inbound_message(event) is False


def test_delivery_and_read_receipts_are_not_inbound():
    assert _is_inbound_message({"sender": {"id": "psid_123"}, "delivery": {"mids": ["m_1"]}}) is False
    assert _is_inbound_message({"sender": {"id": "psid_123"}, "read": {"watermark": 1}}) is False


def test_an_empty_message_is_not_inbound():
    assert _is_inbound_message({"sender": {"id": "psid_123"}, "message": {"mid": "m_1"}}) is False


def test_a_postback_is_inbound():
    event = {"sender": {"id": "psid_123"}, "postback": {"title": "Ver planes", "payload": "plans"}}

    assert _is_inbound_message(event) is True


# ── Content extraction ───────────────────────────────────────────────────────


def test_plain_text_is_extracted():
    content, extra, message_type = _extract_content(_text_event("¿cuánto cuesta?"))

    assert content == "¿cuánto cuesta?"
    assert extra is None
    assert message_type == "text"


def test_quick_reply_becomes_a_button_id():
    """Same shape the WhatsApp flow already understands, so nothing downstream changes."""
    event = _text_event("Ver planes")
    event["message"]["quick_reply"] = {"payload": "rem_confirm_123"}

    content, extra, message_type = _extract_content(event)

    assert content == "Ver planes"
    assert extra == {"button_id": "rem_confirm_123"}
    assert message_type == "interactive"


def test_postback_becomes_a_button_id():
    event = {"sender": {"id": "psid_123"}, "postback": {"title": "Empezar", "payload": "get_started"}}

    content, extra, message_type = _extract_content(event)

    assert content == "Empezar"
    assert extra == {"button_id": "get_started"}
    assert message_type == "interactive"


def _attachment_event(kind: str) -> dict:
    return {
        "sender": {"id": "psid_123"},
        "message": {"mid": "m_1", "attachments": [{"type": kind, "payload": {"url": "..."}}]},
    }


def test_attachment_becomes_a_placeholder():
    content, extra, message_type = _extract_content(_attachment_event("image"))

    assert content == "[el cliente envió una imagen]"
    assert extra == {"attachment_type": "image"}
    assert message_type == "image"


def test_a_shared_post_is_described_instead_of_labelled():
    """Instagram sends type "template" when someone shares a post or reel.

    The bare "[template]" this used to produce told the agent nothing, so it
    repeated its previous action — in production that queued the same lead a
    second time.
    """
    for kind in ("template", "share"):
        content, extra, message_type = _extract_content(_attachment_event(kind))

        assert content == "[el cliente compartió una publicación]"
        assert extra == {"attachment_type": kind}
        assert message_type == "text"


def test_an_unknown_attachment_type_still_says_something_readable():
    content, _, _ = _extract_content(_attachment_event("sticker"))

    assert content == "[el cliente envió un archivo: sticker]"


# ── Idempotency id ───────────────────────────────────────────────────────────


def test_message_id_uses_metas_mid():
    assert _event_id(_text_event(), "psid_123") == "m_abc"


def test_postback_without_mid_falls_back_to_a_stable_id():
    event = {"sender": {"id": "psid_123"}, "timestamp": 1_900_000_000, "postback": {"payload": "x"}}

    first = _event_id(event, "psid_123")
    second = _event_id(event, "psid_123")

    assert first == second          # stable: a redelivery is deduplicated
    assert "psid_123" in first
