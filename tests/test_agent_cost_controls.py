"""Model routing and prompt caching.

Neither changes what the agent says, so nothing else catches a regression here:
if the cache marker stops being sent, or booking quietly drops to the cheap
model, the bot keeps answering and only the bill (or the quality) moves.
"""

from types import SimpleNamespace

import pytest

from src.domain.shared.channel import Channel
from src.infrastructure.ai.booking_agent import BookingAgent


class _RecordingMessages:
    """Stands in for client.messages, capturing what would go to Anthropic."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="listo")],
            usage=SimpleNamespace(cache_read_input_tokens=0, cache_creation_input_tokens=0),
        )


@pytest.fixture
def agent(monkeypatch):
    """A BookingAgent whose Anthropic client only records calls."""
    a = BookingAgent()
    recorder = _RecordingMessages()
    a._client = SimpleNamespace(messages=recorder)
    a._model = "modelo-razonador"
    a._fast_model = "modelo-rapido"
    return a, recorder


# ── Which model handles which channel ────────────────────────────────────────


def test_whatsapp_stays_on_the_reasoning_model(agent):
    a, _ = agent

    assert a._model_for(Channel.WHATSAPP) == "modelo-razonador"


@pytest.mark.parametrize("channel", [Channel.MESSENGER, Channel.INSTAGRAM])
def test_social_channels_use_the_fast_model(agent, channel):
    a, _ = agent

    assert a._model_for(channel) == "modelo-rapido"


def test_turning_the_split_off_puts_social_back_on_the_reasoning_model(agent):
    a, _ = agent
    a._fast_on_social = False

    assert a._model_for(Channel.INSTAGRAM) == "modelo-razonador"


# ── Prompt caching ───────────────────────────────────────────────────────────


def test_the_system_prompt_is_marked_cacheable(agent):
    a, _ = agent

    param = a._system_param("eres un asistente")

    assert param == [
        {
            "type": "text",
            "text": "eres un asistente",
            "cache_control": {"type": "ephemeral"},
        }
    ]


def test_caching_can_be_switched_off_for_debugging(agent):
    a, _ = agent
    a._prompt_cache = False

    assert a._system_param("eres un asistente") == "eres un asistente"
