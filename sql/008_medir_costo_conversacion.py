"""Costo real por perfil de conversacion, leido del usage de la API.

Tres perfiles, porque no cuestan lo mismo:
  1. gimnasio por WhatsApp, solo consultas  -> el plan Informativo
  2. peluqueria por WhatsApp, con reserva    -> el plan con agenda
  3. gimnasio por Instagram, solo consultas  -> canal social, modelo rapido

Usa el prompt y las herramientas reales de cada negocio y corre el mismo bucle
que produccion. Lo unico simulado son los resultados de las herramientas.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path("d:/Projects/ClaudeCode/agents/agente-citas-app/backend-appointment")
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from anthropic import AsyncAnthropic  # noqa: E402
from sqlalchemy import text  # noqa: E402

from src.domain.business.business import Business  # noqa: E402
from src.domain.membership.membership_plan import MembershipPlan  # noqa: E402
from src.domain.membership.value_objects import BillingPeriod  # noqa: E402
from src.domain.service.service import Service  # noqa: E402
from src.domain.shared.channel import Channel  # noqa: E402
from src.infrastructure.ai.agent_tools import tools_for_channel  # noqa: E402
from src.infrastructure.ai.system_prompt import build_system_prompt  # noqa: E402
from src.infrastructure.config.settings import get_settings  # noqa: E402
from src.infrastructure.persistence.database import get_engine  # noqa: E402

FX = 6.96
PRECIOS = {
    "claude-sonnet-4-6": {"in": 3.00, "out": 15.00, "cw": 3.75, "cr": 0.30},
    "claude-haiku-4-5-20251001": {"in": 1.00, "out": 5.00, "cw": 1.25, "cr": 0.10},
}
# Minimo de tokens que exige cada modelo para que el cache se active
MIN_CACHE = {"claude-sonnet-4-6": 1024, "claude-haiku-4-5-20251001": 4096}

CONSULTAS_GYM = [
    "hola",
    "que planes tienen?",
    "cuanto sale el mensual?",
    "el anual tiene descuento?",
    "y que clases hacen?",
    "gracias, lo voy a pensar",
]
RESERVA_PELU = [
    "hola quiero un corte",
    "para el sabado",
    "a las 11 esta bien",
    "con Ana si puede ser",
    "Juan Perez",
    "si confirmo",
]

ESCENARIOS = [
    ("Gimnasio · WhatsApp · solo consultas", "gimnasio", Channel.WHATSAPP, CONSULTAS_GYM),
    ("Peluqueria · WhatsApp · con reserva", "peluqueria", Channel.WHATSAPP, RESERVA_PELU),
    ("Gimnasio · Instagram · solo consultas", "gimnasio", Channel.INSTAGRAM, CONSULTAS_GYM),
]


def tool_result(nombre: str) -> str:
    datos = {
        "get_services": {"services": [
            {"id": "s1", "name": "Corte de dama", "duration_minutes": 45, "price_cents": 12000},
            {"id": "s2", "name": "Corte de varon", "duration_minutes": 30, "price_cents": 8000},
            {"id": "s3", "name": "Color", "duration_minutes": 120, "price_cents": 25000},
            {"id": "s4", "name": "Peinado", "duration_minutes": 60, "price_cents": 15000},
        ]},
        "get_membership_plans": {"plans": [
            {"name": "Mensual", "price_cents": 25000, "billing_period": "monthly"},
            {"name": "Trimestral", "price_cents": 65000, "billing_period": "quarterly"},
            {"name": "Anual", "price_cents": 220000, "billing_period": "annual"},
        ]},
        "get_professionals": {"professionals": [
            {"id": "p1", "name": "Ana"}, {"id": "p2", "name": "Marcos"},
            {"id": "p3", "name": "Sofia"},
        ]},
        "check_availability": {"date": "2026-08-15",
                               "slots": ["09:00", "10:00", "11:00", "15:00", "16:00"]},
        "create_appointment": {"status": "confirmada", "appointment_id": "a-9f21",
                               "scheduled_at": "2026-08-15T11:00:00-04:00"},
        "capture_lead": {"status": "lead_registrado", "keep_talking": True},
        "get_client_appointments": {"appointments": []},
    }
    return json.dumps(datos.get(nombre, {"ok": True}), ensure_ascii=False)


async def cargar(conn, slug):
    row = (await conn.execute(text(
        "select b.id, b.tenant_id, b.name, b.slug, b.phone, b.timezone "
        "from businesses b where b.slug = :s"), {"s": slug})).mappings().one()
    srows = (await conn.execute(text(
        "select name, duration_minutes, coalesce(price,0) price, capacity from services "
        "where business_id = :b and is_active"), {"b": row["id"]})).mappings().all()
    prows = (await conn.execute(text(
        "select name, price, billing_period from membership_plans "
        "where business_id = :b and is_active"), {"b": row["id"]})).mappings().all()
    industry = await conn.scalar(text("select industry from tenants where id = :t"),
                                 {"t": row["tenant_id"]})
    tid = row["tenant_id"]
    biz = Business.create(tenant_id=tid, name=row["name"], slug=row["slug"],
                          phone=row["phone"], timezone=row["timezone"])
    servicios = [Service.create(tenant_id=tid, business_id=biz.id, name=r["name"],
                                duration_minutes=r["duration_minutes"], price=r["price"],
                                capacity=r["capacity"]) for r in srows]
    planes = [MembershipPlan.create(tenant_id=tid, business_id=biz.id, name=r["name"],
                                    price=r["price"],
                                    billing_period=BillingPeriod(r["billing_period"]))
              for r in prows]
    return biz, servicios, planes, industry or ""


async def correr(client, settings, biz, servicios, planes, industry, canal, guion):
    modelo = (settings.anthropic_model_fast
              if settings.anthropic_fast_on_social and canal.is_social
              else settings.anthropic_model_reasoning)
    system = build_system_prompt(business=biz, services=servicios, client_name="Juan",
                                is_returning_client=False, industry=industry,
                                channel=canal, plans=planes)
    tools = tools_for_channel(canal)

    solo_t = (await client.messages.count_tokens(
        model=modelo, tools=tools, messages=[{"role": "user", "content": "."}])).input_tokens
    prefijo = (await client.messages.count_tokens(
        model=modelo, system=system, tools=tools,
        messages=[{"role": "user", "content": "."}])).input_tokens

    tot = {"in": 0, "out": 0, "cw": 0, "cr": 0}
    llamadas = 0
    messages: list[dict] = []

    for texto in guion:
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
                {"type": "tool_result", "tool_use_id": b.id,
                 "content": tool_result(b.name)}
                for b in r.content if b.type == "tool_use"]})

    p = PRECIOS[modelo]
    costo = sum(tot[k] / 1e6 * p[k] for k in tot)
    bruto = ((tot["in"] + tot["cw"] + tot["cr"]) / 1e6 * p["in"]
             + tot["out"] / 1e6 * p["out"])
    return {"modelo": modelo, "tools": solo_t, "prefijo": prefijo, "llamadas": llamadas,
            "costo": costo, "bruto": bruto, "min_cache": MIN_CACHE[modelo], **tot}


async def main() -> int:
    settings = get_settings()
    engine = get_engine()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    filas = []

    async with engine.connect() as conn:
        cache: dict = {}
        for etiqueta, slug, canal, guion in ESCENARIOS:
            if slug not in cache:
                cache[slug] = await cargar(conn, slug)
            biz, srv, pl, ind = cache[slug]
            print(f"midiendo: {etiqueta} ...", flush=True)
            filas.append((etiqueta, await correr(client, settings, biz, srv, pl, ind,
                                                 canal, guion)))
    await engine.dispose()

    print()
    for etiqueta, r in filas:
        cachea = "SI" if r["prefijo"] >= r["min_cache"] else "NO"
        print("=" * 68)
        print(f"  {etiqueta}")
        print("=" * 68)
        print(f"  modelo               {r['modelo']}")
        print(f"  herramientas         {r['tools']:>6,} tokens")
        print(f"  prefijo fijo         {r['prefijo']:>6,} tokens   "
              f"(minimo del modelo {r['min_cache']:,} -> cachea: {cachea})")
        print(f"  llamadas a la API    {r['llamadas']:>6}   "
              f"({len(CONSULTAS_GYM)} mensajes del cliente)")
        print(f"  entrada sin cachear  {r['in']:>6,} tokens")
        print(f"  escritura de cache   {r['cw']:>6,} tokens")
        print(f"  lectura de cache     {r['cr']:>6,} tokens")
        print(f"  salida               {r['out']:>6,} tokens")
        print(f"  --> COSTO REAL       US$ {r['costo']:.4f}   (Bs {r['costo'] * FX:.3f})")
        ahorro = (1 - r["costo"] / r["bruto"]) * 100 if r["bruto"] else 0
        print(f"      sin cache        US$ {r['bruto']:.4f}   (el cache ahorra {ahorro:.0f}%)")
        print()

    print("=" * 68)
    print("  RESUMEN — costo por conversacion de 6 mensajes")
    print("=" * 68)
    for etiqueta, r in filas:
        print(f"  {etiqueta:<40} US$ {r['costo']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
