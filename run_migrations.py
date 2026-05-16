"""
Script para ejecutar migraciones directamente sin Alembic CLI.
Evita los problemas de psycopg2 en Windows 32-bit.
"""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.infrastructure.config.settings import get_settings
from src.infrastructure.persistence.database import Base
# Importar los modelos para que se registren en Base.metadata
from src.infrastructure.persistence.models import (  # noqa: F401
    AppointmentModel,
    BusinessHourModel,
    BusinessModel,
    ClientModel,
    ConversationModel,
    MessageModel,
    ProfessionalModel,
    ServiceModel,
    TenantModel,
    UserModel,
)


async def run_migrations():
    settings = get_settings()

    # Crear engine con asyncpg
    engine = create_async_engine(
        settings.database_url,
        echo=True,
    )

    try:
        async with engine.begin() as conn:
            # Crear todas las tablas desde los modelos
            await conn.run_sync(Base.metadata.create_all)

            # Marcar la migración como ejecutada
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR(32) NOT NULL,
                    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                )
            """))

            await conn.execute(text("""
                INSERT INTO alembic_version (version_num)
                VALUES ('001')
                ON CONFLICT DO NOTHING
            """))

            print("✅ Base de datos inicializada correctamente")
            print("✅ Todas las tablas creadas")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migrations())
