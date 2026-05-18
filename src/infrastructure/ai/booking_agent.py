from __future__ import annotations

from dataclasses import dataclass

import structlog
from anthropic import AsyncAnthropic

from src.domain.business.business import Business
from src.domain.conversation.conversation import Message
from src.domain.service.service import Service
from src.infrastructure.ai.agent_tools import TOOL_DEFINITIONS, ToolContext, execute_tool
from src.infrastructure.ai.system_prompt import build_system_prompt
from src.infrastructure.config.settings import get_settings

log = structlog.get_logger(__name__)

_MAX_ITERATIONS = 5
_FALLBACK_REPLY = (
    "Lo siento, en este momento no puedo procesar tu solicitud. "
    "Por favor, contáctanos directamente para ayudarte con tu cita."
)


@dataclass(frozen=True)
class AgentInput:
    business: Business
    services: list[Service]
    client_name: str
    is_returning_client: bool
    history: list[Message]       # recent conversation messages (chronological)
    user_message: str
    tool_ctx: ToolContext
    industry: str = ""


class BookingAgent:
    """Claude-powered agentic loop for appointment booking via WhatsApp.

    Runs up to _MAX_ITERATIONS of: call Claude → handle tool_use → feed results
    back → repeat until end_turn or iteration limit.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model_reasoning
        self._max_tokens = settings.anthropic_max_tokens

    async def run(self, inp: AgentInput) -> str:
        system = build_system_prompt(
            business=inp.business,
            services=inp.services,
            client_name=inp.client_name,
            is_returning_client=inp.is_returning_client,
            industry=inp.industry,
        )

        # Convert stored Message objects → Anthropic message dicts
        messages: list[dict] = _build_message_list(inp.history, inp.user_message)

        for iteration in range(_MAX_ITERATIONS):
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            log.debug(
                "agent_iteration",
                iteration=iteration,
                stop_reason=response.stop_reason,
                content_blocks=len(response.content),
            )

            # Append the assistant's full response to the running history
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                return _extract_text(response.content)

            if response.stop_reason != "tool_use":
                # Unknown stop reason — return whatever text we got
                return _extract_text(response.content) or _FALLBACK_REPLY

            # Execute all tool_use blocks, collect results
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                log.info("agent_tool_call", tool=block.name, inputs=block.input)
                result = await execute_tool(block.name, block.input, inp.tool_ctx)
                log.debug("agent_tool_result", tool=block.name, result=result[:200])
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

            # Feed tool results back as a user turn
            messages.append({"role": "user", "content": tool_results})

        log.warning(
            "agent_max_iterations_reached",
            business_id=str(inp.tool_ctx.business_id),
            client_id=str(inp.tool_ctx.client_id),
        )
        return _FALLBACK_REPLY


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_message_list(history: list[Message], user_message: str) -> list[dict]:
    """Convert stored Messages to Anthropic format and append the new user turn."""
    messages: list[dict] = []
    for msg in history:
        role = "user" if msg.sender == "client" else "assistant"
        # Skip empty messages; Anthropic requires non-empty content
        if msg.content.strip():
            messages.append({"role": role, "content": msg.content})

    # Anthropic requires messages to alternate roles; collapse consecutive same-role
    messages = _collapse_same_role(messages)

    # Append the current inbound message
    if messages and messages[-1]["role"] == "user":
        # Merge with existing last user turn to stay valid
        messages[-1]["content"] = messages[-1]["content"] + "\n\n" + user_message
    else:
        messages.append({"role": "user", "content": user_message})

    return messages


def _collapse_same_role(messages: list[dict]) -> list[dict]:
    """Merge consecutive messages with the same role into a single turn."""
    if not messages:
        return messages
    result = [messages[0]]
    for msg in messages[1:]:
        if msg["role"] == result[-1]["role"]:
            result[-1]["content"] = result[-1]["content"] + "\n\n" + msg["content"]
        else:
            result.append(msg)
    return result


def _extract_text(content: list) -> str:
    """Pull the first text block from a response content list."""
    for block in content:
        if hasattr(block, "type") and block.type == "text" and block.text.strip():
            return block.text.strip()
    return ""
