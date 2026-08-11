"""Mueve los canales de Meta (WhatsApp, Instagram, Messenger) a otro negocio.

El webhook resuelve a qué negocio pertenece un mensaje buscando el
phone_number_id en la base, así que cambiar de negocio activo es mover esas
credenciales — no hay que tocar nada en el panel de Meta ni reiniciar el túnel.

Las credenciales se MUEVEN, no se copian: si dos negocios tuvieran el mismo
phone_number_id la búsqueda sería ambigua y contestaría cualquiera de los dos.

Uso:
    python sql/007_cambiar_canal.py                 # muestra quién lo tiene hoy
    python sql/007_cambiar_canal.py peluqueria      # se lo pasa a ese negocio
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from sqlalchemy import text  # noqa: E402

from src.infrastructure.persistence.database import get_engine  # noqa: E402

CAMPOS = [
    "whatsapp_phone_number_id",
    "whatsapp_access_token",
    "whatsapp_app_secret",
    "whatsapp_waba_id",
    "owner_whatsapp",
    "facebook_page_id",
    "facebook_page_access_token",
    "instagram_account_id",
    "meta_app_secret",
]


async def main() -> int:
    destino = sys.argv[1].lower() if len(sys.argv) > 1 else None
    engine = get_engine()

    async with engine.begin() as conn:
        negocios = (
            await conn.execute(
                text(
                    "select b.id, b.name, b.slug, t.industry, "
                    "       b.whatsapp_phone_number_id, b.instagram_account_id "
                    "from businesses b join tenants t on t.id = b.tenant_id "
                    "where b.is_active order by b.created_at"
                )
            )
        ).mappings().all()

        print("\nnegocios activos:")
        actual = None
        for b in negocios:
            tiene = bool(b["whatsapp_phone_number_id"])
            if tiene:
                actual = b
            marca = "  <-- tiene el canal" if tiene else ""
            redes = " + redes" if b["instagram_account_id"] else ""
            print(f"  {b['slug']:<14} {b['name']:<14} ({b['industry']}){redes}{marca}")

        if destino is None:
            print("\nPara cambiarlo:  python sql/007_cambiar_canal.py <slug>")
            await engine.dispose()
            return 0

        nuevo = next((b for b in negocios if b["slug"] == destino), None)
        if nuevo is None:
            print(f"\n[FALLA] No hay un negocio activo con slug '{destino}'.")
            await engine.dispose()
            return 1

        if actual is None:
            print("\n[FALLA] Ningún negocio tiene el canal configurado; no hay nada que mover.")
            await engine.dispose()
            return 1

        if actual["id"] == nuevo["id"]:
            print(f"\n'{nuevo['name']}' ya tiene el canal. Nada que hacer.")
            await engine.dispose()
            return 0

        # Copiar al destino y limpiar el origen, dentro de la misma transacción.
        sets_destino = ", ".join(f"{c} = o.{c}" for c in CAMPOS)
        await conn.execute(
            text(
                f"update businesses set {sets_destino} "
                "from businesses o where businesses.id = :nuevo and o.id = :viejo"
            ),
            {"nuevo": nuevo["id"], "viejo": actual["id"]},
        )
        sets_origen = ", ".join(f"{c} = null" for c in CAMPOS)
        await conn.execute(
            text(f"update businesses set {sets_origen} where id = :viejo"),
            {"viejo": actual["id"]},
        )

        print(f"\nmovido: {actual['name']}  ->  {nuevo['name']}")

    async with engine.connect() as conn:
        fila = (
            await conn.execute(
                text(
                    "select b.name, t.industry, b.timezone, "
                    "       b.whatsapp_phone_number_id is not null as wa, "
                    "       b.instagram_account_id is not null as ig, "
                    "       (select count(*) from services s "
                    "         where s.business_id = b.id and s.is_active) as servicios "
                    "from businesses b join tenants t on t.id = b.tenant_id "
                    "where b.id = :i"
                ),
                {"i": nuevo["id"]},
            )
        ).mappings().one()

    print(
        f"\nahora responde : {fila['name']}  ·  industria {fila['industry']}"
        f"  ·  {fila['servicios']} servicios  ·  {fila['timezone']}"
    )
    print(f"canales        : WhatsApp {'si' if fila['wa'] else 'no'}"
          f"  ·  Instagram/Messenger {'si' if fila['ig'] else 'no'}")
    print("\nNo hace falta tocar Meta ni reiniciar el túnel: el número es el mismo,")
    print("solo cambió a qué negocio apunta. Mandá un mensaje y contesta el nuevo.")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
