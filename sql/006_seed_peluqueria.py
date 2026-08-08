"""Crea el tenant de una peluquería, con estilistas y sus servicios asignados.

Igual que 005_seed_restaurante.py: escribe directo en DATABASE_URL, sin depender
de que el backend esté levantado ni del correo de verificación. Es idempotente.

Lo propio de este rubro son los ESTILISTAS: el cliente reserva con quien lo
atiende siempre, así que se cargan como profesionales y se vincula cada uno con
los servicios que hace. Sin plan de membresía — una peluquería no los tiene, y
así se verifica que el bloque de planes no aparezca cuando no corresponde.

Uso:  .venv\\Scripts\\python.exe sql/006_seed_peluqueria.py
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
    "name": "Peluquería",
    "slug": "peluqueria",
    "industry": "peluqueria",   # debe coincidir con la clave en _INDUSTRY_HINTS
    "admin_email": "peluqueria@datec.com.bo",
}
PASSWORD = "Peluqueria2026!"

BUSINESS = {
    "name": "Peluquería",
    "slug": "peluqueria",
    "phone": "59169334673",
    "timezone": "America/La_Paz",
    "description": "Peluquería y estética: corte, color, tratamientos y peinados",
}

# price en CENTAVOS (25000 = Bs 250). capacity = cuántos turnos simultáneos
# admite el servicio, que acá lo limita la cantidad de estilistas que lo hacen.
SERVICES = [
    ("Corte caballero",      "Corte y peinado para caballero",             30,   4000, 3),
    ("Corte dama",           "Corte, lavado y secado",                     45,   6000, 3),
    ("Corte y peinado",      "Corte con peinado de salón",                 60,   9000, 2),
    ("Color",                "Tintura completa. El precio varía con el largo", 120, 25000, 2),
    ("Mechas o balayage",    "Técnica de color. El precio varía con el largo", 180, 45000, 1),
    ("Tratamiento capilar",  "Hidratación o reconstrucción",               60,  12000, 2),
    ("Peinado para evento",  "Recogido o peinado de fiesta",               60,  15000, 2),
    ("Manicure",             "Manicure completa con esmaltado",            45,   5000, 2),
]

# Cada estilista con los servicios que hace. El nombre debe existir arriba.
PROFESSIONALS = [
    ("Ana",     ["Corte dama", "Corte y peinado", "Color", "Mechas o balayage",
                 "Tratamiento capilar", "Peinado para evento"]),
    ("Carla",   ["Corte dama", "Corte y peinado", "Color", "Tratamiento capilar",
                 "Peinado para evento", "Manicure"]),
    ("Marcos",  ["Corte caballero", "Corte dama", "Color"]),
]

# día 0 = lunes … 6 = domingo. Lunes y domingo cerrado.
HOURS = [
    ("0", None, None, True),
    ("1", "09:00", "19:00", False),
    ("2", "09:00", "19:00", False),
    ("3", "09:00", "19:00", False),
    ("4", "09:00", "19:00", False),
    ("5", "09:00", "18:00", False),
    ("6", None, None, True),
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
                    "id": tenant_id, "name": TENANT["name"], "slug": TENANT["slug"],
                    "email": TENANT["admin_email"], "industry": TENANT["industry"],
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
                    "id": uuid4(), "tenant": tenant_id, "email": TENANT["admin_email"],
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
                    "id": business_id, "tenant": tenant_id, "name": BUSINESS["name"],
                    "slug": BUSINESS["slug"], "desc": BUSINESS["description"],
                    "phone": BUSINESS["phone"], "tz": BUSINESS["timezone"],
                },
            )
            creado.append("negocio")

        # ── Servicios ────────────────────────────────────────────────────────
        servicio_id: dict[str, object] = {}
        nuevos = 0
        for name, desc, minutes, price, capacity in SERVICES:
            sid = await conn.scalar(
                text("select id from services where business_id = :b and name = :n"),
                {"b": business_id, "n": name},
            )
            if sid is None:
                sid = uuid4()
                await conn.execute(
                    text(
                        "insert into services (id, tenant_id, business_id, name, description, "
                        "duration_minutes, price, capacity, is_active) "
                        "values (:id, :t, :b, :n, :d, :min, :p, :cap, true)"
                    ),
                    {
                        "id": sid, "t": tenant_id, "b": business_id, "n": name,
                        "d": desc, "min": minutes, "p": price, "cap": capacity,
                    },
                )
                nuevos += 1
            servicio_id[name] = sid
        if nuevos:
            creado.append(f"{nuevos} servicios")

        # ── Estilistas y qué hace cada uno ───────────────────────────────────
        prof_nuevos = 0
        vinculos = 0
        for nombre, servicios in PROFESSIONALS:
            pid = await conn.scalar(
                text("select id from professionals where business_id = :b and name = :n"),
                {"b": business_id, "n": nombre},
            )
            if pid is None:
                pid = uuid4()
                await conn.execute(
                    text(
                        "insert into professionals (id, tenant_id, business_id, name, is_active) "
                        "values (:id, :t, :b, :n, true)"
                    ),
                    {"id": pid, "t": tenant_id, "b": business_id, "n": nombre},
                )
                prof_nuevos += 1

            for s in servicios:
                sid = servicio_id.get(s)
                if sid is None:
                    print(f"  [aviso] {nombre} referencia un servicio inexistente: {s}")
                    continue
                ya = await conn.scalar(
                    text(
                        "select 1 from service_professionals "
                        "where service_id = :s and professional_id = :p"
                    ),
                    {"s": sid, "p": pid},
                )
                if ya:
                    continue
                await conn.execute(
                    text(
                        "insert into service_professionals (tenant_id, service_id, professional_id) "
                        "values (:t, :s, :p)"
                    ),
                    {"t": tenant_id, "s": sid, "p": pid},
                )
                vinculos += 1
        if prof_nuevos:
            creado.append(f"{prof_nuevos} estilistas")
        if vinculos:
            creado.append(f"{vinculos} asignaciones de servicio")

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
                    "select s.name, s.duration_minutes, s.price, s.capacity, "
                    "       count(sp.professional_id) as estilistas "
                    "from services s "
                    "left join service_professionals sp on sp.service_id = s.id "
                    "where s.business_id = :b "
                    "group by s.id, s.name, s.duration_minutes, s.price, s.capacity "
                    "order by s.duration_minutes, s.name"
                ),
                {"b": business_id},
            )
        ).all()

    print(f"\ntenant   : {TENANT['name']}  (slug {TENANT['slug']}, id {tenant_id})")
    print(f"negocio  : {BUSINESS['name']}  (id {business_id})")
    print(f"login    : {TENANT['admin_email']}  /  {PASSWORD}")
    print(f"creado   : {', '.join(creado) if creado else 'nada — ya estaba todo'}")
    print("\nservicios:")
    for name, minutes, price, capacity, estilistas in servicios:
        precio = f"Bs {price / 100:.0f}" if price else "sin precio"
        print(
            f"  - {name:<22} {minutes:>3} min  {precio:>9}  "
            f"cupo {capacity}  ·  {estilistas} estilista(s)"
        )

    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
