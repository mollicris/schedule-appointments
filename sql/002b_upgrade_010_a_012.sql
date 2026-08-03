BEGIN;

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

