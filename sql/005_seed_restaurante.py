"""Crea el tenant de un restaurante con bolos, listo para atender por WhatsApp.

Hace lo mismo que el registro + wizard de la app, pero sin depender de que el
backend esté levantado ni del correo de verificación: escribe directo en la base
de DATABASE_URL. Es idempotente — si el tenant ya existe, completa lo que falte
y no duplica nada.

Uso:  .venv\\Scripts\\python.exe sql/005_seed_restaurante.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import time
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from sqlalchemy import text  # noqa: E402

from src.infrastructure.adapters.password_hasher import Argon2PasswordHasher  # noqa: E402
from src.infrastructure.persistence.database import get_engine  # noqa: E402

# ── Lo que se crea. Cambiá estos valores y volvé a correr el script. ─────────

TENANT = {
    "name": "Restaurante",
    "slug": "restaurante",
    "industry": "restaurantes",   # debe coincidir con la clave en _INDUSTRY_HINTS
    "admin_email": "restaurante@datec.com.bo",
}
PASSWORD = "Restaurante2026!"     # para entrar al dashboard

BUSINESS = {
    "name": "Restaurante",
    "slug": "restaurante",
    "phone": "59169334673",
    "timezone": "America/La_Paz",
    "description": "Restaurante con bolos, mesas y paquetes para eventos",
}

# price en CENTAVOS (45000 = Bs 450). capacity = cuántas reservas simultáneas
# admite ese servicio: 8 mesas de dos, 6 pistas, etc.
SERVICES = [
    ("Mesa para 2",          "Mesa para dos personas",                        90,  None,  8),
    ("Mesa para 4",          "Mesa para tres o cuatro personas",              90,  None,  6),
    ("Mesa para 6 a 8",      "Mesa larga para grupos",                       120,  None,  3),
    ("Pista de bolos",       "Una pista por hora, hasta 6 jugadores",         60,   8000, 6),
    ("Paquete Cumpleaños",   "Mesa decorada, torta y una hora de bolos",     180,  45000, 2),
    ("Paquete Corporativo",  "Salón privado, menú cerrado y dos pistas",     240,  90000, 1),
    ("Paquete Bolos + Cena", "Dos horas de pista más cena para dos",         150,  28000, 4),
]

# día 0 = lunes … 6 = domingo. El lunes cierra.
HOURS = [
    ("0", None, None, True),
    ("1", "12:00", "23:00", False),
    ("2", "12:00", "23:00", False),
    ("3", "12:00", "23:00", False),
    ("4", "12:00", "23:59", False),
    ("5", "12:00", "23:59", False),
    ("6", "12:00", "22:00", False),
]


async def main() -> int:
    engine = get_engine()
    creado: list[str] = []

    async with engine.begin() as conn:
        # ── Tenant ───────────────────────────────────────────────────────────
        tenant_id = await conn.scalar(
            text("select id from tenants where slug = :slug"), {"slug": TENANT["slug"]}
        )
        if tenant_id is None:
            tenant_id = uuid4()
            await conn.execute(
                text(
                    "insert into tenants (id, name, slug, admin_email, industry, status, "
                    "plan, verified_at, onboarded_at) "
                    "values (:id, :name, :slug, :email, :industry, 'active', 'trial', "
                    "now(), now())"
                ),
                {
                    "id": tenant_id,
                    "name": TENANT["name"],
                    "slug": TENANT["slug"],
                    "email": TENANT["admin_email"],
                    "industry": TENANT["industry"],
                },
            )
            creado.append("tenant")

        # ── Usuario administrador ────────────────────────────────────────────
        user_id = await conn.scalar(
            text("select id from users where email = :email"),
            {"email": TENANT["admin_email"]},
        )
        if user_id is None:
            await conn.execute(
                text(
                    "insert into users (id, tenant_id, email, password_hash, role, "
                    "email_verified, is_active) "
                    "values (:id, :tenant, :email, :hash, 'admin', true, true)"
                ),
                {
                    "id": uuid4(),
                    "tenant": tenant_id,
                    "email": TENANT["admin_email"],
                    "hash": Argon2PasswordHasher().hash(PASSWORD),
                },
            )
            creado.append("usuario admin")

        # ── Negocio ──────────────────────────────────────────────────────────
        business_id = await conn.scalar(
            text("select id from businesses where tenant_id = :t and slug = :slug"),
            {"t": tenant_id, "slug": BUSINESS["slug"]},
        )
        if business_id is None:
            business_id = uuid4()
            await conn.execute(
                text(
                    "insert into businesses (id, tenant_id, name, slug, description, "
                    "phone, timezone, is_active) "
                    "values (:id, :tenant, :name, :slug, :desc, :phone, :tz, true)"
                ),
                {
                    "id": business_id,
                    "tenant": tenant_id,
                    "name": BUSINESS["name"],
                    "slug": BUSINESS["slug"],
                    "desc": BUSINESS["description"],
                    "phone": BUSINESS["phone"],
                    "tz": BUSINESS["timezone"],
                },
            )
            creado.append("negocio")

        # ── Servicios ────────────────────────────────────────────────────────
        nuevos = 0
        for name, desc, minutes, price, capacity in SERVICES:
            existe = await conn.scalar(
                text("select 1 from services where business_id = :b and name = :n"),
                {"b": business_id, "n": name},
            )
            if existe:
                continue
            await conn.execute(
                text(
                    "insert into services (id, tenant_id, business_id, name, description, "
                    "duration_minutes, price, capacity, is_active) "
                    "values (:id, :t, :b, :n, :d, :min, :p, :cap, true)"
                ),
                {
                    "id": uuid4(), "t": tenant_id, "b": business_id, "n": name,
                    "d": desc, "min": minutes, "p": price, "cap": capacity,
                },
            )
            nuevos += 1
        if nuevos:
            creado.append(f"{nuevos} servicios")

        # ── Horarios ─────────────────────────────────────────────────────────
        horas_nuevas = 0
        for day, opens, closes, closed in HOURS:
            existe = await conn.scalar(
                text(
                    "select 1 from business_hours where business_id = :b "
                    "and day_of_week = :d and sequence = 1"
                ),
                {"b": business_id, "d": day},
            )
            if existe:
                continue
            await conn.execute(
                text(
                    "insert into business_hours (id, tenant_id, business_id, day_of_week, "
                    "open_at, close_at, is_closed, sequence) "
                    "values (:id, :t, :b, :d, :open, :close, :closed, 1)"
                ),
                {
                    "id": uuid4(), "t": tenant_id, "b": business_id, "d": day,
                    # un día cerrado igual necesita horas: la columna es NOT NULL,
                    # y asyncpg exige datetime.time, no una cadena
                    "open": time.fromisoformat(opens or "00:00"),
                    "close": time.fromisoformat(closes or "00:00"),
                    "closed": closed,
                },
            )
            horas_nuevas += 1
        if horas_nuevas:
            creado.append(f"{horas_nuevas} días de horario")

    # ── Resumen ──────────────────────────────────────────────────────────────
    async with engine.connect() as conn:
        servicios = (
            await conn.execute(
                text(
                    "select name, duration_minutes, price, capacity from services "
                    "where business_id = :b order by price nulls first, name"
                ),
                {"b": business_id},
            )
        ).all()

    print(f"\ntenant   : {TENANT['name']}  (slug {TENANT['slug']}, id {tenant_id})")
    print(f"negocio  : {BUSINESS['name']}  (id {business_id})")
    print(f"login    : {TENANT['admin_email']}  /  {PASSWORD}")
    print(f"creado   : {', '.join(creado) if creado else 'nada — ya estaba todo'}")
    print("\nservicios:")
    for name, minutes, price, capacity in servicios:
        precio = f"Bs {price / 100:.0f}" if price else "sin precio"
        print(f"  - {name:<22} {minutes:>3} min  {precio:>12}  cupo {capacity}")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
