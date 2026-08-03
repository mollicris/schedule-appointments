BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 001

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE tenants (
    id UUID NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    slug VARCHAR(63) NOT NULL, 
    admin_email VARCHAR(255) NOT NULL, 
    industry VARCHAR(63) NOT NULL, 
    status VARCHAR(50) DEFAULT 'pending_verification' NOT NULL, 
    plan VARCHAR(50) DEFAULT 'trial' NOT NULL, 
    trial_ends_at TIMESTAMP WITH TIME ZONE, 
    verified_at TIMESTAMP WITH TIME ZONE, 
    onboarded_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (slug)
);

CREATE INDEX ix_tenants_name ON tenants (name);

CREATE INDEX ix_tenants_admin_email ON tenants (admin_email);

CREATE TABLE users (
    id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    phone VARCHAR(20), 
    password_hash VARCHAR(255) NOT NULL, 
    role VARCHAR(50) DEFAULT 'staff' NOT NULL, 
    email_verified BOOLEAN DEFAULT 'false' NOT NULL, 
    phone_verified BOOLEAN DEFAULT 'false' NOT NULL, 
    verification_token VARCHAR(255), 
    verification_token_expires_at TIMESTAMP WITH TIME ZONE, 
    last_login_at TIMESTAMP WITH TIME ZONE, 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_users_tenant_id ON users (tenant_id);

CREATE INDEX ix_users_email ON users (email);

CREATE TABLE businesses (
    id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    slug VARCHAR(127) NOT NULL, 
    description TEXT, 
    phone VARCHAR(20) NOT NULL, 
    email VARCHAR(255), 
    address TEXT, 
    timezone VARCHAR(63) DEFAULT 'UTC' NOT NULL, 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_businesses_tenant_id ON businesses (tenant_id);

CREATE TABLE services (
    id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    business_id UUID NOT NULL, 
    name VARCHAR(127) NOT NULL, 
    description TEXT, 
    duration_minutes INTEGER DEFAULT '30' NOT NULL, 
    price INTEGER, 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);

CREATE INDEX ix_services_tenant_id ON services (tenant_id);

CREATE INDEX ix_services_business_id ON services (business_id);

CREATE TABLE professionals (
    id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    business_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    name VARCHAR(127) NOT NULL, 
    phone VARCHAR(20), 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_professionals_tenant_id ON professionals (tenant_id);

CREATE INDEX ix_professionals_business_id ON professionals (business_id);

CREATE INDEX ix_professionals_user_id ON professionals (user_id);

CREATE TABLE business_hours (
    id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    business_id UUID NOT NULL, 
    day_of_week VARCHAR(1) NOT NULL, 
    open_at TIME WITHOUT TIME ZONE NOT NULL, 
    close_at TIME WITHOUT TIME ZONE NOT NULL, 
    is_closed BOOLEAN DEFAULT 'false' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);

CREATE INDEX ix_business_hours_tenant_id ON business_hours (tenant_id);

CREATE INDEX ix_business_hours_business_id ON business_hours (business_id);

CREATE TABLE clients (
    id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    whatsapp_number VARCHAR(20) NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    email VARCHAR(255), 
    phone VARCHAR(20), 
    notes TEXT, 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    appointment_count INTEGER DEFAULT '0' NOT NULL, 
    last_appointment_at TIMESTAMP WITH TIME ZONE, 
    last_interaction_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_clients_tenant_id ON clients (tenant_id);

CREATE INDEX ix_clients_whatsapp_number ON clients (whatsapp_number);

CREATE TABLE appointments (
    id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    business_id UUID NOT NULL, 
    service_id UUID NOT NULL, 
    professional_id UUID, 
    client_id UUID NOT NULL, 
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    duration_minutes INTEGER NOT NULL, 
    status VARCHAR(50) DEFAULT 'pending' NOT NULL, 
    notes TEXT, 
    cancelled_reason VARCHAR(255), 
    cancelled_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE, 
    FOREIGN KEY(service_id) REFERENCES services (id) ON DELETE RESTRICT, 
    FOREIGN KEY(professional_id) REFERENCES professionals (id) ON DELETE SET NULL, 
    FOREIGN KEY(client_id) REFERENCES clients (id) ON DELETE RESTRICT
);

CREATE INDEX ix_appointments_tenant_id ON appointments (tenant_id);

CREATE INDEX ix_appointments_business_id ON appointments (business_id);

CREATE INDEX ix_appointments_client_id ON appointments (client_id);

CREATE INDEX ix_appointments_scheduled_at ON appointments (scheduled_at);

CREATE TABLE conversations (
    id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    business_id UUID NOT NULL, 
    client_id UUID NOT NULL, 
    current_state VARCHAR(50) DEFAULT 'idle' NOT NULL, 
    collected_data JSONB DEFAULT '{}' NOT NULL, 
    message_count INTEGER DEFAULT '0' NOT NULL, 
    is_escalated BOOLEAN DEFAULT 'false' NOT NULL, 
    escalated_at TIMESTAMP WITH TIME ZONE, 
    last_message_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE, 
    FOREIGN KEY(client_id) REFERENCES clients (id) ON DELETE CASCADE
);

CREATE INDEX ix_conversations_tenant_id ON conversations (tenant_id);

CREATE INDEX ix_conversations_business_id ON conversations (business_id);

CREATE INDEX ix_conversations_client_id ON conversations (client_id);

CREATE INDEX ix_conversations_last_message_at ON conversations (last_message_at);

CREATE TABLE messages (
    id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    conversation_id UUID NOT NULL, 
    sender VARCHAR(20) NOT NULL, 
    message_type VARCHAR(20) DEFAULT 'text' NOT NULL, 
    content TEXT NOT NULL, 
    extra_data JSONB, 
    whatsapp_message_id VARCHAR(255), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE, 
    UNIQUE (whatsapp_message_id)
);

CREATE INDEX ix_messages_tenant_id ON messages (tenant_id);

CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);

CREATE INDEX ix_messages_created_at ON messages (created_at);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;

ALTER TABLE businesses ENABLE ROW LEVEL SECURITY;

ALTER TABLE services ENABLE ROW LEVEL SECURITY;

ALTER TABLE professionals ENABLE ROW LEVEL SECURITY;

ALTER TABLE business_hours ENABLE ROW LEVEL SECURITY;

ALTER TABLE clients ENABLE ROW LEVEL SECURITY;

ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_select ON users
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_insert ON users
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_update ON users
            FOR UPDATE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_delete ON users
            FOR DELETE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_select ON businesses
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_insert ON businesses
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_update ON businesses
            FOR UPDATE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_delete ON businesses
            FOR DELETE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_select ON services
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_insert ON services
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_update ON services
            FOR UPDATE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_delete ON services
            FOR DELETE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_select ON professionals
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_insert ON professionals
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_update ON professionals
            FOR UPDATE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_delete ON professionals
            FOR DELETE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_select ON business_hours
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_insert ON business_hours
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_update ON business_hours
            FOR UPDATE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_delete ON business_hours
            FOR DELETE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_select ON clients
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_insert ON clients
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_update ON clients
            FOR UPDATE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_delete ON clients
            FOR DELETE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_select ON appointments
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_insert ON appointments
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_update ON appointments
            FOR UPDATE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_delete ON appointments
            FOR DELETE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_select ON conversations
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_insert ON conversations
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_update ON conversations
            FOR UPDATE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_delete ON conversations
            FOR DELETE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_select ON messages
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_insert ON messages
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_update ON messages
            FOR UPDATE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_delete ON messages
            FOR DELETE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

INSERT INTO alembic_version (version_num) VALUES ('001') RETURNING alembic_version.version_num;

-- Running upgrade 001 -> 002

ALTER TABLE businesses ADD COLUMN whatsapp_phone_number_id VARCHAR(64);

ALTER TABLE businesses ADD COLUMN whatsapp_app_secret VARCHAR(255);

CREATE INDEX ix_businesses_whatsapp_phone_number_id ON businesses (whatsapp_phone_number_id);

CREATE INDEX ix_appointments_professional_id ON appointments (professional_id);

ALTER TABLE business_hours ADD CONSTRAINT uq_business_hours_business_day UNIQUE (business_id, day_of_week);

UPDATE alembic_version SET version_num='002' WHERE alembic_version.version_num = '001';

-- Running upgrade 002 -> 003

ALTER TABLE appointments ADD COLUMN reminder_sent_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE businesses ADD COLUMN owner_whatsapp VARCHAR(20);

CREATE TABLE human_transfers (
    id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    business_id UUID NOT NULL, 
    conversation_id UUID NOT NULL, 
    client_id UUID NOT NULL, 
    reason TEXT, 
    context_snapshot JSONB DEFAULT '[]' NOT NULL, 
    status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
    resolved_at TIMESTAMP WITH TIME ZONE, 
    resolved_by_id UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE, 
    FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE, 
    FOREIGN KEY(client_id) REFERENCES clients (id)
);

CREATE INDEX ix_human_transfers_client_id ON human_transfers (client_id);

CREATE INDEX ix_human_transfers_business_id ON human_transfers (business_id);

CREATE INDEX ix_human_transfers_tenant_id ON human_transfers (tenant_id);

CREATE INDEX ix_human_transfers_conversation_id ON human_transfers (conversation_id);

CREATE INDEX ix_human_transfers_status ON human_transfers (status);

UPDATE alembic_version SET version_num='003' WHERE alembic_version.version_num = '002';

-- Running upgrade 003 -> 004

ALTER TABLE business_hours ADD COLUMN sequence INTEGER DEFAULT '1' NOT NULL;

ALTER TABLE business_hours DROP CONSTRAINT uq_business_hours_business_day;

ALTER TABLE business_hours ADD CONSTRAINT uq_business_hours_business_day_sequence UNIQUE (business_id, day_of_week, sequence);

UPDATE alembic_version SET version_num='004' WHERE alembic_version.version_num = '003';

-- Running upgrade 004 -> 005

ALTER TABLE professionals ALTER COLUMN user_id DROP NOT NULL;

UPDATE alembic_version SET version_num='005' WHERE alembic_version.version_num = '004';

-- Running upgrade 005 -> 006

CREATE TABLE service_professionals (
    tenant_id UUID NOT NULL, 
    service_id UUID NOT NULL, 
    professional_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (service_id, professional_id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    FOREIGN KEY(service_id) REFERENCES services (id) ON DELETE CASCADE, 
    FOREIGN KEY(professional_id) REFERENCES professionals (id) ON DELETE CASCADE
);

CREATE INDEX ix_service_professionals_professional ON service_professionals (professional_id);

CREATE INDEX ix_service_professionals_tenant ON service_professionals (tenant_id);

ALTER TABLE service_professionals ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_select ON service_professionals
        FOR SELECT
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_insert ON service_professionals
        FOR INSERT
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_update ON service_professionals
        FOR UPDATE
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_delete ON service_professionals
        FOR DELETE
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

UPDATE alembic_version SET version_num='006' WHERE alembic_version.version_num = '005';

-- Running upgrade 006 -> 007

ALTER TABLE businesses ADD COLUMN whatsapp_waba_id VARCHAR(64);

ALTER TABLE businesses ADD COLUMN whatsapp_access_token VARCHAR(512);

CREATE INDEX ix_businesses_whatsapp_waba_id ON businesses (whatsapp_waba_id);

UPDATE alembic_version SET version_num='007' WHERE alembic_version.version_num = '006';

-- Running upgrade 007 -> 008

ALTER TABLE services ADD COLUMN capacity INTEGER DEFAULT '1' NOT NULL;

UPDATE alembic_version SET version_num='008' WHERE alembic_version.version_num = '007';

-- Running upgrade 008 -> 009

CREATE TABLE membership_plans (
    id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    business_id UUID NOT NULL, 
    name VARCHAR(127) NOT NULL, 
    description TEXT, 
    price INTEGER DEFAULT '0' NOT NULL, 
    billing_period VARCHAR(20) DEFAULT 'monthly' NOT NULL, 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);

CREATE INDEX ix_membership_plans_tenant ON membership_plans (tenant_id);

CREATE INDEX ix_membership_plans_business ON membership_plans (business_id);

CREATE TABLE membership_plan_services (
    id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    membership_plan_id UUID NOT NULL, 
    service_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    FOREIGN KEY(membership_plan_id) REFERENCES membership_plans (id) ON DELETE CASCADE, 
    FOREIGN KEY(service_id) REFERENCES services (id) ON DELETE CASCADE, 
    CONSTRAINT uq_membership_plan_services_plan_service UNIQUE (membership_plan_id, service_id)
);

CREATE INDEX ix_membership_plan_services_tenant ON membership_plan_services (tenant_id);

CREATE INDEX ix_membership_plan_services_plan ON membership_plan_services (membership_plan_id);

CREATE INDEX ix_membership_plan_services_service ON membership_plan_services (service_id);

CREATE TABLE memberships (
    id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    business_id UUID NOT NULL, 
    client_id UUID NOT NULL, 
    membership_plan_id UUID NOT NULL, 
    status VARCHAR(20) DEFAULT 'active' NOT NULL, 
    starts_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    ends_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    billing_period VARCHAR(20) DEFAULT 'monthly' NOT NULL, 
    price_paid INTEGER DEFAULT '0' NOT NULL, 
    frozen_at TIMESTAMP WITH TIME ZONE, 
    frozen_days_used INTEGER DEFAULT '0' NOT NULL, 
    renewal_count INTEGER DEFAULT '0' NOT NULL, 
    cancelled_at TIMESTAMP WITH TIME ZONE, 
    cancelled_reason TEXT, 
    notes TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE, 
    FOREIGN KEY(client_id) REFERENCES clients (id) ON DELETE RESTRICT, 
    FOREIGN KEY(membership_plan_id) REFERENCES membership_plans (id) ON DELETE RESTRICT
);

CREATE INDEX ix_memberships_tenant ON memberships (tenant_id);

CREATE INDEX ix_memberships_business ON memberships (business_id);

CREATE INDEX ix_memberships_client ON memberships (client_id);

CREATE INDEX ix_memberships_ends_at ON memberships (ends_at);

CREATE UNIQUE INDEX uq_memberships_one_live_per_client
        ON memberships (tenant_id, business_id, client_id)
        WHERE status IN ('active', 'frozen');

ALTER TABLE membership_plans ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_select ON membership_plans
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_insert ON membership_plans
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_update ON membership_plans
            FOR UPDATE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_delete ON membership_plans
            FOR DELETE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

ALTER TABLE membership_plan_services ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_select ON membership_plan_services
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_insert ON membership_plan_services
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_update ON membership_plan_services
            FOR UPDATE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_delete ON membership_plan_services
            FOR DELETE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_select ON memberships
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_insert ON memberships
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_update ON memberships
            FOR UPDATE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_delete ON memberships
            FOR DELETE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

UPDATE alembic_version SET version_num='009' WHERE alembic_version.version_num = '008';

-- Running upgrade 009 -> 010

CREATE TABLE campaign_sends (
    id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    business_id UUID NOT NULL, 
    client_id UUID NOT NULL, 
    campaign_key VARCHAR(50) NOT NULL, 
    dedupe_key VARCHAR(160) NOT NULL, 
    sent_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE, 
    FOREIGN KEY(client_id) REFERENCES clients (id) ON DELETE CASCADE, 
    CONSTRAINT uq_campaign_sends_tenant_dedupe UNIQUE (tenant_id, dedupe_key)
);

CREATE INDEX ix_campaign_sends_tenant ON campaign_sends (tenant_id);

CREATE INDEX ix_campaign_sends_business ON campaign_sends (business_id);

CREATE INDEX ix_campaign_sends_client ON campaign_sends (client_id);

ALTER TABLE campaign_sends ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_select ON campaign_sends
        FOR SELECT
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_insert ON campaign_sends
        FOR INSERT
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_update ON campaign_sends
        FOR UPDATE
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_delete ON campaign_sends
        FOR DELETE
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

UPDATE alembic_version SET version_num='010' WHERE alembic_version.version_num = '009';

-- Running upgrade 010 -> 011

ALTER TABLE clients ADD COLUMN channel VARCHAR(20) DEFAULT 'whatsapp' NOT NULL;

ALTER TABLE clients ADD COLUMN external_id VARCHAR(64);

UPDATE clients SET external_id = whatsapp_number WHERE external_id IS NULL;

ALTER TABLE clients ALTER COLUMN external_id SET NOT NULL;

ALTER TABLE clients ALTER COLUMN whatsapp_number DROP NOT NULL;

CREATE INDEX ix_clients_external_id ON clients (external_id);

ALTER TABLE clients ADD CONSTRAINT uq_clients_tenant_channel_external UNIQUE (tenant_id, channel, external_id);

ALTER TABLE conversations ADD COLUMN channel VARCHAR(20) DEFAULT 'whatsapp' NOT NULL;

ALTER TABLE messages RENAME whatsapp_message_id TO external_message_id;

UPDATE alembic_version SET version_num='011' WHERE alembic_version.version_num = '010';

-- Running upgrade 011 -> 012

ALTER TABLE businesses ADD COLUMN facebook_page_id VARCHAR(64);

ALTER TABLE businesses ADD COLUMN facebook_page_access_token VARCHAR(512);

ALTER TABLE businesses ADD COLUMN instagram_account_id VARCHAR(64);

ALTER TABLE businesses ADD COLUMN meta_app_secret VARCHAR(255);

CREATE INDEX ix_businesses_facebook_page_id ON businesses (facebook_page_id);

CREATE INDEX ix_businesses_instagram_account_id ON businesses (instagram_account_id);

ALTER TABLE human_transfers ADD COLUMN kind VARCHAR(20) DEFAULT 'escalation' NOT NULL;

CREATE INDEX ix_human_transfers_kind ON human_transfers (kind);

UPDATE alembic_version SET version_num='012' WHERE alembic_version.version_num = '011';

COMMIT;

