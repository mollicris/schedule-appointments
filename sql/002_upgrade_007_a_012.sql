BEGIN;

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

