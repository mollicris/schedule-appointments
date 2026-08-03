"""Diagnostico de la conexion a la base configurada en DATABASE_URL.

Revisa la forma de la URL, conecta, y reporta version del servidor, extension
pgvector, tablas y revision de Alembic. No imprime la contrasena.

Uso:  .venv\\Scripts\\python.exe sql/check_supabase.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# El script vive en sql/, así que el paquete `src` no está en el path y el .env
# se busca relativo al directorio actual: ambas cosas se resuelven acá para
# poder ejecutarlo desde cualquier lado.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from sqlalchemy import text  # noqa: E402

from src.infrastructure.config.settings import get_settings  # noqa: E402
from src.infrastructure.persistence.database import get_engine  # noqa: E402

TABLAS_ESPERADAS = 17


def revisar_url(url: str) -> list[str]:
    """Errores de forma que dan mensajes confusos si se dejan pasar."""
    problemas: list[str] = []

    if "+asyncpg" not in url:
        problemas.append(
            "Falta '+asyncpg' en el esquema: con 'postgresql://' SQLAlchemy busca "
            "psycopg2, que no está instalado. Usá 'postgresql+asyncpg://'."
        )

    parsed = urlparse(url.replace("postgresql+asyncpg", "postgresql"))
    if not parsed.password:
        problemas.append("La URL no trae contraseña (revisá los dos puntos antes de la @).")
    if parsed.port == 6543:
        problemas.append(
            "Puerto 6543 = pooler transaccional. Funciona porque el engine "
            "desactiva el cache de prepared statements, pero el pooler de sesión "
            "(puerto 5432) es más simple si tu red llega por IPv4."
        )
    if parsed.hostname and parsed.hostname.startswith("db.") and parsed.hostname.endswith(
        ".supabase.co"
    ):
        problemas.append(
            "Conexión directa de Supabase: sólo responde por IPv6. Si tu red o "
            "Cloud Run no tienen IPv6, usá el host del pooler."
        )
    return problemas


async def main() -> int:
    settings = get_settings()
    url = settings.database_url
    parsed = urlparse(url.replace("postgresql+asyncpg", "postgresql"))
    print(f"host={parsed.hostname}  puerto={parsed.port}  base={(parsed.path or '/').lstrip('/')}")
    print(f"usuario={parsed.username}  contraseña={'definida' if parsed.password else 'FALTA'}")

    problemas = revisar_url(url)
    for p in problemas:
        print(f"  [aviso] {p}")

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            version = await conn.scalar(text("select version()"))
            print(f"\n[OK] conectado: {str(version)[:60]}…")

            vector = await conn.scalar(
                text("select count(*) from pg_extension where extname = 'vector'")
            )
            print(f"  pgvector: {'instalada' if vector else 'FALTA (créala en Database → Extensions)'}")

            tablas = await conn.scalar(
                text("select count(*) from information_schema.tables where table_schema = 'public'")
            )
            print(f"  tablas en public: {tablas} (esperadas {TABLAS_ESPERADAS})")

            revision = None
            if tablas:
                revision = await conn.scalar(
                    text(
                        "select version_num from alembic_version "
                        "where exists (select 1 from information_schema.tables "
                        "where table_name = 'alembic_version')"
                    )
                )
            print(f"  revisión de Alembic: {revision or 'sin alembic_version — cargá 001_schema_completo.sql'}")

            if tablas:
                negocios = await conn.scalar(text("select count(*) from businesses"))
                clientes = await conn.scalar(text("select count(*) from clients"))
                print(f"  datos: {negocios} negocios, {clientes} clientes")
        await engine.dispose()
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"\n[FALLA] no se pudo conectar: {type(exc).__name__}: {str(exc)[:300]}")
        print(
            "\nPistas: contraseña incorrecta → 'password authentication failed'; "
            "IPv6 sin salida → 'Network is unreachable'; host mal escrito → "
            "'Name or service not known'."
        )
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
