"""Como crece el costo con el largo de la conversacion.

Cada turno reenvia todo el historial, asi que el costo no es lineal. Esto mide
el costo acumulado turno a turno para saber que se esta vendiendo cuando se
cotiza "una conversacion".
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path("d:/Projects/ClaudeCode/agents/agente-citas-app/backend-appointment")
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

sys.path.insert(0, str(Path(__file__).parent))
import importlib
_008 = importlib.import_module("008_medir_costo_conversacion")
FX, PRECIOS = _008.FX, _008.PRECIOS
cargar, tool_result = _008.cargar, _008.tool_result

from anthropic import AsyncAnthropic  # noqa: E402

from src.domain.shared.channel import Channel  # noqa: E402
from src.infrastructure.ai.agent_tools import tools_for_channel  # noqa: E402
from src.infrastructure.ai.system_prompt import build_system_prompt  # noqa: E402
from src.infrastructure.config.settings import get_settings  # noqa: E402
from src.infrastructure.persistence.database import get_engine  # noqa: E402

GUION = [
    "hola",
    "que planes tienen?",
    "cuanto sale el mensual?",
    "el anual tiene descuento?",
    "y que clases hacen?",
    "las de yoga que dia son?",
    "hay clases en la manana?",
    "cuanto dura cada clase?",
    "puedo ir con un amigo?",
    "necesito llevar algo?",
    "tienen duchas?",
    "listo, gracias",
]


async def main() -> int:
    settings = get_settings()
    engine = get_engine()
    async with engine.connect() as conn:
        biz, servicios, planes, industry = await cargar(conn, "gimnasio")
    await engine.dispose()

    canal = Channel.WHATSAPP
    modelo = settings.anthropic_model_reasoning
    system = build_system_prompt(business=biz, services=servicios, client_name="Juan",
                                is_returning_client=False, industry=industry,
                                channel=canal, plans=planes)
    tools = tools_for_channel(canal)
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    p = PRECIOS[modelo]

    tot = {"in": 0, "out": 0, "cw": 0, "cr": 0}
    messages: list[dict] = []
    llamadas = 0

    print(f"  turno  llamadas   costo acumulado   costo del turno")
    print(f"  {'-' * 52}")
    previo = 0.0

    for turno, texto in enumerate(GUION, 1):
        messages.append({"role": "user", "content": texto})
        for _ in range(5):
            r = await client.messages.create(
                model=modelo, max_tokens=settings.anthropic_max_tokens,
                system=[{"type": "text", "text": system,
                         "cache_control": {"type": "ephemeral"}}],
                tools=tools, messages=messages)
            llamadas += 1
            u = r.usage
            tot["in"] += u.input_tokens
            tot["out"] += u.output_tokens
            tot["cw"] += getattr(u, "cache_creation_input_tokens", 0) or 0
            tot["cr"] += getattr(u, "cache_read_input_tokens", 0) or 0
            messages.append({"role": "assistant", "content": r.content})
            if r.stop_reason != "tool_use":
                break
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": b.id, "content": tool_result(b.name)}
                for b in r.content if b.type == "tool_use"]})

        costo = sum(tot[k] / 1e6 * p[k] for k in tot)
        marca = "  <- conversacion tipica" if turno == 6 else ""
        print(f"  {turno:>5}  {llamadas:>8}   US$ {costo:.4f}       "
              f"US$ {costo - previo:.4f}{marca}")
        previo = costo

    costo = sum(tot[k] / 1e6 * p[k] for k in tot)
    print()
    print(f"  {len(GUION)} mensajes = US$ {costo:.4f}  (Bs {costo * FX:.3f})")
    print(f"  promedio por mensaje del cliente: US$ {costo / len(GUION):.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
