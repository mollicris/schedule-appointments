"""
Script para ejecutar migraciones directamente con asyncpg.
Evita completamente SQLAlchemy sync engine.
"""

import asyncio
import asyncpg
from src.infrastructure.config.settings import get_settings


async def run_migrations():
    settings = get_settings()

    # Parsear la URL
    # postgresql+asyncpg://agente:agente_dev@localhost:5432/agente_citas
    url = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://")

    # Conectar a PostgreSQL
    conn = await asyncpg.connect(url)

    try:
        print("[OK] Conectado a PostgreSQL")

        # Habilitar pgvector (opcional)
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pgvector")
            print("[OK] Extension pgvector habilitada")
        except Exception as e:
            print(f"[WARN] pgvector no disponible (opcional): {e}")

        # Crear tabla de version de Alembic
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL PRIMARY KEY
            )
        """)

        # Crear las tablas (copiado del SQL de la migracion 001)
        sql = """
        -- Tenants (no tenant-aware)
        CREATE TABLE IF NOT EXISTS tenants (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(63) NOT NULL UNIQUE,
            admin_email VARCHAR(255) NOT NULL,
            industry VARCHAR(63) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending_verification',
            plan VARCHAR(50) NOT NULL DEFAULT 'trial',
            trial_ends_at TIMESTAMP WITH TIME ZONE,
            verified_at TIMESTAMP WITH TIME ZONE,
            onboarded_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_tenants_name ON tenants(name);
        CREATE INDEX IF NOT EXISTS ix_tenants_admin_email ON tenants(admin_email);

        -- Users
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            email VARCHAR(255) NOT NULL,
            phone VARCHAR(20),
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'staff',
            email_verified BOOLEAN NOT NULL DEFAULT false,
            phone_verified BOOLEAN NOT NULL DEFAULT false,
            verification_token VARCHAR(255),
            verification_token_expires_at TIMESTAMP WITH TIME ZONE,
            last_login_at TIMESTAMP WITH TIME ZONE,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_users_tenant_id ON users(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);

        -- Businesses
        CREATE TABLE IF NOT EXISTS businesses (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(127) NOT NULL,
            description TEXT,
            phone VARCHAR(20) NOT NULL,
            email VARCHAR(255),
            address TEXT,
            timezone VARCHAR(63) NOT NULL DEFAULT 'UTC',
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_businesses_tenant_id ON businesses(tenant_id);

        -- Services
        CREATE TABLE IF NOT EXISTS services (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            name VARCHAR(127) NOT NULL,
            description TEXT,
            duration_minutes INTEGER NOT NULL DEFAULT 30,
            price INTEGER,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_services_tenant_id ON services(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_services_business_id ON services(business_id);

        -- Professionals
        CREATE TABLE IF NOT EXISTS professionals (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(127) NOT NULL,
            phone VARCHAR(20),
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_professionals_tenant_id ON professionals(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_professionals_business_id ON professionals(business_id);
        CREATE INDEX IF NOT EXISTS ix_professionals_user_id ON professionals(user_id);

        -- Business Hours
        CREATE TABLE IF NOT EXISTS business_hours (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            day_of_week VARCHAR(1) NOT NULL,
            open_at TIME NOT NULL,
            close_at TIME NOT NULL,
            is_closed BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_business_hours_tenant_id ON business_hours(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_business_hours_business_id ON business_hours(business_id);

        -- Clients
        CREATE TABLE IF NOT EXISTS clients (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            whatsapp_number VARCHAR(20) NOT NULL,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            phone VARCHAR(20),
            notes TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            appointment_count INTEGER NOT NULL DEFAULT 0,
            last_appointment_at TIMESTAMP WITH TIME ZONE,
            last_interaction_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_clients_tenant_id ON clients(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_clients_whatsapp_number ON clients(whatsapp_number);

        -- Appointments
        CREATE TABLE IF NOT EXISTS appointments (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            service_id UUID NOT NULL REFERENCES services(id) ON DELETE RESTRICT,
            professional_id UUID REFERENCES professionals(id) ON DELETE SET NULL,
            client_id UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
            scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
            duration_minutes INTEGER NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            notes TEXT,
            cancelled_reason VARCHAR(255),
            cancelled_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_appointments_tenant_id ON appointments(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_appointments_business_id ON appointments(business_id);
        CREATE INDEX IF NOT EXISTS ix_appointments_client_id ON appointments(client_id);
        CREATE INDEX IF NOT EXISTS ix_appointments_scheduled_at ON appointments(scheduled_at);

        -- Conversations
        CREATE TABLE IF NOT EXISTS conversations (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            current_state VARCHAR(50) NOT NULL DEFAULT 'idle',
            collected_data JSONB NOT NULL DEFAULT '{}',
            message_count INTEGER NOT NULL DEFAULT 0,
            is_escalated BOOLEAN NOT NULL DEFAULT false,
            escalated_at TIMESTAMP WITH TIME ZONE,
            last_message_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_conversations_tenant_id ON conversations(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_conversations_business_id ON conversations(business_id);
        CREATE INDEX IF NOT EXISTS ix_conversations_client_id ON conversations(client_id);
        CREATE INDEX IF NOT EXISTS ix_conversations_last_message_at ON conversations(last_message_at);

        -- Messages
        CREATE TABLE IF NOT EXISTS messages (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            sender VARCHAR(20) NOT NULL,
            message_type VARCHAR(20) NOT NULL DEFAULT 'text',
            content TEXT NOT NULL,
            extra_data JSONB,
            whatsapp_message_id VARCHAR(255) UNIQUE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_messages_tenant_id ON messages(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_messages_conversation_id ON messages(conversation_id);
        CREATE INDEX IF NOT EXISTS ix_messages_created_at ON messages(created_at);
        """

        # Ejecutar el SQL completo
        await conn.execute(sql)
        print("[OK] Todas las tablas creadas correctamente")

        # Registrar la migracion como completada
        try:
            await conn.execute("INSERT INTO alembic_version VALUES ('001')")
            print("[OK] Migracion 001 registrada")
        except Exception:
            print("[INFO] Migracion 001 ya estaba registrada")

        # Verificar tablas creadas
        result = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        print("\n[OK] Tablas en la BD:")
        for row in result:
            print(f"  - {row['table_name']}")

    finally:
        await conn.close()
        print("\n[OK] Desconectado de PostgreSQL")


if __name__ == "__main__":
    asyncio.run(run_migrations())
